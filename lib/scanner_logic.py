import re
import pdfplumber
import pandas as pd
from datetime import datetime
import requests
import os
from dotenv import load_dotenv
from lib.db import fetch_scanner_context, fetch_categories

load_dotenv()

def generate_transaction_dataframe(pdf_path) -> pd.DataFrame:
    # === STEP 1: Extract text from PDF ===
    lines_data = []
    with pdfplumber.open(pdf_path) as pdf:
        for i, page in enumerate(pdf.pages):
            text = page.extract_text()
            if text:
                for j, line in enumerate(text.splitlines()):
                    lines_data.append({
                        "page": i + 1,
                        "line_number": j + 1,
                        "text": line.strip()
                    })

    df = pd.DataFrame(lines_data)

    # === STEP 2: Preprocessing and Normalisation ===
    iban_re = re.compile(r"\bBE\d{2}\d{12,16}\b")
    bic_re = re.compile(r"\b[A-Z]{6}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b")
    time_re = re.compile(r"\bOM\s?(\d{1,2})[.:](\d{2})\s?UUR\b", re.IGNORECASE)
    footer_re = re.compile(
        r"^\d{4}-\d{2}-\d{2}-\d{2}\.\d{2}\.\d{2}\.\d{9}A\s+afschrift\s+\d+\s+\d+/\d+$",
        re.IGNORECASE
    )
    header_line_re = re.compile(
        r"^van\d{2}-\d{2}-\d{4}tot\d{2}-\d{2}-\d{4}$", re.IGNORECASE
    )

    def is_irrelevant_line(s):
        s_norm = s.strip().lower().replace(" ", "")
        return (
            not s.strip()
            or iban_re.search(s)
            or bic_re.search(s)
            or time_re.search(s)
            or footer_re.search(s)
            or s.strip().lower().startswith("kbc-rekening")
            or s.strip().lower().startswith("ibanbe")
            or "met kbc mobile" in s.lower()
            or "bankier" in s.lower()
            or "nr." in s.lower() and "datum" in s.lower() and "omschrijving" in s.lower()
            or header_line_re.match(s_norm)
        )

    header_re = re.compile(
        r"^\s*(?P<trx>\d{3})\s+"
        r"(?P<date>\d{2}-\d{2}-\d{4})\s+"
        r"(?P<desc>.+?)\s+"
        r"(?P<amount>\d{1,3}(?:\.\d{3})*,\d{2})(?P<sign>[+-])\s*$"
    )

    def normalise_text(s):
        s = re.sub(r"(OVERSCHRIJVING)(VAN|NAAR)", r"\1 \2", s, flags=re.IGNORECASE)
        s = re.sub(r"(INSTANT)(OVERSCHRIJVING)", r"\1 \2", s, flags=re.IGNORECASE)
        s = re.sub(r"(INSTANT OVERSCHRIJVING)(VAN|NAAR)", r"\1 \2", s, flags=re.IGNORECASE)
        s = re.sub(r"\bOM(\d{1,2}[.:]\d{2})UUR\b", r"OM \1 UUR", s, flags=re.IGNORECASE)
        s = re.sub(r"METKBCMOBILE", "MET KBC MOBILE", s, flags=re.IGNORECASE)
        return s.strip()

    df["text_norm"] = df["text"].map(normalise_text)

    # === STEP 3: Grouping transactions ===
    transactions = []
    current = None

    for _, row in df.iterrows():
        t = row["text_norm"]
        m = header_re.match(t)
        if m:
            if current:
                transactions.append(current)
            trx_no = int(m.group("trx"))
            date_str = m.group("date")
            desc = m.group("desc").strip()
            amount_str = m.group("amount")
            sign = m.group("sign")
            try:
                date_iso = datetime.strptime(date_str, "%d-%m-%Y").date().isoformat()
            except:
                date_iso = None
            amt = float(amount_str.replace(".", "").replace(",", "."))
            current = {
                "trx_no": trx_no,
                "date": date_iso,
                "amount_eur": amt,
                "sign": sign,
                "type_desc": desc,
                "page_start": int(row["page"]),
                "line_start": int(row["line_number"]),
                "header_text": row["text_norm"],
                "details": [],
            }
        else:
            if current:
                current["details"].append(row["text_norm"])

    if current:
        transactions.append(current)

    # === STEP 4: Extract structured info ===
    def pick_counterparty_name(lines):
        for s in lines:
            if is_irrelevant_line(s): continue
            return s.strip()
        return None

    records = []
    for tr in transactions:
        lines = tr["details"]
        ibans = []
        bics = []
        tm = None
        for s in lines:
            ibans += iban_re.findall(s)
            bics += bic_re.findall(s)
            tm_m = time_re.search(s)
            if tm_m and not tm:
                hh, mm = tm_m.group(1), tm_m.group(2)
                tm = f"{int(hh):02d}:{int(mm):02d}"
        counterparty_name = pick_counterparty_name(lines)
        msg_parts = []
        for s in lines:
            if is_irrelevant_line(s): continue
            if counterparty_name and s.strip() == counterparty_name: continue
            msg_parts.append(s.strip())
        message = " | ".join(msg_parts) if msg_parts else None
        direction = "income" if tr["amount_eur"] > 0 else "expense"
        type_desc = re.sub(r"\s+", " ", tr["type_desc"]).strip()
        records.append({
            "trx_no": tr["trx_no"],
            "date": tr["date"],
            "time": tm,
            "amount_eur": tr["amount_eur"],
            "direction": direction,
            "type": type_desc,
            "counterparty_name": counterparty_name,
            "counterparty_iban": ibans[0] if ibans else None,
            "counterparty_bic": bics[0] if bics else None,
            "message": message,
            "page_start": tr["page_start"],
            "line_start": tr["line_start"],
        })

    tx_df = pd.DataFrame(records)
    tx_df.head(20)

    return tx_df


def transaction_categorisation(tx_df1) -> pd.DataFrame:
    # === CONFIG ===

    API_KEY = os.getenv("GEMINI_API_KEY")
    BASE_URL = os.getenv("GEMINI_API_URL")

    if not API_KEY or not BASE_URL:
        raise ValueError("Missing Gemini API key or URL in environment variables")

    ENDPOINT = f"{BASE_URL}?key={API_KEY}"

    VALID_CATEGORIES = fetch_categories()["name"].tolist()
    print("Valid categories:", VALID_CATEGORIES)

    # === Editable categorisation context (update freely) ===
    CATEGORISATION_CONTEXT = fetch_scanner_context()

    # === PROMPT GENERATOR ===
    def format_prompt(message: str, amount: float) -> str:
        return f"""You are given a bank transaction and a fixed list of valid categories.
    Use the context to determine the best category. Only return the category name exactly as written.

    Context:
    {CATEGORISATION_CONTEXT.strip()}

    Valid categories:
    {", ".join(VALID_CATEGORIES)}

    Transaction message:
    {message}

    Transaction amount:
    {amount:.2f} EUR
    """

    # === GEMINI API CALL ===
    def ask_gemini(message: str, amount: float) -> str:
        prompt = format_prompt(message, amount)
        print("Prompt for Gemini API:", prompt)
        payload = {
            "contents": [{
                "parts": [{"text": prompt}]
            }]
        }
        headers = {
            "Content-Type": "application/json"
        }
        response = requests.post(ENDPOINT, headers=headers, json=payload)
        if response.status_code == 200:
            try:
                return response.json()["candidates"][0]["content"]["parts"][0]["text"].strip()
            except Exception as e:
                print("Parsing error:", e)
                return "UNKNOWN"
        else:
            print("API error:", response.status_code, response.text)
            return "ERROR"

    # === APPLY TO TRANSACTION DATAFRAME ===
    # Requires your tx_df1 to include 'message' and 'amount_eur'
    def classify_transactions_with_context(tx_df1: pd.DataFrame) -> pd.DataFrame:
        def classify_row(row):
            if pd.notna(row["message"]) or pd.notna(row["amount_eur"]):
                return ask_gemini(row["message"], row["amount_eur"])
            return "UNKNOWN"

        tx_df1["category"] = tx_df1.apply(classify_row, axis=1)
        return tx_df1
    tx_df1 = classify_transactions_with_context(tx_df1)
    print(tx_df1[["date", "amount_eur", "message", "category"]].head(10))
    return tx_df1

def classify_transactions(pdf) -> pd.DataFrame:
    transaction_dataframe = generate_transaction_dataframe(pdf)
    categorized_df = transaction_categorisation(transaction_dataframe)
    return categorized_df
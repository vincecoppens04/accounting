import streamlit as st
from supabase import create_client
import pandas as pd

@st.cache_resource
def get_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

# ---------- Categories ----------

def fetch_categories() -> pd.DataFrame:
    sb = get_client()
    try:
        res = sb.table("accounting_categories").select("name, monthly_budget").order("name").execute()
        if getattr(res, "status_code", 200) == 200 and res.data:
            return pd.DataFrame(res.data)
    except Exception:
        pass
    return pd.DataFrame({"name": ["Income"], "monthly_budget": [0]})

def upsert_categories(df: pd.DataFrame) -> int:
    sb = get_client()
    if df is None or df.empty:
        return 0
    clean = df.copy()
    if "name" not in clean.columns:
        return 0
    clean["name"] = clean["name"].fillna("").astype(str).str.strip()
    if "monthly_budget" in clean.columns:
        clean["monthly_budget"] = pd.to_numeric(clean["monthly_budget"], errors="coerce").fillna(0.0)
    clean = clean[clean["name"] != ""]
    existing_df = fetch_categories()
    existing_set = set(existing_df["name"].astype(str).str.strip()) if not existing_df.empty else set()

    updated = clean[clean["name"].isin(existing_set)].to_dict(orient="records")
    new_rows = clean[~clean["name"].isin(existing_set)].to_dict(orient="records")

    if updated:
        sb.table("accounting_categories").upsert(updated, on_conflict="name").execute()
    if new_rows:
        sb.table("accounting_categories").insert(new_rows).execute()

    return len(updated) + len(new_rows)

def delete_categories(names: list[str]) -> int:
    """Delete categories by name. Returns count attempted (actual deletions may be fewer if FK constraints block)."""
    if not names:
        return 0
    sb = get_client()
    # Supabase supports .in_(column, values)
    res = sb.table("accounting_categories").delete().in_("name", names).execute()
    try:
        return len(res.data) if getattr(res, "data", None) else 0
    except Exception:
        return 0

# ---------- Settings (single row id=1) ----------

def fetch_settings() -> dict:
    sb = get_client()
    res = sb.table("accounting_settings").select("*").eq("id", 1).maybe_single().execute()
    data = res.data or {}
    if not data:
        sb.table("accounting_settings").insert({"id": 1}).execute()
        data = {"id": 1}
    return data

def update_settings(payload: dict):
    sb = get_client()
    sb.table("accounting_settings").upsert({"id": 1, **payload}).execute()

# ---------- Transactions ----------

def insert_transaction(row: dict) -> tuple[bool, object]:
    sb = get_client()
    try:
        res = sb.table("accounting_transactions").insert(row).execute()
        ok = bool(getattr(res, "data", None))
        return ok, getattr(res, "data", None)
    except Exception as e:
        return False, str(e)

def fetch_transactions():
    sb = get_client()
    res = sb.table("accounting_transactions").select("*").order("txn_date").execute()
    return res.data or []

# --- Transaction helpers ---
def upsert_transactions(df: pd.DataFrame) -> tuple[int, int]:
    """Upsert existing rows (with id) and insert new rows (without id). Returns (upserted_or_updated, inserted)."""
    sb = get_client()
    if df is None or df.empty:
        return 0, 0
    clean = df.copy()
    # Normalise keys
    for col in ["txn_date", "time_label", "category", "description", "amount", "is_expense", "currency", "id"]:
        if col not in clean.columns:
            clean[col] = None
    # Ensure time_label from txn_date if missing
    def compute_label(v):
        try:
            import pandas as _pd
            return _pd.to_datetime(v).strftime("%Y-%m") if _pd.notna(v) else None
        except Exception:
            return None
    clean["time_label"] = clean.apply(lambda r: r["time_label"] or compute_label(r["txn_date"]), axis=1)

    # Split existing vs new
    existing = clean[clean["id"].notna()].to_dict(orient="records")
    new_rows = clean[clean["id"].isna()].drop(columns=["id"]).to_dict(orient="records")

    updated = 0
    inserted = 0
    if existing:
        sb.table("accounting_transactions").upsert(existing, on_conflict="id").execute()
        updated = len(existing)
    if new_rows:
        sb.table("accounting_transactions").insert(new_rows).execute()
        inserted = len(new_rows)
    return updated, inserted


def delete_transactions(ids: list[str]) -> int:
    """Delete transactions by uuid id. Returns number deleted."""
    if not ids:
        return 0
    sb = get_client()
    res = sb.table("accounting_transactions").delete().in_("id", ids).execute()
    try:
        return len(res.data) if getattr(res, "data", None) else 0
    except Exception:
        return 0

# ---------- Scanner context ----------

def fetch_scanner_context() -> str:
    settings = fetch_settings()
    return settings.get("scanner_context", "")

def update_scanner_context(new_context: str):
    update_settings({"scanner_context": new_context})
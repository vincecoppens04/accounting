import streamlit as st
from supabase import create_client
import pandas as pd
import os, base64, hashlib, hmac
from dotenv import load_dotenv
load_dotenv()

@st.cache_resource
def get_client():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

def pbkdf2_hash_env(password: str) -> str:
    """Return PBKDF2-HMAC-SHA256 hash using base64 salt from env var SALT_B64."""
    salt_b64 = os.getenv("SALT_B64")
    if not salt_b64:
        raise RuntimeError("SALT_B64 is not configured in environment or secrets.")
    salt = base64.b64decode(salt_b64)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return base64.b64encode(dk).decode("utf-8")

def fetch_member(username: str):
    sb = get_client()
    res = sb.table("authentication").select("username, name, email, is_admin, is_board, password").eq("username", username).maybe_single().execute()
    return res.data if getattr(res, "data", None) else None

def validate_member_credentials(username: str, password: str) -> tuple[str, dict | None]:
    member = fetch_member(username)
    if not member:
        return "invalid", None
    try:
        derived = pbkdf2_hash_env(password)
    except Exception:
        return "invalid", None
    stored = member.get("password")
    if not stored or not hmac.compare_digest(derived, stored):
        return "invalid", None
    if not member.get("is_board", False):
        return "no_priv", member
    return "ok", member

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

def fetch_category_budgets() -> pd.DataFrame:
    """Return DataFrame with columns: name, monthly_budget."""
    try:
        sb = get_client()
        res = sb.table("accounting_categories").select("name, monthly_budget").order("name").execute()
        df = pd.DataFrame(res.data or [])
        if df.empty:
            df = pd.DataFrame({"name": ["Income"], "monthly_budget": [0.0]})
        if "monthly_budget" not in df.columns:
            df["monthly_budget"] = 0.0
        return df
    except Exception:
        return pd.DataFrame({"name": ["Income"], "monthly_budget": [0.0]})

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
    # Keep only real DB columns to avoid PostgREST errors (e.g., original_name from UI)
    allowed_cols = ["name", "monthly_budget"]
    clean = clean[[c for c in allowed_cols if c in clean.columns]]
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
    """Fetch the single settings row (id=1). Creates it if missing.
    Note: We keep only generic app settings here (e.g., fiscal year start).
    Password-related fields are deprecated and unused by the app UI.
    """
    sb = get_client()
    res = sb.table("accounting_settings").select("*").eq("id", 1).maybe_single().execute()
    data = res.data or {}
    if not data:
        sb.table("accounting_settings").insert({"id": 1}).execute()
        data = {"id": 1}
    return data

def update_settings(payload: dict):
    """Upsert settings into the single-row table (id=1)."""
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

# ---------- Members & Amounts Due ----------
import datetime as _dt
from typing import List, Dict, Optional


def _current_username() -> Optional[str]:
    """Best-effort lookup of the logged-in member's username from session state.
    lib.auth.authenticate() typically stores a member dict under one of these keys.
    """
    cand = st.session_state.get("member") or st.session_state.get("user") or {}
    if isinstance(cand, dict) and cand.get("username"):
        return cand.get("username")
    # Fallbacks
    return st.session_state.get("username")


def get_members() -> List[Dict[str, str]]:
    """Return a lightweight member list for dropdowns and future features.
    Each item: { username, name, email }
    """
    sb = get_client()
    res = sb.table("authentication").select("username, name, email").order("name").execute()
    rows = res.data or []
    # Normalise & ensure keys exist
    out: List[Dict[str, str]] = []
    for r in rows:
        out.append({
            "username": (r.get("username") or "").strip(),
            "name": (r.get("name") or r.get("username") or "").strip(),
            "email": (r.get("email") or "").strip(),
        })
    return out


# ---- Amounts Due CRUD ----

def _parse_date(v) -> Optional[_dt.date]:
    if v is None:
        return None
    if isinstance(v, _dt.date) and not isinstance(v, _dt.datetime):
        return v
    if isinstance(v, _dt.datetime):
        return v.date()
    if isinstance(v, str):
        try:
            # Accept 'YYYY-MM-DD' or full ISO
            return _dt.date.fromisoformat(v[:10])
        except Exception:
            return None
    return None


def _parse_datetime(v) -> Optional[_dt.datetime]:
    if v is None:
        return None
    if isinstance(v, _dt.datetime):
        return v
    if isinstance(v, str):
        try:
            v2 = v.replace("Z", "+00:00")
            return _dt.datetime.fromisoformat(v2)
        except Exception:
            return None
    return None


def list_amounts_due() -> List[Dict]:
    """Fetch open amounts, enrich with member_name for UI convenience.
    Returns items with keys: id, member_username, member_name, amount, created_at (datetime), due_date (date), note
    """
    sb = get_client()
    res = sb.table("amounts_due").select("id, member_username, amount, created_at, due_date, note").order("due_date").execute()
    rows = res.data or []
    # Build mapping username -> name
    members = {m["username"]: m.get("name") or m["username"] for m in get_members()}
    out: List[Dict] = []
    for r in rows:
        out.append({
            "id": r.get("id"),
            "member_username": r.get("member_username"),
            "member_name": members.get(r.get("member_username"), r.get("member_username")),
            "amount": float(r.get("amount") or 0.0),
            "created_at": _parse_datetime(r.get("created_at")),
            "due_date": _parse_date(r.get("due_date")),
            "note": r.get("note") or "",
        })
    return out


def create_amount_due(member_username: str, amount: float, due_date: _dt.date, note: Optional[str] = None) -> None:
    """Insert a new amount-due row. The creator is captured from session state."""
    if not member_username:
        raise ValueError("member_username is required")
    try:
        amount = float(amount)
    except Exception:
        raise ValueError("amount must be a number")
    if amount <= 0:
        raise ValueError("amount must be > 0")

    creator = _current_username()
    if not creator:
        raise RuntimeError("No logged-in user found to record 'inserted_by_username'.")

    sb = get_client()
    due = _parse_date(due_date) or (_dt.date.today() + _dt.timedelta(days=7))
    payload = {
        "member_username": member_username,
        "amount": amount,
        # created_at is defaulted by DB; due_date can be overridden here
        "due_date": due.isoformat(),
        "note": (note or "").strip(),
        "inserted_by_username": creator,
    }
    sb.table("amounts_due").insert(payload).execute()


def update_amount_due(id: str, amount: float, due_date: _dt.date, note: Optional[str] = None) -> None:
    if not id:
        raise ValueError("id is required")
    try:
        amount = float(amount)
    except Exception:
        raise ValueError("amount must be a number")
    if amount <= 0:
        raise ValueError("amount must be > 0")

    sb = get_client()
    due = _parse_date(due_date) or (_dt.date.today() + _dt.timedelta(days=7))
    payload = {
        "amount": amount,
        "due_date": due.isoformat(),
        "note": (note or "").strip(),
    }
    sb.table("amounts_due").update(payload).eq("id", id).execute()


def delete_amount_due(id: str) -> None:
    if not id:
        return
    sb = get_client()
    sb.table("amounts_due").delete().eq("id", id).execute()


# ---- Convenience: totals for member banner ----

def fetch_member_due_total(member_username: str) -> float:
    """Return the sum currently due for a member (0.0 if none)."""
    if not member_username:
        return 0.0
    sb = get_client()
    res = sb.rpc(
        "sql",
        params={
            "query": (
                "select coalesce(sum(amount), 0) as total from amounts_due where member_username = %(u)s;",
                {"u": member_username},
            )
        },
    ) if False else None  # keep simple; do it client-side for portability

    # Fallback: compute from list_amounts_due to avoid DB RPC dependency
    total = 0.0
    for r in list_amounts_due():
        if r.get("member_username") == member_username:
            total += float(r.get("amount") or 0.0)
    return float(total)
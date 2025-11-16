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

sb = get_client()

def pbkdf2_hash_env(password: str) -> str:
    """Return PBKDF2-HMAC-SHA256 hash using base64 salt from env var SALT_B64."""
    salt_b64 = os.getenv("SALT_B64")
    if not salt_b64:
        raise RuntimeError("SALT_B64 is not configured in environment or secrets.")
    salt = base64.b64decode(salt_b64)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 200000)
    return base64.b64encode(dk).decode("utf-8")

def fetch_member(username: str):
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
    if not (member.get("is_board", False) or member.get("is_admin", False)):
        return "no_priv", member
    return "ok", member

# ---------- Categories ----------
def fetch_transactions_with_categories(selected_year: str) -> pd.DataFrame:
    rows = fetch_transactions()
    if not rows:
        st.info("No transactions yet.")
        st.stop()

    # fetch transactions and filter on slected year
    transaction_df = pd.DataFrame(rows)
    transaction_df = transaction_df[transaction_df["year_label"] == selected_year]

    categories_df = fetch_categories_df(selected_year)

    # Join category names into the transactions dataframe
    if not categories_df.empty and "budget_category_id" in transaction_df.columns:
        full_df = transaction_df.merge(
            categories_df[["id", "category_name"]],
            how="left",
            left_on="budget_category_id",
            right_on="id",
            suffixes=("", "_cat"),
        )
        full_df["category"] = full_df["category_name"].fillna("Uncategorized")
        full_df = full_df.drop(columns=["id_cat", "category_name"])
    else:
        full_df = transaction_df.copy()
        full_df["category"] = "Uncategorized"
    return full_df

def fetch_categories(year_label: str | None = None) -> list[str]:
    """Return a list of category names from accounting_budget.

    If year_label is provided, only categories for that year are returned.
    """
    try:
        query = sb.table("accounting_budget").select("category_name, year_label")
        if year_label:
            query = query.eq("year_label", year_label)
        res = query.order("category_name").execute()
        rows = res.data or []
        names = sorted({(r.get("category_name") or "").strip() for r in rows if r.get("category_name")})
        return names
    except Exception:
        return ["Income"]

def fetch_categories_df(year_label: str | None = None) -> pd.DataFrame:
    """Return a DataFrame of categories from accounting_budget.

    If year_label is provided, only categories for that year are returned.
    Columns: name, monthly_budget (if available)
    """
    try:
        query = sb.table("accounting_budget").select("category_name, budget, year_label, id")
        if year_label:
            query = query.eq("year_label", year_label)
        res = query.order("category_name").execute()
        df = pd.DataFrame(res.data or [])
        if df.empty:
            pass
        else:
            return df
    except Exception:
        return pd.DataFrame({"name": ["Income"], "monthly_budget": [0.0]})


# ---- Helper to get budget category id ----
def get_budget_category_id(year_label: str, category_name: str) -> str | None:
    """Return accounting_budget.id for the given year and category name, or None if not found."""
    if not year_label or not category_name:
        return None
    res = (
        sb.table("accounting_budget")
        .select("id")
        .eq("year_label", year_label)
        .eq("category_name", category_name)
        .maybe_single()
        .execute()
    )
    data = getattr(res, "data", None) or {}
    return data.get("id")

# ---------- Budget (new logic) ----------

# NOTE: New budgeting system uses two tables:
# - accounting_budget_years (id, year_label, opening_cash, sort_order, created_at)
# - accounting_budget        (id, year_label, category_name, budget_type, budget, created_at)
# Categories are implicit: each row in accounting_budget *is* a category+amount.

# ---- Budget years ----

def fetch_budget_years_df() -> pd.DataFrame:
    """Return all budget years as a DataFrame sorted by sort_order then year_label.
    Expected columns in DB: year_label, opening_cash, sort_order.
    """
    try:
        res = (
            sb.table("accounting_budget_years")
            .select("id, year_label, opening_cash, sort_order, created_at")
            .order("sort_order")
            .order("year_label")
            .execute()
        )
        df = pd.DataFrame(res.data or [])
        if df.empty:
            return pd.DataFrame(columns=["id", "year_label", "opening_cash", "sort_order", "created_at"])
        return df
    except Exception:
        # Fail soft: return empty frame so UI can handle no years
        return pd.DataFrame(columns=["id", "year_label", "opening_cash", "sort_order", "created_at"])


def fetch_budget_year_labels() -> list[str]:
    """Return list of year_label values, sorted for use in dropdowns."""
    df = fetch_budget_years_df()
    if df.empty or "year_label" not in df.columns:
        return []
    return [""] + df["year_label"].astype(str).tolist()


def get_opening_cash(year_label: str) -> float:
    """Return opening_cash for a given year_label (0.0 if missing)."""
    if not year_label:
        return 0.0
    try:
        res = (
            sb.table("accounting_budget_years")
            .select("opening_cash")
            .eq("year_label", year_label)
            .maybe_single()
            .execute()
        )
        data = getattr(res, "data", None) or {}
        return float(data.get("opening_cash", 0.0))
    except Exception:
        return 0.0


def update_opening_cash(year_label: str, amount: float) -> None:
    """Update opening_cash for a given year_label. No-op if year_label is empty.
    Assumes the row already exists in accounting_budget_years.
    """
    if not year_label:
        return
    try:
        amount_val = float(amount)
    except Exception:
        amount_val = 0.0
    sb.table("accounting_budget_years").update({"opening_cash": amount_val}).eq("year_label", year_label).execute()


# ---- Budget entries (categories + amounts) ----

# We treat each row in accounting_budget as a category for a given year and type.
# Fields used: year_label, category_name, budget_type, budget.


def fetch_budget_entries(year_label: str) -> pd.DataFrame:
    """Return all budget entries for a given year_label.
    Columns: id, year_label, category_name, budget_type, budget.
    """
    if not year_label:
        return pd.DataFrame(columns=["id", "year_label", "category_name", "budget_type", "budget"])
    try:
        res = (
            sb.table("accounting_budget")
            .select("id, year_label, category_name, budget_type, budget")
            .eq("year_label", year_label)
            .order("category_name")
            .order("budget_type")
            .execute()
        )
        df = pd.DataFrame(res.data or [])
        if df.empty:
            return pd.DataFrame(columns=["id", "year_label", "category_name", "budget_type", "budget"])
        # Normalise types
        if "budget" in df.columns:
            df["budget"] = pd.to_numeric(df["budget"], errors="coerce").fillna(0.0)
        return df
    except Exception:
        return pd.DataFrame(columns=["id", "year_label", "category_name", "budget_type", "budget"])


def fetch_budget_entries_for_type(year_label: str, budget_type: str) -> pd.DataFrame:
    """Return budget entries filtered by year and budget_type."""
    df = fetch_budget_entries(year_label)
    if df.empty:
        return df
    if "budget_type" not in df.columns:
        return df
    return df[df["budget_type"] == budget_type].reset_index(drop=True)


def add_budget_category(year_label: str, name: str, budget_type: str, budget: float = 0.0) -> None:
    """Create a new accounting_budget row for (year, category, type).
    Duplicate protection is delegated to the DB unique constraint.
    """
    if not year_label or not name:
        return
    try:
        budget_val = float(budget)
    except Exception:
        budget_val = 0.0
    payload = {
        "year_label": year_label,
        "category_name": name.strip(),
        "budget_type": budget_type,
        "budget": budget_val,
    }
    sb.table("accounting_budget").insert(payload).execute()


def delete_budget_category(year_label: str, name: str, budget_type: str | None = None) -> None:
    """Delete budget rows for a given category.
    If budget_type is None, deletes all types for that (year, name).
    """
    if not year_label or not name:
        return
    q = sb.table("accounting_budget").delete().eq("year_label", year_label).eq("category_name", name)
    if budget_type:
        q = q.eq("budget_type", budget_type)
    q.execute()


# ---- Simplified single function to update name, type, and budget in one step ----
def update_budget_category(year_label: str, old_name: str, new_name: str, old_type: str, new_type: str, amount: float) -> None:
    """Simplified single function to update name, type, and budget in one step."""
    if not year_label or not old_name or not new_name or not old_type or not new_type:
        return
    try:
        amount_val = float(amount)
    except Exception:
        amount_val = 0.0

    # 1. Update name if changed
    if new_name != old_name:
        sb.table("accounting_budget").update({"category_name": new_name}).eq("year_label", year_label).eq("category_name", old_name).execute()
        target_name = new_name
    else:
        target_name = old_name

    # 2. Update type if changed
    if new_type != old_type:
        sb.table("accounting_budget").update({"budget_type": new_type}).eq("year_label", year_label).eq("category_name", target_name).eq("budget_type", old_type).execute()
        target_type = new_type
    else:
        target_type = old_type

    # 3. Always update the amount
    sb.table("accounting_budget").update({"budget": amount_val}).eq("year_label", year_label).eq("category_name", target_name).eq("budget_type", target_type).execute()

# ---------- Settings (single row id=1) ----------
def fetch_settings() -> dict:
    """Fetch the single settings row (id=1). Creates it if missing.
    Note: We keep only generic app settings here (e.g., fiscal year start).
    Password-related fields are deprecated and unused by the app UI.
    """
    res = sb.table("accounting_settings").select("*").eq("id", 1).maybe_single().execute()
    data = res.data or {}
    if not data:
        sb.table("accounting_settings").insert({"id": 1}).execute()
        data = {"id": 1}
    return data

def update_settings(payload: dict):
    """Upsert settings into the single-row table (id=1)."""
    sb.table("accounting_settings").upsert({"id": 1, **payload}).execute()

# ---------- Transactions ----------

def insert_transaction(row: dict) -> tuple[bool, object]:
    """Insert a transaction row as-is into accounting_transactions."""
    try:
        res = sb.table("accounting_transactions").insert(row).execute()
        ok = bool(getattr(res, "data", None))
        return ok, getattr(res, "data", None)
    except Exception as e:
        return False, str(e)

# DASHBOARD
def fetch_transactions():
    res = sb.table("accounting_transactions").select("*").order("txn_date").execute()
    return res.data or []


# --- Transaction helpers ---
def upsert_transactions(df: pd.DataFrame) -> tuple[int, int]:
    """Upsert existing rows (with id) and insert new rows (without id). Returns (upserted_or_updated, inserted)."""
    if df is None or df.empty:
        return 0, 0
    clean = df.copy()
    # Ensure txn_date is a JSON-serialisable ISO string
    if "txn_date" in clean.columns:
        import pandas as _pd

        def _norm_date(v):
            try:
                if v is None or (isinstance(v, float) and _pd.isna(v)):
                    return None
                return _pd.to_datetime(v).strftime("%Y-%m-%d")
            except Exception:
                return None

        clean["txn_date"] = clean["txn_date"].apply(_norm_date)
    # Normalise keys
    for col in ["txn_date", "time_label", "category", "description", "amount", "is_expense", "currency", "id"]:
        if col not in clean.columns:
            clean[col] = None
    
def delete_transactions(ids: list[str]) -> int:
    """Delete transactions by uuid id. Returns number deleted."""
    if not ids:
        return 0
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
    sb.table("amounts_due").delete().eq("id", id).execute()
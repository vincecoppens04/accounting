import pandas as pd
from lib.db import (
    fetch_budget_entries,
    get_opening_cash,
    get_savings,
    load_working_capital,
    fetch_transactions_with_categories
)

def calculate_budget_metrics(year_label: str) -> dict:
    """
    Calculate budget metrics for a given year.
    Returns a dictionary with:
    - opening_cash
    - total_income
    - total_expenses_sem1
    - total_expenses_sem2
    - total_expenses_year
    - total_expenses_all
    - savings
    - free_float
    """
    if not year_label:
        return {
            "opening_cash": 0.0,
            "total_income": 0.0,
            "total_expenses_sem1": 0.0,
            "total_expenses_sem2": 0.0,
            "total_expenses_year": 0.0,
            "total_expenses_all": 0.0,
            "savings": 0.0,
            "free_float": 0.0,
        }

    # 1. Fetch data
    opening_cash = get_opening_cash(year_label)
    savings = get_savings(year_label)
    entries = fetch_budget_entries(year_label)

    # 2. Calculate totals from entries
    if entries.empty:
        total_income = 0.0
        sem1 = 0.0
        sem2 = 0.0
        year_exp = 0.0
    else:
        # Ensure budget column is numeric
        entries["budget"] = pd.to_numeric(entries["budget"], errors="coerce").fillna(0.0)
        
        total_income = entries[entries["budget_type"] == "income"]["budget"].sum()
        sem1 = entries[entries["budget_type"] == "semester1"]["budget"].sum()
        sem2 = entries[entries["budget_type"] == "semester2"]["budget"].sum()
        year_exp = entries[entries["budget_type"] == "year"]["budget"].sum()

    total_expenses_all = sem1 + sem2 + year_exp

    # 3. Calculate Free Float
    # Free float = Opening + Income - All Expenses - Savings
    free_float = opening_cash + total_income - total_expenses_all - savings

    return {
        "opening_cash": opening_cash,
        "total_income": total_income,
        "total_expenses_sem1": sem1,
        "total_expenses_sem2": sem2,
        "total_expenses_year": year_exp,
        "total_expenses_all": total_expenses_all,
        "savings": savings,
        "free_float": free_float,
    }


def calculate_working_capital_metrics(year_label: str) -> dict:
    """
    Calculate working capital metrics for a given year.
    Returns a dictionary with:
    - total_ar
    - total_ar_member
    - total_ar_sponsor
    - total_ar_other
    - total_ap
    - total_inventory
    - nwc
    """
    # 1. Fetch AR data
    ar_df = load_working_capital(book_year_label=year_label, kind="AR")
    if ar_df.empty:
        total_ar = 0.0
        ar_member = 0.0
        ar_sponsor = 0.0
        ar_other = 0.0
    else:
        ar_df["amount"] = pd.to_numeric(ar_df["amount"], errors="coerce").fillna(0.0)
        total_ar = ar_df["amount"].sum()
        
        # Breakdown
        if "kind_detail" in ar_df.columns:
            ar_member = ar_df[ar_df["kind_detail"] == "Member"]["amount"].sum()
            ar_sponsor = ar_df[ar_df["kind_detail"] == "Sponsor"]["amount"].sum()
            ar_other = ar_df[ar_df["kind_detail"] == "Other"]["amount"].sum()
        else:
            ar_member = 0.0
            ar_sponsor = 0.0
            ar_other = 0.0

    # 2. Fetch AP data
    ap_df = load_working_capital(book_year_label=year_label, kind="AP")
    if ap_df.empty:
        total_ap = 0.0
    else:
        ap_df["amount"] = pd.to_numeric(ap_df["amount"], errors="coerce").fillna(0.0)
        total_ap = ap_df["amount"].sum()

    # 3. Fetch Inventory data (independent of year)
    inv_df = load_working_capital(kind="INVENTORY")
    if inv_df.empty:
        total_inventory = 0.0
    else:
        inv_df["amount"] = pd.to_numeric(inv_df["amount"], errors="coerce").fillna(0.0)
        total_inventory = inv_df["amount"].sum()

    # 4. Calculate NWC
    nwc = total_ar + total_inventory - total_ap

    return {
        "total_ar": total_ar,
        "total_ar_member": ar_member,
        "total_ar_sponsor": ar_sponsor,
        "total_ar_other": ar_other,
        "total_ap": total_ap,
        "total_inventory": total_inventory,
        "nwc": nwc,
    }


def calculate_dashboard_data(year_label: str, period_filter: str) -> pd.DataFrame:
    """
    Prepare data for the dashboard based on the selected period.
    period_filter options: "Everything", "Sem 1", "Sem 2", "Year Expenses"
    Returns a DataFrame with columns: category, budget, net_spending, remaining, budget_type
    """
    # 1. Fetch Budget Entries
    budget_df = fetch_budget_entries(year_label)
    if budget_df.empty:
        return pd.DataFrame(columns=["category", "budget", "net_spending", "remaining", "budget_type"])

    # 2. Filter Budget Entries
    # We focus on expenses for this view as requested ("net spending", "budget")
    # "Everything" implies all expense types.
    if period_filter == "Sem 1":
        budget_df = budget_df[budget_df["budget_type"] == "semester1"]
    elif period_filter == "Sem 2":
        budget_df = budget_df[budget_df["budget_type"] == "semester2"]
    elif period_filter == "Year Expenses":
        budget_df = budget_df[budget_df["budget_type"] == "year"]
    else: # "Everything"
        budget_df = budget_df[budget_df["budget_type"].isin(["semester1", "semester2", "year"])]
    
    if budget_df.empty:
        return pd.DataFrame(columns=["category", "budget", "net_spending", "remaining", "budget_type"])

    # 3. Fetch Transactions
    txn_df = fetch_transactions_with_categories(year_label)
    
    # 4. Calculate Net Spending per Category
    # Net spending = Expense - Income (for a given category)
    # If txn_df is empty, spending is 0
    if txn_df.empty:
        spending_series = pd.Series(dtype=float)
    else:
        # Ensure numeric
        txn_df["amount"] = pd.to_numeric(txn_df["amount"], errors="coerce").fillna(0.0)
        
        # Calculate signed amount: Expense is positive spending, Income is negative spending (reimbursement)
        # Wait, usually for budget tracking:
        # If I budgeted 100 for "Food", and I spent 50, remaining is 50.
        # If I got a refund of 10, net spending is 40.
        # So: if is_expense=True -> +amount, if is_expense=False -> -amount
        txn_df["net_amount"] = txn_df.apply(
            lambda r: r["amount"] if r["is_expense"] else -r["amount"], axis=1
        )
        spending_series = txn_df.groupby("category")["net_amount"].sum()

    # 5. Merge
    # We merge on 'category_name' from budget_df and index 'category' from spending_series
    merged = budget_df.merge(
        spending_series.rename("net_spending"),
        left_on="category_name",
        right_index=True,
        how="left"
    )
    merged["net_spending"] = merged["net_spending"].fillna(0.0)
    merged["budget"] = pd.to_numeric(merged["budget"], errors="coerce").fillna(0.0)
    
    # 6. Calculate Remaining
    merged["remaining"] = merged["budget"] - merged["net_spending"]
    
    # Rename for clarity
    merged = merged.rename(columns={"category_name": "category"})
    
    return merged[["category", "budget", "net_spending", "remaining", "budget_type"]]


def calculate_cash_flow_evolution(year_label: str) -> pd.DataFrame:
    """
    Calculate the daily cash flow evolution for the given year.
    Returns a DataFrame with 'date' and 'balance'.
    """
    # 1. Fetch Opening Cash
    opening_cash = get_opening_cash(year_label)
    
    # 2. Fetch Transactions
    txn_df = fetch_transactions_with_categories(year_label)
    
    if txn_df.empty:
        # Return just the opening balance today (or start of year if we knew it)
        # For simplicity, let's just return a single point
        return pd.DataFrame({"date": [pd.Timestamp.now().date()], "balance": [opening_cash]})
    
    # 3. Process Transactions
    # Ensure date is datetime
    txn_df["txn_date"] = pd.to_datetime(txn_df["txn_date"])
    
    # Calculate net amount for each transaction
    # Income is positive for cash flow, Expense is negative
    # Wait, in the DB: is_expense=True means money out (-), is_expense=False means money in (+)
    txn_df["amount"] = pd.to_numeric(txn_df["amount"], errors="coerce").fillna(0.0)
    txn_df["flow"] = txn_df.apply(lambda r: -r["amount"] if r["is_expense"] else r["amount"], axis=1)
    
    # Group by date to handle multiple transactions per day
    daily_flow = txn_df.groupby("txn_date")["flow"].sum().sort_index().reset_index()
    
    # 4. Calculate Cumulative Sum
    # We need to start with opening cash.
    # Let's create a starting row if the first transaction is after the "start" of the year?
    # Or just assume the cumulative sum starts adding to opening cash.
    
    daily_flow["cumulative_flow"] = daily_flow["flow"].cumsum()
    daily_flow["balance"] = opening_cash + daily_flow["cumulative_flow"]
    
    # Add the starting point (before first transaction) if desired, but for now just the evolution
    # To make it look nice, maybe add a row for "Start" with opening cash?
    # Let's just return the daily balances.
    
    return daily_flow[["txn_date", "balance"]].rename(columns={"txn_date": "date"})


def calculate_current_cash_position(year_label: str) -> float:
    """
    Calculate the current cash position based on the latest balance from cash flow evolution.
    Returns the most recent balance value.
    """
    cash_flow_df = calculate_cash_flow_evolution(year_label)
    
    if cash_flow_df.empty:
        return get_opening_cash(year_label)
    
    # Return the most recent balance
    return float(cash_flow_df.iloc[-1]["balance"])


def calculate_cash_position_with_nwc(year_label: str) -> float:
    """
    Calculate cash position with NWC.
    Formula: Current Cash Position + NWC
    """
    current_cash = calculate_current_cash_position(year_label)
    wc_metrics = calculate_working_capital_metrics(year_label)
    
    return current_cash + wc_metrics["nwc"]

import pandas as pd
import io
from lib.db import (
    fetch_budget_entries,
    fetch_transactions_with_categories,
    load_working_capital
)
from lib.backend_calculations import (
    calculate_budget_metrics,
    calculate_cash_metrics,
    calculate_working_capital_metrics
)

def generate_excel_export(year_label: str) -> io.BytesIO:
    """
    Generate an Excel file with financial data for the given year.
    Returns a BytesIO object containing the Excel file.
    """
    output = io.BytesIO()
    
    # Use xlsxwriter engine for better formatting options if needed, 
    # but default is fine. We'll try to use 'xlsxwriter' explicitly if available,
    # otherwise pandas defaults.
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        
        # --- 1. Metrics Tab ---
        # Gather metrics
        b_metrics = calculate_budget_metrics(year_label)
        c_metrics = calculate_cash_metrics(year_label)
        wc_metrics = calculate_working_capital_metrics(year_label)
        
        metrics_data = [
            {"Category": "Budget", "Metric": "Opening Cash", "Value": b_metrics.get("opening_cash")},
            {"Category": "Budget", "Metric": "Total Income (Projected)", "Value": b_metrics.get("total_income")},
            {"Category": "Budget", "Metric": "Total Expenses (Budgeted)", "Value": b_metrics.get("total_expenses_all")},
            {"Category": "Budget", "Metric": "Savings Goal", "Value": b_metrics.get("savings")},
            {"Category": "Budget", "Metric": "Free Float", "Value": b_metrics.get("free_float")},
            {"Category": "Cash", "Metric": "Begin Cash Position", "Value": c_metrics.get("begin_cash")},
            {"Category": "Cash", "Metric": "Total Income (Txn)", "Value": c_metrics.get("total_income_txn")},
            {"Category": "Cash", "Metric": "Total Expenses (Txn)", "Value": c_metrics.get("total_expenses_txn")},
            {"Category": "Cash", "Metric": "Current Cash Position", "Value": c_metrics.get("current_cash")},
            {"Category": "Cash", "Metric": "Cash Position with NWC", "Value": c_metrics.get("cash_with_nwc")},
            {"Category": "Working Capital", "Metric": "NWC", "Value": wc_metrics.get("nwc")},
            {"Category": "Working Capital", "Metric": "Total AR", "Value": wc_metrics.get("total_ar")},
            {"Category": "Working Capital", "Metric": "Total AP", "Value": wc_metrics.get("total_ap")},
            {"Category": "Working Capital", "Metric": "Total Inventory", "Value": wc_metrics.get("total_inventory")},
        ]
        metrics_df = pd.DataFrame(metrics_data)
        metrics_df.to_excel(writer, sheet_name="Metrics", index=False)
        
        # --- 2. Budget Tab ---
        budget_df = fetch_budget_entries(year_label)
        if budget_df.empty:
            budget_df = pd.DataFrame(columns=["category_name", "budget", "budget_type", "year_label"])
        budget_df.to_excel(writer, sheet_name="Budget", index=False)
        
        # --- 3. Transactions Tab ---
        txn_df = fetch_transactions_with_categories(year_label)
        if txn_df.empty:
            txn_df = pd.DataFrame(columns=["id", "txn_date", "category", "description", "amount", "is_expense", "year_label"])
        txn_df.to_excel(writer, sheet_name="Transactions", index=False)
        
        # --- 4. AR Tab ---
        ar_df = load_working_capital(book_year_label=year_label, kind="AR")
        if ar_df.empty:
            ar_df = pd.DataFrame(columns=["id", "member_username", "amount", "due_date", "note", "kind", "kind_detail", "status", "year_label"])
        ar_df.to_excel(writer, sheet_name="AR", index=False)
        
        # --- 5. AP Tab ---
        ap_df = load_working_capital(book_year_label=year_label, kind="AP")
        if ap_df.empty:
            ap_df = pd.DataFrame(columns=["id", "member_username", "amount", "due_date", "note", "kind", "kind_detail", "status", "year_label"])
        ap_df.to_excel(writer, sheet_name="AP", index=False)
        
        # --- 6. Inventory Tab ---
        # Inventory is usually global, but we can check if it filters by year in load_working_capital. 
        # The function signature suggests it can take year, but usually inventory is a snapshot.
        # Based on previous usage: load_working_capital(kind="INVENTORY") without year.
        inv_df = load_working_capital(kind="INVENTORY")
        if inv_df.empty:
            inv_df = pd.DataFrame(columns=["id", "member_username", "amount", "due_date", "note", "kind", "kind_detail", "status", "year_label"])
        inv_df.to_excel(writer, sheet_name="Inventory", index=False)
        
    output.seek(0)
    return output

import streamlit as st
from lib.auth import authenticate, logout
authenticate()

st.set_page_config(page_title="Investia – Finance", page_icon="💷", layout="wide")

st.title("Investia Finance Management System")
st.markdown("### Welcome to your comprehensive financial management platform")

st.markdown("""
This application provides a complete suite of tools for managing Investia's finances, including budget tracking, 
transaction management, working capital monitoring, and automated bank statement processing.
""")

st.divider()

# Overview section
st.markdown("## Application Overview")
st.markdown("""
The Investia Finance Management System is designed to streamline all aspects of financial administration for your organization. 
Navigate through the different pages using the sidebar to access various features.
""")

st.divider()

# Feature descriptions
st.markdown("## Key Features")

# Dashboard
with st.expander("Dashboard - Financial Overview at a Glance", expanded=True):
    st.markdown("""
    The Dashboard provides a comprehensive overview of your financial health:
    
    **Key Metrics Display:**
    - **Total Income**: View all income for the selected budget year
    - **Total Expenses**: See expenses broken down by Semester 1, Semester 2, and Year expenses
    - **Net Working Capital (NWC)**: Monitor your working capital with breakdowns for Accounts Receivable (AR), Accounts Payable (AP), and Inventory
    - **Savings**: Track funds designated to remain in the account
    - **Free Float**: Calculate available funds after accounting for all commitments
    
    **Budget vs Spending Analysis:**
    - Interactive bullet charts showing spending against budget by category
    - Filter by period: Everything, Semester 1, Semester 2, or Year Expenses
    - Detailed budget table with color-coded remaining amounts (green for under budget, red for over budget)
    
    **Cash Flow Evolution:**
    - Visual line chart tracking your balance over time
    - See how transactions impact your financial position throughout the year
    """)

# Transactions
with st.expander("Transactions - Manage All Financial Transactions"):
    st.markdown("""
    View, edit, and manage all your financial transactions in one place:
    
    **Features:**
    - **Comprehensive Transaction List**: See all transactions for the selected budget year
    - **Advanced Filtering**: Filter by month and category to find specific transactions
    - **Direct Editing**: Edit transaction details directly in the table (date, description, amount, type)
    - **Bulk Operations**: Delete multiple transactions at once
    - **Category Display**: View the budget category associated with each transaction
    
    **Note**: To change a transaction's category, delete it and re-insert it with the correct category using the Insert Transaction page.
    """)

# Insert Manually
with st.expander("Insert Transaction - Add Transactions Manually"):
    st.markdown("""
    Quickly add individual transactions to your financial records:
    
    **Input Fields:**
    - **Date**: Select the transaction date
    - **Budget Year**: Choose the applicable budget year
    - **Category**: Select from available budget categories
    - **Description**: Add details about the transaction
    - **Amount**: Enter the transaction amount in EUR
    - **Type**: Specify whether it's an Expense or Income
    
    Perfect for one-off entries or when you need to manually record a transaction.
    """)

# Scanner
with st.expander("Bank Statement Scanner - Automated Transaction Import"):
    st.markdown("""
    Leverage AI to automatically extract and classify transactions from your KBC bank statements:
    
    **How It Works:**
    1. **Upload PDF**: Upload your KBC PDF bank statement
    2. **AI Classification**: The system uses AI to extract transaction data and suggest categories
    3. **Review & Edit**: Review each transaction, adjust categories and details as needed
    4. **Batch Save**: Save all transactions with a single click
    
    **Context Management:**
    - Customize the AI classification context to improve accuracy
    - Save context settings for consistent classification across statements
    - The system learns from your category structure to make better suggestions
    
    This feature dramatically reduces manual data entry time and minimizes errors.
    """)

# Budget
with st.expander("Budget - Plan and Track Your Budget"):
    st.markdown("""
    Create and manage your annual budget with detailed category tracking:
    
    **Budget Overview:**
    - **Cash Position**: Set and track opening cash balance
    - **Total Income**: Monitor all income categories
    - **Total Expenses**: View expenses across all periods (Semester 1, Semester 2, Year)
    - **Savings**: Define funds to keep in reserve
    - **Free Float**: See available funds after all allocations
    
    **Category Management:**
    - **Add Categories**: Create new budget categories for different expense/income types
    - **Category Types**: Organize by Income, Year, Semester 1, or Semester 2
    - **Edit Categories**: Update category names, types, and budgeted amounts
    - **Delete Categories**: Remove unused categories (only if no transactions are linked)
    
    **Budget Configuration:**
    - Set opening cash position for each budget year
    - Define savings targets
    - View all categories organized by type (Income, Full Year, Semester 1, Semester 2)
    """)

# Working Capital
with st.expander("Working Capital - Manage AR, AP, and Inventory"):
    st.markdown("""
    Track and manage your working capital components with precision:
    
    **Key Metrics:**
    - **Total Accounts Receivable (AR)**: Track money owed to you, broken down by Member, Sponsor, and Other
    - **Total Accounts Payable (AP)**: Monitor outstanding payments you need to make
    - **Total Inventory**: Manage physical inventory value and quantities
    - **Net Working Capital (NWC)**: Calculated as AR + Inventory - AP
    
    **Accounts Receivable Management:**
    - Add new receivables for Members, Sponsors, or Other parties
    - **Member Integration**: Select from registered members and automatically send email notifications
    - **Email Notifications**: Notify members of amounts due with detailed descriptions
    - **Send Reminders**: Resend payment reminders to members with a single click
    - Track category, amount, date, and description for each receivable
    - Mark receivables as fulfilled when paid
    - Edit existing receivables (amount, date, category, description)
    
    **Accounts Payable Management:**
    - Record bills and payments you owe
    - Track by category, amount, and due date
    - Mark as fulfilled when paid
    - Edit existing payables
    
    **Inventory Management:**
    - Maintain a live inventory list
    - Track description, value, and number of pieces
    - Add, edit, or remove inventory items
    - Dynamic table editing with automatic save
    - **Note**: Inventory is independent of budget year
    
    **Email Integration:**
    - Automatic email notifications to members for new amounts due
    - Polite, professional email templates with all relevant details
    - One-click reminder emails for outstanding amounts
    """)

# Settings
with st.expander("Settings - Configure System Preferences"):
    st.markdown("""
    Customize system settings to match your organization's needs:
    
    **Financial Year Configuration:**
    - Set the start month and day of your financial year
    - Default follows Investia statutes (October 1st)
    - Affects reporting and year-based calculations
    
    **Account Management:**
    - Logout option for secure session management
    """)

st.divider()

# How to get started
st.markdown("## Getting Started")
st.markdown("""
1. **Set Up Your Budget**: Go to the Budget page and create your budget categories and set your opening cash position
2. **Configure Settings**: Visit Settings to set your financial year start date
3. **Add Transactions**: Use the Scanner for bulk imports or Insert Transaction for manual entries
4. **Monitor Performance**: Check the Dashboard regularly to track spending vs budget
5. **Manage Working Capital**: Keep track of receivables, payables, and inventory in the Working Capital page
6. **Review Transactions**: Use the Transactions page to audit and edit your financial records
""")

st.divider()

# Technical details
st.markdown("## Technical Details")
col1, col2 = st.columns(2)

with col1:
    st.markdown("""
    **Data Storage:**
    - All data securely stored in Supabase
    - Real-time synchronization
    - Automatic backups
    """)

with col2:
    st.markdown("""
    **Security:**
    - User authentication required
    - Secure session management
    - Role-based access control
    """)

st.divider()

st.markdown("## Navigation")
st.info("👈 Use the sidebar navigation to access different pages and start managing your finances!")

if st.session_state.get("authenticated"):
    st.divider()
    if st.button("🚪 Logout"):
        logout()

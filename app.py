import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date
from io import BytesIO

# ---------------- Google Sheets Credentials ----------------
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

# Make a copy of secrets and fix the private key newlines
creds_dict = dict(st.secrets["google_credentials"])
creds_dict["private_key"] = creds_dict["private_key"].replace("\\n", "\n")

creds = Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
client = gspread.authorize(creds)

SHEET_NAME = "Expense Tracker App"

# ---------------- Open or Create Spreadsheet ----------------
try:
    sheet = client.open(SHEET_NAME)
except gspread.SpreadsheetNotFound:
    sheet = client.create(SHEET_NAME)
    sheet.share(creds.service_account_email, perm_type="user", role="writer")

# ---------------- Ensure Tabs Exist ----------------
def get_or_create_worksheet(name, headers):
    try:
        ws = sheet.worksheet(name)
    except gspread.WorksheetNotFound:
        ws = sheet.add_worksheet(title=name, rows="100", cols=str(len(headers)))
        ws.append_row(headers)
    return ws

expenses_ws = get_or_create_worksheet("Expenses", ["Date", "Amount", "Category", "Notes", "Month"])
medicines_ws = get_or_create_worksheet("Medicines", ["Date", "Medicine", "Quantity", "Cost", "Notes"])
investments_ws = get_or_create_worksheet("Investments", ["Date", "Type", "Amount", "Frequency", "Notes"])
expense_cat_ws = get_or_create_worksheet("ExpenseCategories", ["Category"])
investment_cat_ws = get_or_create_worksheet("InvestmentCategories", ["Type"])

# ---------------- Helper Functions ----------------
def ws_to_df(ws):
    data = ws.get_all_records()
    return pd.DataFrame(data)

def df_to_ws(df, ws):
    ws.clear()
    ws.append_row(df.columns.tolist())
    ws.append_rows(df.values.tolist())

def load_expense_categories():
    df = ws_to_df(expense_cat_ws)
    if df.empty:
        default = ["Food", "Transport", "Shopping", "Donation", "Bills", "Other"]
        expense_cat_ws.append_rows([[c] for c in default])
        return default
    return df["Category"].tolist()

def load_investment_categories():
    df = ws_to_df(investment_cat_ws)
    if df.empty:
        default = ["Salary", "SIP", "FD", "Stocks", "Chit Fund", "Other"]
        investment_cat_ws.append_rows([[c] for c in default])
        return default
    return df["Type"].tolist()

def download_all_data():
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        ws_to_df(expenses_ws).to_excel(writer, sheet_name="Expenses", index=False)
        ws_to_df(medicines_ws).to_excel(writer, sheet_name="Medicines", index=False)
        ws_to_df(investments_ws).to_excel(writer, sheet_name="Investments", index=False)
    buffer.seek(0)
    return buffer

def show_table_with_actions(df, ws):
    if df.empty:
        st.info("No records yet.")
        return

    for i, row in df.iterrows():
        cols = st.columns([2, 2, 2, 3, 2])
        for j, val in enumerate(row.values):
            cols[j].write(val)

        if cols[3].button("✏️ Edit", key=f"edit_{i}"):
            with st.form(f"edit_form_{i}"):
                new_values = []
                for col_name, value in row.items():
                    new_val = st.text_input(col_name, str(value))
                    new_values.append(new_val)
                submit_edit = st.form_submit_button("Save")
                if submit_edit:
                    df.loc[i] = new_values
                    df_to_ws(df, ws)
                    st.success("✅ Row updated successfully!")
                    st.rerun()

        if cols[4].button("🗑 Delete", key=f"delete_{i}"):
            df = df.drop(index=i).reset_index(drop=True)
            df_to_ws(df, ws)
            st.success("✅ Row deleted successfully!")
            st.rerun()

# ---------------- Sidebar ----------------
st.sidebar.title("📂 Menu")
menu = st.sidebar.radio("Go to:", ["💸 Expenses", "💊 Medicines", "💰 Investments"])

st.sidebar.header("📥 Backup Data")
if st.sidebar.button("Download Excel Backup"):
    st.sidebar.download_button(
        "Download File",
        download_all_data(),
        "expense_tracker_backup.xlsx"
    )

# ---------------- Expenses Tab ----------------
if menu == "💸 Expenses":
    st.title("💸 Expense Tracker")
    expense_categories = load_expense_categories()
    category = st.selectbox("Category", expense_categories)

    new_cat = st.text_input("➕ Add New Category")
    if st.button("Add Category"):
        if new_cat.strip() and new_cat not in expense_categories:
            expense_cat_ws.append_row([new_cat])
            st.success("✅ Category added!")
            st.rerun()

    with st.form("expense_form"):
        exp_date = st.date_input("Date", value=date.today())
        amount = st.number_input("Amount (₹)", min_value=0.0, step=10.0)
        notes = st.text_input("Notes (optional)")
        submit = st.form_submit_button("Add Expense")

    if submit and amount > 0:
        df = ws_to_df(expenses_ws)
        new_row = [str(exp_date), amount, category, notes, exp_date.strftime("%B %Y")]
        df.loc[len(df)] = new_row
        df_to_ws(df, expenses_ws)
        st.success("✅ Expense added successfully!")

    st.header("📊 Expenses Table")
    show_table_with_actions(ws_to_df(expenses_ws), expenses_ws)

# ---------------- Medicines Tab ----------------
if menu == "💊 Medicines":
    st.title("💊 Medicines Tracker")

    with st.form("medicine_form"):
        med_date = st.date_input("Date of Purchase", value=date.today())
        med_name = st.text_input("Medicine Name")
        quantity = st.number_input("Quantity", min_value=1, step=1)
        cost = st.number_input("Cost (₹)", min_value=0.0, step=10.0)
        notes = st.text_input("Notes (optional)")
        submit_med = st.form_submit_button("Add Medicine")

    if submit_med and med_name.strip():
        df = ws_to_df(medicines_ws)
        df.loc[len(df)] = [str(med_date), med_name, quantity, cost, notes]
        df_to_ws(df, medicines_ws)
        st.success("✅ Medicine added successfully!")

    st.header("📋 Medicines Table")
    show_table_with_actions(ws_to_df(medicines_ws), medicines_ws)

# ---------------- Investments Tab ----------------
if menu == "💰 Investments":
    st.title("💰 Investments Tracker")
    investment_categories = load_investment_categories()
    inv_type = st.selectbox("Investment Type", investment_categories)

    new_inv = st.text_input("➕ Add New Investment Type")
    if st.button("Add Investment Type"):
        if new_inv.strip() and new_inv not in investment_categories:
            investment_cat_ws.append_row([new_inv])
            st.success("✅ Investment type added!")
            st.rerun()

    with st.form("investment_form"):
        inv_date = st.date_input("Date", value=date.today())
        amount = st.number_input("Amount (₹)", min_value=0.0, step=100.0)
        frequency = st.selectbox("Frequency", ["One-time", "Monthly", "Quarterly"])
        notes = st.text_input("Notes (optional)")
        submit_inv = st.form_submit_button("Add Investment")

    if submit_inv and amount > 0:
        df = ws_to_df(investments_ws)
        df.loc[len(df)] = [str(inv_date), inv_type, amount, frequency, notes]
        df_to_ws(df, investments_ws)
        st.success("✅ Investment added successfully!")

    st.header("📋 Investments Table")
    show_table_with_actions(ws_to_df(investments_ws), investments_ws)

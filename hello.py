import streamlit as st
import pandas as pd
import sqlite3
import datetime
from io import BytesIO

DB_FILE = "expenses.db"
CATEGORY_LIST = [
    "Travel", "Food", "Personal Care", "Shopping", "Entertainment",
    "SIP", "Upskilling", "Family & Loan", "Miscellaneous"
]

def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            type TEXT,
            amount INTEGER,
            category TEXT,
            description TEXT
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS balance (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            amount INTEGER
        )
    """)
    conn.commit()
    conn.close()

def add_entry(date, entry_type, amount, category, description):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute(
        "INSERT INTO expenses (date, type, amount, category, description) VALUES (?, ?, ?, ?, ?)",
        (date, entry_type, amount, category, description)
    )
    conn.commit()
    conn.close()

def get_data():
    conn = sqlite3.connect(DB_FILE)
    df = pd.read_sql_query("SELECT * FROM expenses", conn)
    conn.close()
    return df

def get_balance():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT amount FROM balance WHERE id = 1")
    row = c.fetchone()
    conn.close()
    return row[0] if row else 0

def set_balance(new_amount):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("""
        INSERT INTO balance (id, amount) VALUES (1, ?)
        ON CONFLICT(id) DO UPDATE SET amount=excluded.amount
    """, (new_amount,))
    conn.commit()
    conn.close()

def reset_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM expenses")
    c.execute("DELETE FROM balance")
    conn.commit()
    conn.close()

def get_spending_stats(df):
    today = datetime.date.today()
    first_of_month = today.replace(day=1)
    today_spent = 0
    month_spent = 0
    if not df.empty:
        df['date'] = pd.to_datetime(df['date']).dt.date
        today_spent = df[
            (df['type'] == "Expense") & (df['date'] == today)
        ]['amount'].astype(int).sum()
        month_spent = df[
            (df['type'] == "Expense") & (df['date'] >= first_of_month) & (df['date'] <= today)
        ]['amount'].astype(int).sum()
    return today_spent, month_spent

def get_current_balance(df, initial_balance):
    total_credited = df[df['type'] == "Credited"]["amount"].astype(int).sum() if not df.empty else 0
    total_expense = df[df['type'] == "Expense"]["amount"].astype(int).sum() if not df.empty else 0
    current_balance = initial_balance + total_credited - total_expense
    return current_balance

def to_excel_bytes(df):
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False, sheet_name='Records')
    return output.getvalue()

# --- Main App ---
st.set_page_config(
    page_title="Personal Expense Tracker",
    page_icon="💸",
    layout="wide",
    initial_sidebar_state="collapsed"
)

init_db()

# --- Sidebar Navigation ---
section = st.sidebar.radio(
    "Navigation",
    ["Add Entry", "Add/Update Balance", "Stats & Analysis", "Records"]
)

df = get_data()
initial_balance = get_balance()
current_balance = get_current_balance(df, initial_balance)

# --- Display Quick Spend Summary only on Add Entry and Stats & Analysis ---
if section in ["Add Entry", "Stats & Analysis"]:
    today_spent, month_spent = get_spending_stats(df)
    st.markdown("### Overall Spend Summary")
    col_t1, col_t2, col_t3 = st.columns(3)
    col_t1.metric("Today's Total Spent", f"₹{today_spent}")
    col_t2.metric("Monthly Spent", f"₹{month_spent}")
    col_t3.metric("Current Balance", f"₹{current_balance}")

if section == "Add Entry":
    st.header("Add New Entry")
    with st.form(key="entry_form", clear_on_submit=True):
        entry_date = st.date_input("Date", datetime.date.today())
        entry_type = st.selectbox("Type", ["Expense", "Credited"])
        amount = st.text_input("Amount (whole numbers only)", "")

        if entry_type == "Expense":
            category = st.selectbox("Category", CATEGORY_LIST)
            description = st.text_input("Description (optional)")
        else:
            category = ""
            description = ""

        submitted = st.form_submit_button("Add")
        if submitted:
            if not amount.isdigit() or int(amount) <= 0:
                st.error("Amount must be a positive whole number.")
            elif entry_type == "Expense" and not category:
                st.error("Category is required for Expense.")
            else:
                add_entry(
                    entry_date,
                    entry_type,
                    int(amount),
                    category,
                    description
                )
                st.success(f"{entry_type} of ₹{amount} added on {entry_date}.")

elif section == "Add/Update Balance":
    st.header("Add or Update Bank Balance")
    st.info(f"Current Bank Balance: ₹{initial_balance}")
    with st.form(key="balance_form", clear_on_submit=True):
        new_balance = st.text_input("Set/Update your current bank balance (whole number)", value=str(initial_balance if initial_balance else ""))
        balance_submitted = st.form_submit_button("Update Balance")
        if balance_submitted:
            if not new_balance.isdigit() or int(new_balance) < 0:
                st.error("Balance must be a positive whole number (or zero).")
            else:
                set_balance(int(new_balance))
                st.success(f"Bank balance updated to ₹{new_balance}")

elif section == "Stats & Analysis":
    st.header("Stats & Analysis")
    if df.empty:
        st.info("No data yet. Start adding your expenses or credits.")
    else:
        df['date'] = pd.to_datetime(df['date']).dt.date
        df['amount'] = df['amount'].astype(int)

        st.subheader("Daily Summary")
        daily = (
            df[df['type'].isin(["Expense", "Credited"])]
            .groupby(['date', 'type'])['amount']
            .sum()
            .unstack(fill_value=0)
            .reset_index()
        )
        st.dataframe(daily, use_container_width=True)

        st.subheader("Category-wise Expense")
        cat_exp = (
            df[df['type'] == "Expense"]
            .groupby("category")['amount'].sum().sort_values(ascending=False)
        )
        st.bar_chart(cat_exp)

        st.subheader("Expense/Credit Trend")
        chart_df = (
            df[df['type'].isin(["Expense", "Credited"])]
            .groupby(['date', 'type'])['amount']
            .sum()
            .unstack(fill_value=0)
        )
        st.line_chart(chart_df)

        st.subheader("All Entries")
        st.dataframe(df.sort_values("date", ascending=False), use_container_width=True)

        st.markdown("---")
        st.download_button("Download as CSV", df.to_csv(index=False), "expenses.csv")
        if st.button("Reset All Data"):
            reset_db()
            st.warning("All data reset. Please reload the page.")

elif section == "Records":
    st.header("Records: View Activity By Date Range")
    if df.empty:
        st.info("No data yet.")
    else:
        df['date'] = pd.to_datetime(df['date']).dt.date
        min_date = df['date'].min()
        max_date = df['date'].max()
        col1, col2 = st.columns(2)
        from_date = col1.date_input("From", min_value=min_date, max_value=max_date, value=min_date)
        to_date = col2.date_input("To", min_value=min_date, max_value=max_date, value=max_date)
        if from_date > to_date:
            st.warning("Start date must be before end date.")
        else:
            filtered = df[(df['date'] >= from_date) & (df['date'] <= to_date)]
            st.subheader(f"All records from {from_date} to {to_date}")
            st.dataframe(filtered.sort_values("date", ascending=False), use_container_width=True)
            if not filtered.empty:
                excel_data = to_excel_bytes(filtered)
                st.download_button(
                    label="Download as Excel",
                    data=excel_data,
                    file_name=f"records_{from_date}_to_{to_date}.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )

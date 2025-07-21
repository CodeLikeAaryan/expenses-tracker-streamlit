import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime
import altair as alt

# — Page Config (hamburger on mobile) —
st.set_page_config(
    page_title="📊 Mobile Expense Tracker",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# — Database Setup —
conn = sqlite3.connect("expenses.db", check_same_thread=False)
c = conn.cursor()

# Create tables if they don't exist
c.execute("""CREATE TABLE IF NOT EXISTS expenses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    category TEXT,
    amount REAL,
    notes TEXT
)""")
c.execute("""CREATE TABLE IF NOT EXISTS balances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    amount REAL,
    notes TEXT
)""")
c.execute("""CREATE TABLE IF NOT EXISTS account_balance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    balance REAL,
    notes TEXT
)""")
c.execute("""CREATE TABLE IF NOT EXISTS records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    action TEXT,
    details TEXT
)""")
conn.commit()

# — Helper to fetch metrics & cache them —
@st.cache_data
def get_sums():
    today_iso = date.today().isoformat()
    # Today's total expense
    today_exp = c.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE date = ?", (today_iso,)
    ).fetchone()[0]
    # Total credits ever
    total_cred = c.execute(
        "SELECT COALESCE(SUM(amount),0) FROM balances"
    ).fetchone()[0]
    # Latest manual bank set
    row = c.execute(
        "SELECT date, balance FROM account_balance ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row:
        manual_date_iso, manual_bal = row
    else:
        manual_date_iso, manual_bal = "1970-01-01", 0.0
    # Credits since manual set
    cred_after = c.execute(
        "SELECT COALESCE(SUM(amount),0) FROM balances WHERE date >= ?", (manual_date_iso,)
    ).fetchone()[0]
    # Expenses since manual set
    exp_after = c.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE date >= ?", (manual_date_iso,)
    ).fetchone()[0]
    # Dynamic balance
    current_bal = manual_bal + cred_after - exp_after
    return today_exp, total_cred, current_bal

# — Sidebar Navigation —
st.sidebar.title("⚙️ Menu")
page = st.sidebar.radio("", ["Dashboard / Add", "Reports", "Records"])

if page == "Dashboard / Add":
    # Top metrics
    today_exp, total_cred, current_bal = get_sums()
    m1, m2, m3 = st.columns(3)
    m1.metric("💸 Today's Spent", f"₹{today_exp:,.2f}")
    m2.metric("💰 Total Credited", f"₹{total_cred:,.2f}")
    m3.metric("🏦 Bank Balance", f"₹{current_bal:,.2f}")

    st.markdown("---")
    action = st.radio(
        "What would you like to do?",
        ["Add Expense", "Add Balance", "Set Bank Amount"],
        horizontal=True
    )

    if action == "Add Expense":
        st.subheader("➕ Add a New Expense")
        with st.form("expense_form", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns([2,2,2,4])
            with c1:
                exp_date = st.date_input("Date", date.today())
            with c2:
                category = st.selectbox("Category", [
                    "Food","Learning","Investment",
                    "Entertainment","Shopping",
                    "Loans And Family","Miscellaneous"
                ])
            with c3:
                amt_text = st.text_input("Amount (₹)", placeholder="e.g. 150.75")
            with c4:
                notes = st.text_input("Notes (optional)")
            if st.form_submit_button("Add Expense"):
                try:
                    amt = float(amt_text)
                    c.execute(
                        "INSERT INTO expenses (date, category, amount, notes) VALUES (?,?,?,?)",
                        (exp_date.isoformat(), category, amt, notes)
                    )
                    c.execute(
                        "INSERT INTO records (timestamp, action, details) VALUES (?,?,?)",
                        (
                            datetime.now().isoformat(),
                            "Expense",
                            f"₹{amt:.2f} ({category})"
                        )
                    )
                    conn.commit()
                    st.success("✅ Expense recorded!")
                    st.cache_data.clear()
                    st.rerun()
                except ValueError:
                    st.error("❌ Enter a valid number for Amount.")

    elif action == "Add Balance":
        st.subheader("➕ Add a Balance (Credit)")
        with st.form("balance_form", clear_on_submit=True):
            b1, b2, b3 = st.columns([2,2,6])
            with b1:
                bal_date = st.date_input("Date", date.today())
            with b2:
                bal_text = st.text_input("Credit Amount (₹)", placeholder="e.g. 2000.00")
            with b3:
                bal_notes = st.text_input("Notes (optional)")
            if st.form_submit_button("Add Balance"):
                try:
                    bal_amt = float(bal_text)
                    c.execute(
                        "INSERT INTO balances (date, amount, notes) VALUES (?,?,?)",
                        (bal_date.isoformat(), bal_amt, bal_notes)
                    )
                    c.execute(
                        "INSERT INTO records (timestamp, action, details) VALUES (?,?,?)",
                        (
                            datetime.now().isoformat(),
                            "Credit",
                            f"₹{bal_amt:.2f}"
                        )
                    )
                    conn.commit()
                    st.success("✅ Balance added!")
                    st.cache_data.clear()
                    st.rerun()
                except ValueError:
                    st.error("❌ Enter a valid number for Credit Amount.")

    else:  # Set Bank Amount
        st.subheader("🏦 Set Bank Account Amount")
        with st.form("bank_form", clear_on_submit=True):
            b1, b2, b3 = st.columns([2,2,6])
            with b1:
                bank_date = st.date_input("Date", date.today())
            with b2:
                bank_text = st.text_input("Bank Amount (₹)", placeholder="e.g. 50000.00")
            with b3:
                bank_notes = st.text_input("Notes (optional)")
            if st.form_submit_button("Set Bank Amount"):
                try:
                    bank_amt = float(bank_text)
                    c.execute(
                        "INSERT INTO account_balance (date, balance, notes) VALUES (?,?,?)",
                        (bank_date.isoformat(), bank_amt, bank_notes)
                    )
                    c.execute(
                        "INSERT INTO records (timestamp, action, details) VALUES (?,?,?)",
                        (
                            datetime.now().isoformat(),
                            "Set Bank",
                            f"Bank set to ₹{bank_amt:.2f}"
                        )
                    )
                    conn.commit()
                    st.success("✅ Bank amount updated!")
                    st.cache_data.clear()
                    st.rerun()
                except ValueError:
                    st.error("❌ Enter a valid number for Bank Amount.")

    # Expenses list as before
    st.markdown("---")
    st.subheader("🔍 Your Expenses")
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("From", date.today().replace(day=1), key="view_start")
    with col2:
        end = st.date_input("To", date.today(), key="view_end")
    df = pd.read_sql_query(
        "SELECT * FROM expenses WHERE date BETWEEN ? AND ? ORDER BY date DESC",
        conn, params=(start.isoformat(), end.isoformat())
    )
    if df.empty:
        st.info("No expenses in this range.")
    else:
        st.dataframe(df[["id","date","category","amount","notes"]], use_container_width=True)
        st.download_button("📂 Download CSV", df.to_csv(index=False).encode(), "expenses.csv", "text/csv")
        st.markdown("**🗑️ Delete Expenses**")
        to_delete = st.multiselect(
            "Select ID(s) to delete",
            options=df["id"].tolist(),
            format_func=lambda x: f"{x} → {df.loc[df.id==x,'category'].values[0]}, ₹{df.loc[df.id==x,'amount'].values[0]:.2f}"
        )
        if st.button("Delete selected"):
            for did in to_delete:
                c.execute("DELETE FROM expenses WHERE id = ?", (did,))
                c.execute(
                    "INSERT INTO records (timestamp, action, details) VALUES (?,?,?)",
                    (datetime.now().isoformat(), "Delete Expense", f"ID {did}")
                )
            conn.commit()
            st.success(f"Deleted IDs: {to_delete}")
            st.rerun()

elif page == "Reports":
    st.header("📈 Expense Reports")
    df = pd.read_sql_query("SELECT * FROM expenses", conn)
    if df.empty:
        st.warning("No data yet—add some expenses first.")
        st.stop()
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M").astype(str)
    c1, c2, c3 = st.columns(3)
    c1.metric("Total Spent", f"₹{df['amount'].sum():,.2f}")
    c2.metric("Avg. Daily Spend", f"₹{df.groupby('date')['amount'].sum().mean():,.2f}")
    c3.metric("Top Category", df.groupby("category")["amount"].sum().idxmax())
    st.markdown("---")
    st.subheader("Spending Over Time")
    ts = df.groupby("date")["amount"].sum().reset_index()
    st.altair_chart(alt.Chart(ts).mark_line(point=True).encode(x="date:T", y="amount:Q").interactive(), use_container_width=True)
    st.markdown("---")
    st.subheader("Category Breakdown")
    cat = df.groupby("category")["amount"].sum().reset_index()
    l, r = st.columns(2)
    l.altair_chart(alt.Chart(cat).mark_bar().encode(x=alt.X("category:N", sort="-y"), y="amount:Q", tooltip=["category","amount"]), use_container_width=True)
    r.altair_chart(alt.Chart(cat).mark_arc(innerRadius=50).encode(theta="amount:Q", color="category:N", tooltip=["category","amount"]), use_container_width=True)
    st.markdown("---")
    st.subheader("Monthly Totals")
    monthly = df.groupby("month")["amount"].sum().reset_index()
    st.altair_chart(alt.Chart(monthly).mark_line(point=True).encode(x="month:T", y="amount:Q").interactive(), use_container_width=True)

else:  # Records page
    st.header("📝 Action Records")
    # Show metrics
    total_spent = c.execute("SELECT COALESCE(SUM(amount),0) FROM expenses").fetchone()[0]
    total_cred = c.execute("SELECT COALESCE(SUM(amount),0) FROM balances").fetchone()[0]
    _, _, current_bal = get_sums()
    r1, r2, r3 = st.columns(3)
    r1.metric("Total Spent", f"₹{total_spent:,.2f}")
    r2.metric("Total Credited", f"₹{total_cred:,.2f}")
    r3.metric("Bank Balance", f"₹{current_bal:,.2f}")
    st.markdown("---")
    # Date-range filter
    c1, c2 = st.columns(2)
    with c1:
        rec_start = st.date_input("From", date.today().replace(day=1), key="rec_start")
    with c2:
        rec_end = st.date_input("To", date.today(), key="rec_end")
    rec_df = pd.read_sql_query(
        "SELECT timestamp, action, details FROM records WHERE date(timestamp) BETWEEN ? AND ? ORDER BY timestamp DESC",
        conn,
        params=(rec_start.isoformat(), rec_end.isoformat())
    )
    # Format timestamp and columns
    if not rec_df.empty:
        rec_df['Date'] = pd.to_datetime(rec_df['timestamp']).dt.date
        rec_df = rec_df[['Date','action','details']]
        rec_df.columns = ['Date','Action','Details']
        # Download and display
        csv = rec_df.to_csv(index=False).encode()
        st.download_button("📂 Download Records as CSV", csv, "records.csv", "text/csv")
        st.dataframe(rec_df, use_container_width=True)
    else:
        st.info("No records in this range.")

import streamlit as st
import pandas as pd
import sqlite3
from datetime import date, datetime, timedelta
import altair as alt

# — Page Config —
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
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    category TEXT,
    amount REAL,
    notes TEXT
)""")
c.execute("""CREATE TABLE IF NOT EXISTS balances (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    date TEXT,
    amount REAL,
    notes TEXT
)""")
c.execute("""CREATE TABLE IF NOT EXISTS account_balance (
    id      INTEGER PRIMARY KEY AUTOINCREMENT,
    date    TEXT,
    balance REAL,
    notes   TEXT
)""")
c.execute("""CREATE TABLE IF NOT EXISTS records (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT,
    action    TEXT,
    details   TEXT
)""")
conn.commit()

# — Cached Metrics —
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
        manual_date_iso, manual_bal = today_iso, 0.0
    # Dynamic balance
    cred_after = c.execute(
        "SELECT COALESCE(SUM(amount),0) FROM balances WHERE date >= ?", (manual_date_iso,)
    ).fetchone()[0]
    exp_after = c.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE date >= ?", (manual_date_iso,)
    ).fetchone()[0]
    current_bal = manual_bal + cred_after - exp_after
    # Averages
    d7 = (date.today() - timedelta(days=6)).isoformat()
    sum7 = c.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE date BETWEEN ? AND ?", (d7, today_iso)
    ).fetchone()[0]
    avg7 = sum7 / 7
    d30 = (date.today() - timedelta(days=29)).isoformat()
    sum30 = c.execute(
        "SELECT COALESCE(SUM(amount),0) FROM expenses WHERE date BETWEEN ? AND ?", (d30, today_iso)
    ).fetchone()[0]
    avg30 = sum30 / 30
    return today_exp, total_cred, current_bal, avg7, avg30

# — Session override defaults —
for key in ("override_today", "override_credit", "override_balance"):
    if key not in st.session_state:
        st.session_state[key] = None

# — Sidebar Navigation —
st.sidebar.title("⚙️ Menu")
page = st.sidebar.radio("", ["Dashboard / Add", "Edit Details", "Reports", "Records"])

# — Helper to apply overrides —
def get_metrics():
    today_exp, total_cred, current_bal, avg7, avg30 = get_sums()
    if st.session_state.override_today is not None:
        today_exp = st.session_state.override_today
    if st.session_state.override_credit is not None:
        total_cred = st.session_state.override_credit
    if st.session_state.override_balance is not None:
        current_bal = st.session_state.override_balance
    return today_exp, total_cred, current_bal, avg7, avg30

# — Main Pages —
if page == "Dashboard / Add":
    today_exp, total_cred, current_bal, avg7, avg30 = get_metrics()
    cols = st.columns(5)
    cols[0].metric("💸 Today's Spent", f"₹{today_exp:,.2f}")
    cols[1].metric("💰 Total Credited", f"₹{total_cred:,.2f}")
    cols[2].metric("🏦 Bank Balance", f"₹{current_bal:,.2f}")
    cols[3].metric("🗓️ Weekly Average", f"₹{avg7:,.2f}")
    cols[4].metric("🌐 Monthly Average", f"₹{avg30:,.2f}")

    st.markdown("---")
    action = st.radio(
        "Action:", ["Add Expense", "Add Credited Amount", "Set Bank Amount"], horizontal=True
    )

    if action == "Add Expense":
        st.subheader("➕ Add a New Expense")
        with st.form("expense_form", clear_on_submit=True):
            c1, c2, c3, c4 = st.columns([2,2,2,4])
            exp_date = c1.date_input("Date", date.today())
            category = c2.selectbox("Category", [
                "Food","Learning","Investment","Entertainment",
                "Shopping","Loans And Family","Miscellaneous"
            ])
            amt_text = c3.text_input("Amount (₹)", placeholder="e.g. 150.75")
            notes = c4.text_input("Notes (optional)")
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
        # Delete today's expenses
        st.markdown("**🗑️ Delete Today's Expenses**")
        today_str = date.today().isoformat()
        df_today = pd.read_sql_query(
            "SELECT id, category, amount FROM expenses WHERE date = ?", conn,
            params=(today_str,)
        )
        if not df_today.empty:
            to_delete = st.multiselect(
                "Select IDs to delete:",
                options=df_today.id.tolist(),
                format_func=lambda x: f"{x} → {df_today[df_today.id==x].category.values[0]}, ₹{df_today[df_today.id==x].amount.values[0]:.2f}"
            )
            if st.button("Delete Selected"):
                for did in to_delete:
                    c.execute("DELETE FROM expenses WHERE id = ?", (did,))
                    c.execute(
                        "INSERT INTO records (timestamp, action, details) VALUES (?,?,?)",
                        (datetime.now().isoformat(), "Delete Expense", f"ID {did}")
                    )
                conn.commit()
                st.success(f"Deleted IDs: {to_delete}")
                st.cache_data.clear()
                st.rerun()

    elif action == "Add Balance":
        st.subheader("➕ Add a Balance (Credit)")
        with st.form("balance_form", clear_on_submit=True):
            b1, b2, b3 = st.columns([2,2,6])
            bal_date = b1.date_input("Date", date.today())
            bal_text = b2.text_input("Credit Amount (₹)", placeholder="e.g. 2000.00")
            bal_notes = b3.text_input("Notes (optional)")
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
            bank_date = b1.date_input("Date", date.today())
            bank_text = b2.text_input("Bank Amount (₹)", placeholder="e.g. 50000.00")
            bank_notes = b3.text_input("Notes (optional)")
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

elif page == "Edit Details":
    st.header("✏️ Edit Metrics Manually")
    today_exp, total_cred, current_bal, avg7, avg30 = get_sums()
    with st.form("edit_form"):
        st.session_state.override_today = st.number_input("Today's Spent", value=today_exp)
        st.session_state.override_credit = st.number_input("Total Credited", value=total_cred)
        st.session_state.override_balance = st.number_input("Bank Balance", value=current_bal)
        if st.form_submit_button("Update Metrics"):
            st.success("Metrics updated.")

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
    rec_start = st.date_input("From", date.today().replace(day=1), key="rec_start")
    rec_end = st.date_input("To", date.today(), key="rec_end")
    rec_df = pd.read_sql_query(
        "SELECT timestamp, action, details FROM records WHERE date(timestamp) BETWEEN ? AND ? ORDER BY timestamp DESC",
        conn,
        params=(rec_start.isoformat(), rec_end.isoformat())
    )
    if not rec_df.empty:
        rec_df['Date'] = pd.to_datetime(rec_df['timestamp']).dt.date
        rec_df = rec_df[['Date','action','details']]
        rec_df.columns = ['Date','Action','Details']
        csv = rec_df.to_csv(index=False).encode()
        st.download_button("📂 Download Records as CSV", csv, "records.csv", "text/csv")
        st.dataframe(rec_df, use_container_width=True)
    else:
        st.info("No records in this range.")

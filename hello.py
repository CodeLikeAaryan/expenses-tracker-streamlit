import streamlit as st
import pandas as pd
import sqlite3
from datetime import date
import altair as alt

# — Page Config —
st.set_page_config(
    page_title="📊 Mobile Expense Tracker",
    layout="wide",
    initial_sidebar_state="expanded"
)

# — Database Setup —
conn = sqlite3.connect("expenses.db", check_same_thread=False)
c = conn.cursor()
c.execute("""
    CREATE TABLE IF NOT EXISTS expenses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        date TEXT,
        category TEXT,
        amount REAL,
        notes TEXT
    )
""")
conn.commit()

# — Sidebar Navigation —
st.sidebar.title("⚙️ Navigation")
page = st.sidebar.radio("", ["Add / View Expenses", "Reports"])

if page == "Add / View Expenses":
    st.header("📥 Add Your Expense")
    with st.form("entry_form", clear_on_submit=True):
        col1, col2, col3, col4 = st.columns([2,2,2,4])
        with col1:
            expense_date = st.date_input("Date", value=date.today())
        with col2:
            category = st.selectbox("Category",
                ("Food", "Learning", "Investment", "Entertainment",
                 "Shopping", "Loans And Family", "Miscellaneous"))
        with col3:
            amount = st.number_input("Amount (₹)", min_value=0.0, format="%.2f")
        with col4:
            notes = st.text_input("Notes (optional)")
        submitted = st.form_submit_button("➕ Add Expense")
        if submitted:
            c.execute(
                "INSERT INTO expenses (date, category, amount, notes) VALUES (?, ?, ?, ?)",
                (expense_date.isoformat(), category, amount, notes)
            )
            conn.commit()
            st.success("Expense added!")

    st.markdown("---")
    st.subheader("🔍 Your Expenses")
    col1, col2 = st.columns(2)
    with col1:
        start = st.date_input("From", value=date.today().replace(day=1), key="view_start")
    with col2:
        end = st.date_input("To", value=date.today(), key="view_end")

    df = pd.read_sql_query(
        "SELECT * FROM expenses WHERE date BETWEEN ? AND ? ORDER BY date DESC",
        conn, params=(start.isoformat(), end.isoformat())
    )

    if df.empty:
        st.info("No expenses in this range.")
    else:
        # show ID so user can delete
        st.dataframe(df[["id","date","category","amount","notes"]], use_container_width=True)

        # CSV export
        csv = df.to_csv(index=False).encode()
        st.download_button("📂 Download CSV", csv, "expenses.csv", "text/csv")

        # Deletion UI
        st.markdown("**🗑️ Delete Expenses**")
        to_delete = st.multiselect(
            "Select ID(s) to delete",
            options=df["id"].tolist(),
            format_func=lambda x: f"{x} → {df.loc[df.id==x, 'category'].values[0]}, ₹{df.loc[df.id==x, 'amount'].values[0]:.2f}"
        )
        if st.button("🗑️ Delete selected"):
            for del_id in to_delete:
                c.execute("DELETE FROM expenses WHERE id = ?", (del_id,))
            conn.commit()
            st.success(f"Deleted entries: {to_delete}")
            st.rerun()

elif page == "Reports":
    st.header("📈 Expense Reports")
    df = pd.read_sql_query("SELECT * FROM expenses", conn)
    if df.empty:
        st.warning("No data yet—add some expenses first.")
        st.stop()

    # prepare data
    df["date"] = pd.to_datetime(df["date"])
    df["month"] = df["date"].dt.to_period("M").astype(str)

    # Summary metrics
    total = df["amount"].sum()
    avg_daily = df.groupby("date")["amount"].sum().mean()
    top_cat = df.groupby("category")["amount"].sum().idxmax()
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Spent", f"₹{total:,.2f}")
    col2.metric("Avg. Daily Spend", f"₹{avg_daily:,.2f}")
    col3.metric("Top Category", top_cat)

    st.markdown("---")
    # Time Series Chart
    st.subheader("Spending Over Time")
    ts = df.groupby("date")["amount"].sum().reset_index()
    line = (
        alt.Chart(ts)
        .mark_line(point=True)
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("amount:Q", title="Amount (₹)")
        )
        .interactive()
    )
    st.altair_chart(line, use_container_width=True)

    st.markdown("---")
    # Category Breakdown
    st.subheader("Category Breakdown")
    cat = df.groupby("category")["amount"].sum().reset_index()
    bar = (
        alt.Chart(cat)
        .mark_bar()
        .encode(
            x=alt.X("category:N", sort="-y", title="Category"),
            y=alt.Y("amount:Q", title="Amount (₹)"),
            tooltip=["category","amount"]
        )
    )
    pie = (
        alt.Chart(cat)
        .mark_arc(innerRadius=50)
        .encode(
            theta=alt.Theta("amount:Q"),
            color=alt.Color("category:N"),
            tooltip=["category","amount"]
        )
    )
    c1, c2 = st.columns(2)
    c1.altair_chart(bar, use_container_width=True)
    c2.altair_chart(pie, use_container_width=True)

    st.markdown("---")
    # Monthly Trend
    st.subheader("Monthly Totals")
    monthly = df.groupby("month")["amount"].sum().reset_index()
    month_line = (
        alt.Chart(monthly)
        .mark_line(point=True)
        .encode(
            x=alt.X("month:T", title="Month"),
            y=alt.Y("amount:Q", title="Amount (₹)"),
        )
        .interactive()
    )
    st.altair_chart(month_line, use_container_width=True)

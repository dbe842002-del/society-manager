import streamlit as st
import pandas as pd
from datetime import datetime
import re

# ================= 1. CONFIGURATION & AUTH =================
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Portal", layout="wide")

# Initialize Session States
if "role" not in st.session_state:
    st.session_state.role = None
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# ================= 2. DATA LOADERS =================
def get_csv_url(sheet_name):
    try:
        raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet_id = re.search(r"/d/([a-zA-Z0-9-_]+)", raw_url).group(1)
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    except: return None

@st.cache_data(ttl=60)
def load_data(sheet_name):
    url = get_csv_url(sheet_name)
    try:
        df = pd.read_csv(url)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        # Date conversion for Expenses
        if 'date' in df.columns:
            df['date_dt'] = pd.to_datetime(df['date'], errors='coerce')
        return df
    except: return pd.DataFrame()

def clean_num(val):
    if pd.isna(val) or val == "": return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try: return float(s)
    except: return 0.0

# ================= 3. LOGIN PAGE =================
if not st.session_state.authenticated:
    st.title("🏢 DBE Society Management Portal")
    st.markdown("---")
    
    col1, col2 = st.columns([1.5, 1])
    
    with col1:
        st.image("https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=800&q=80", caption="DBE Residency", use_container_width=True)
        st.info("Welcome! Please log in to access the society's financial records and maintenance status.")

    with col2:
        st.subheader("🔑 Secure Access")
        role_selection = st.radio("Access Level", ["Viewer (Resident)", "Admin (Management)"], index=0)
        password = st.text_input("Enter Password", type="password")
        
        if st.button("Log In"):
            if role_selection == "Admin (Management)" and password == st.secrets.get("admin_password", "admin123"):
                st.session_state.authenticated = True
                st.session_state.role = "admin"
                st.rerun()
            elif role_selection == "Viewer (Resident)" and password == st.secrets.get("view_password", "society123"):
                st.session_state.authenticated = True
                st.session_state.role = "viewer"
                st.rerun()
            else:
                st.error("Invalid credentials. Please try again.")
    st.stop()

# ================= 4. DATA PROCESSING =================
df_owners = load_data("Owners")
df_coll = load_data("Collections")
df_exp = load_data("Expenses")

# Pre-calculate Globals
today = datetime.now()
# Assuming billing started Jan 2025
total_months = (today.year - 2025) * 12 + today.month

# ================= 5. SIDEBAR NAVIGATION =================
st.sidebar.title(f"👤 {st.session_state.role.upper()} PORTAL")
if st.sidebar.button("🚪 Log Out"):
    st.session_state.authenticated = False
    st.session_state.role = None
    st.rerun()

# ================= 6. INTERFACE LOGIC =================

# Define available tabs based on role
if st.session_state.role == "admin":
    tabs = st.tabs(["📊 Reports", "💰 Maintenance Dues", "💸 Expenses", "📋 Database"])
else:
    # Viewer sees only Maintenance and Report (as per your request)
    tabs = st.tabs(["📊 Reports", "💰 Maintenance Dues"])

# ----------------- TAB: REPORTS -----------------
with tabs[0]:
    st.header("Financial Reporting Dashboard")
    
    # --- SUB-SECTION: YEARLY REPORT ---
    st.subheader("📅 Yearly Financial Summary")
    # Group income/expenses by year-month
    # Income logic
    df_coll['amount_num'] = df_coll['amount_received'].apply(clean_num)
    df_coll['date_dt'] = pd.to_datetime(df_coll['date'], errors='coerce')
    income_yearly = df_coll.groupby(df_coll['date_dt'].dt.year)['amount_num'].sum()
    
    # Expense logic
    df_exp['amount_num'] = df_exp['amount'].apply(clean_num)
    df_exp['date_dt'] = pd.to_datetime(df_exp['date'], errors='coerce')
    expense_yearly = df_exp.groupby(df_exp['date_dt'].dt.year)['amount_num'].sum()
    
    y_col1, y_col2 = st.columns(2)
    with y_col1:
        st.write("**Total Yearly Income**")
        st.table(income_yearly.rename("Total Income (₹)"))
    with y_col2:
        st.write("**Total Yearly Expenses**")
        st.table(expense_yearly.rename("Total Expense (₹)"))

    st.divider()

    # --- SUB-SECTION: MONTHLY REPORT ---
    st.subheader("🗓️ Monthly Financial Detail")
    m_list = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    selected_month = st.selectbox("Filter by Month", m_list, index=today.month-1)
    
    m_inc = df_coll[df_coll['months_paid'].str.contains(selected_month, na=False, case=False)]
    m_exp = df_exp[df_exp['month'].str.contains(selected_month, na=False, case=False)]
    
    mc1, mc2 = st.columns(2)
    mc1.metric(f"Income in {selected_month}", f"₹{m_inc['amount_num'].sum():,.0f}")
    mc2.metric(f"Expenses in {selected_month}", f"₹{m_exp['amount_num'].sum():,.0f}")
    
    with st.expander(f"View {selected_month} Transactions"):
        st.write("**Monthly Income Details**")
        st.dataframe(m_inc[['date', 'flat', 'owner', 'amount_received']], use_container_width=True)
        st.write("**Monthly Expense Details**")
        st.dataframe(m_exp[['date', 'description', 'amount']], use_container_width=True)

    st.divider()

    # --- SUB-SECTION: OWNER DUES LIST ---
    st.subheader("📋 Master Owner Dues List")
    report_data = []
    for _, row in df_owners.iterrows():
        flat = row['flat']
        opening = clean_num(row.get('opening_due', 0))
        paid = clean_num(df_coll[df_coll['flat'] == flat]['amount_received'].sum())
        accrued = total_months * MONTHLY_MAINT
        due = (opening + accrued) - paid
        report_data.append({
            "Flat": flat,
            "Owner": row['owner'],
            "Opening Due": opening,
            "Total Paid": paid,
            "Current Outstanding": due
        })
    
    final_report_df = pd.DataFrame(report_data)
    
    # Styling: Highlight debtors in red
    def highlight_debt(s):
        return ['color: #ff4b4b' if v > 0 else 'color: #09ab3b' for v in s]
    
    st.dataframe(final_report_df.style.apply(highlight_debt, subset=['Current Outstanding']), use_container_width=True)

# ----------------- TAB: MAINTENANCE DUES -----------------
with tabs[1]:
    st.subheader("Individual Flat Statement")
    search_flat = st.selectbox("Search Flat", sorted(df_owners['flat'].unique()))
    
    o_data = df_owners[df_owners['flat'] == search_flat].iloc[0]
    p_history = df_coll[df_coll['flat'] == search_flat]
    
    # Calculations
    f_opening = clean_num(o_data.get('opening_due', 0))
    f_paid = clean_num(p_history['amount_received'].sum())
    f_accrued = total_months * MONTHLY_MAINT
    f_balance = (f_opening + f_accrued) - f_paid
    
    sc1, sc2 = st.columns([1, 2])
    with sc1:
        st.info(f"👤 **Owner:** {o_data['owner']}")
        st.metric("Balance Due", f"₹{f_balance:,.0f}")
        
    with sc2:
        st.write("**Recent Payment History**")
        st.dataframe(p_history[['date', 'months_paid', 'amount_received', 'mode']], use_container_width=True, hide_index=True)

    # --- ADMIN ONLY: ADD PAYMENT ---
    if st.session_state.role == "admin":
        st.divider()
        with st.form("admin_pay"):
            st.subheader("➕ Record New Payment")
            a1, a2, a3 = st.columns(3)
            new_date = a1.date_input("Date")
            new_amt = a2.number_input("Amount Received", value=2100)
            new_months = a3.text_input("Months Paid (e.g., Mar-26)")
            if st.form_submit_button("Save Payment to Sheet"):
                # Append logic here using conn.update
                st.success("Record saved! (Simulated)")

# ----------------- ADMIN ONLY TABS -----------------
if st.session_state.role == "admin":
    with tabs[2]:
        st.subheader("Expense Management")
        st.dataframe(df_exp, use_container_width=True)
    with tabs[3]:
        st.subheader("Raw Databases")
        st.write("Owners")
        st.dataframe(df_owners, use_container_width=True)
        st.write("Collections")
        st.dataframe(df_coll, use_container_width=True)

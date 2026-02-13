import streamlit as st
import pandas as pd
from datetime import datetime
import re

# ================= 1. SETTINGS & AUTH =================
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Portal", layout="wide")

if "role" not in st.session_state: st.session_state.role = None
if "authenticated" not in st.session_state: st.session_state.authenticated = False

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
    with col2:
        st.subheader("🔐 Secure Access")
        role = st.selectbox("I am a:", ["Viewer (Resident)", "Admin (Management)"])
        pwd = st.text_input("Password", type="password")
        if st.button("Access Portal"):
            if role == "Admin (Management)" and pwd == st.secrets.get("admin_password", "admin123"):
                st.session_state.authenticated, st.session_state.role = True, "admin"
                st.rerun()
            elif role == "Viewer (Resident)" and pwd == st.secrets.get("view_password", "society123"):
                st.session_state.authenticated, st.session_state.role = True, "viewer"
                st.rerun()
            else: st.error("Wrong password")
    st.stop()

# ================= 4. LOAD DATA =================
df_owners = load_data("Owners")
df_coll = load_data("Collections")
df_exp = load_data("Expenses")
df_bal = load_data("Balance") # New Balance Sheet

# Global Date logic
today = datetime.now()
total_months = (today.year - 2025) * 12 + today.month

# ================= 5. TABS =================
if st.session_state.role == "admin":
    t_maint, t_master, t_reports, t_db = st.tabs(["💰 Maintenance Due", "📋 Master List", "📊 Financial Reports", "⚙️ Admin DB"])
else:
    t_maint, t_master, t_reports = st.tabs(["💰 Maintenance Due", "📋 Master List", "📊 Financial Reports"])

# ----------------- TAB: MAINTENANCE DUE -----------------
with t_maint:
    st.subheader("Individual Resident Statement")
    
    # Requirement: Year selection box
    available_years = sorted(df_coll['date_dt'].dt.year.dropna().unique().astype(int), reverse=True)
    sel_year_maint = st.selectbox("Filter History by Year", available_years)
    
    search_flat = st.selectbox("Select Flat", sorted(df_owners['flat'].unique()))
    o_row = df_owners[df_owners['flat'] == search_flat].iloc[0]
    
    # Calculations
    f_pats_all = df_coll[df_coll['flat'] == search_flat]
    f_pats_yr = f_pats_all[f_pats_all['date_dt'].dt.year == sel_year_maint]
    
    f_open = clean_num(o_row.get('opening_due', 0))
    f_paid_total = f_pats_all['amount_received'].apply(clean_num).sum()
    f_due = (f_open + (total_months * MONTHLY_MAINT)) - f_paid_total
    
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"👤 **Owner:** {o_row['owner']}")
        st.metric("Total Outstanding", f"₹{int(f_due):,}")
    with c2:
        st.write(f"**Payment History ({sel_year_maint})**")
        st.dataframe(f_pats_yr[['date', 'months_paid', 'amount_received', 'mode']], hide_index=True)

# ----------------- TAB: MASTER LIST -----------------
with t_master:
    st.subheader("📋 Master Dues Status")
    report_list = []
    for _, row in df_owners.iterrows():
        flat = row['flat']
        opening = clean_num(row.get('opening_due', 0))
        paid = df_coll[df_coll['flat'] == flat]['amount_received'].apply(clean_num).sum()
        accrued = total_months * MONTHLY_MAINT
        due = (opening + accrued) - paid
        
        entry = {"Flat": flat, "Owner": row['owner'], "Current Outstanding": int(due)}
        if st.session_state.role == "admin":
            entry["Total Paid"] = int(paid)
        report_list.append(entry)
    
    st.dataframe(pd.DataFrame(report_list), use_container_width=True)

# ----------------- TAB: FINANCIAL REPORTS -----------------
with t_reports:
    # 1. Yearly Report (Previous Year)
    prev_year = today.year - 1
    st.header(f"📅 Yearly Summary: {prev_year}")
    
    y_inc = df_coll[df_coll['date_dt'].dt.year == prev_year]['amount_received'].apply(clean_num).sum()
    y_exp = df_exp[df_exp['date_dt'].dt.year == prev_year]['amount'].apply(clean_num).sum()
    
    yc1, yc2, yc3 = st.columns(3)
    yc1.metric("Total Income", f"₹{int(y_inc):,}")
    yc2.metric("Total Expense", f"₹{int(y_exp):,}")
    yc3.metric("Net Surplus", f"₹{int(y_inc - y_exp):,}")

    st.divider()

    # 2. Monthly Cash Flow (Using Balance Sheet)
    st.header("🗓️ Monthly Cash Flow & Expense Details")
    m_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = st.selectbox("Select Month", m_names, index=today.month-1)

    # Lookup Opening Balance from df_bal
    # We look for the row where month matches selected month (e.g. "Jan")
    bal_row = df_bal[df_bal['month'].str.contains(sel_m, na=False, case=False)]
    
    if not bal_row.empty:
        op_cash = clean_num(bal_row.iloc[0].get('opening_cash', 0))
        op_bank = clean_num(bal_row.iloc[0].get('opening_bank', 0))
    else:
        op_cash, op_bank = 0, 0
        st.warning(f"No entry found in 'Balance' sheet for {sel_m}. Using 0 as opening balance.")

    # Filter Current Month Data
    m_inc = df_coll[df_coll['months_paid'].str.contains(sel_m, na=False, case=False)]
    m_exp = df_exp[df_exp['month'].str.contains(sel_m, na=False, case=False)]

    # Cash vs Bank Logic
    c_in = m_inc[m_inc['mode'].str.lower().str.contains('cash', na=False)]['amount_received'].apply(clean_num).sum()
    c_out = m_exp[m_exp['mode'].str.lower().str.contains('cash', na=False)]['amount'].apply(clean_num).sum()
    
    b_in = m_inc[~m_inc['mode'].str.lower().str.contains('cash', na=False)]['amount_received'].apply(clean_num).sum()
    b_out = m_exp[~m_exp['mode'].str.lower().str.contains('cash', na=False)]['amount'].apply(clean_num).sum()

    mc1, mc2 = st.columns(2)
    with mc1:
        st.subheader("💵 Cash Flow")
        st.write(f"Opening Cash: ₹{int(op_cash):,}")
        st.write(f"Add: Cash Collections: ₹{int(c_in):,}")
        st.write(f"Less: Cash Expenses: ₹{int(c_out):,}")
        st.markdown(f"**Closing Cash: ₹{int(op_cash + c_in - c_out):,}**")
        
    with mc2:
        st.subheader("🏦 Bank Flow")
        st.write(f"Opening Bank: ₹{int(op_bank):,}")
        st.write(f"Add: Bank Collections: ₹{int(b_in):,}")
        st.write(f"Less: Bank Expenses: ₹{int(b_out):,}")
        st.markdown(f"**Closing Bank: ₹{int(op_bank + b_in - b_out):,}**")

    st.write(f"**Detailed Expenses (Head-wise) for {sel_m}**")
    if not m_exp.empty:
        st.dataframe(m_exp[['date', 'head', 'description', 'amount', 'mode']], use_container_width=True, hide_index=True)

# ----------------- ADMIN DB -----------------
if st.session_state.role == "admin":
    with t_db:
        st.subheader("Raw Data Inspection")
        st.write("Balance Sheet Data")
        st.dataframe(df_bal)

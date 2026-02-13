import streamlit as st
import pandas as pd
from datetime import datetime
import re

# ================= 1. THEME & UI STYLING =================
st.set_page_config(page_title="DBE Society Portal", layout="wide")

# Modern UI Styling
st.markdown("""
    <style>
    .main { background-color: #f0f2f6; }
    div[data-testid="stMetric"] {
        background-color: #ffffff;
        border: 1px solid #e0e0e0;
        padding: 15px;
        border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .stTabs [data-baseweb="tab-list"] button [data-testid="stMarkdownContainer"] p {
        font-size: 18px;
        font-weight: bold;
    }
    .status-red { color: #ff4b4b; font-weight: bold; }
    .status-green { color: #09ab3b; font-weight: bold; }
    </style>
    """, unsafe_allow_html=True)

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
            df['date_dt'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
        return df
    except: return pd.DataFrame()

def clean_num(val):
    if pd.isna(val) or val == "": return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try: return float(s)
    except: return 0.0

# ================= 3. AUTHENTICATION =================
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
    st.session_state.role = None

if not st.session_state.authenticated:
    st.title("🏢 DBE Residency Portal")
    st.markdown("---")
    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.image("https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=800&q=80", use_container_width=True)
    with c2:
        st.subheader("🔐 Member Login")
        role = st.selectbox("Role", ["Viewer (Resident)", "Admin (Management)"])
        pwd = st.text_input("Password", type="password")
        if st.button("Login"):
            if role == "Admin (Management)" and pwd == st.secrets.get("admin_password", "admin123"):
                st.session_state.authenticated, st.session_state.role = True, "admin"
                st.rerun()
            elif role == "Viewer (Resident)" and pwd == st.secrets.get("view_password", "society123"):
                st.session_state.authenticated, st.session_state.role = True, "viewer"
                st.rerun()
            else: st.error("Invalid Credentials")
    st.stop()

# ================= 4. LOAD CORE DATA =================
df_owners = load_data("Owners")
df_coll = load_data("Collections")
df_exp = load_data("Expenses")
df_bal = load_data("Balance")

MONTHLY_MAINT = 2100
current_date = datetime.now()
# Months since Jan 2025
total_months_elapsed = (current_date.year - 2025) * 12 + current_date.month

# ================= 5. INTERFACE =================
st.sidebar.title("🏢 DBE Society")
st.sidebar.info(f"Access: **{st.session_state.role.upper()}**")
if st.sidebar.button("Log Out"):
    st.session_state.authenticated = False
    st.rerun()

# Define Tabs
if st.session_state.role == "admin":
    tabs = st.tabs(["💰 Maintenance Due", "📋 Master List", "📊 Financial Reports", "⚙️ Admin DB"])
else:
    tabs = st.tabs(["💰 Maintenance Due", "📋 Master List", "📊 Financial Reports"])

# ----------------- TAB: MAINTENANCE DUE (Individual) -----------------
with tabs[0]:
    st.subheader("🔎 My Maintenance Statement")
    
    # Year Selection Filter
    all_years = sorted(df_coll['date_dt'].dt.year.dropna().unique().astype(int), reverse=True)
    if not all_years: all_years = [2025, 2026]
    sel_year = st.selectbox("Select Financial Year", all_years, key="maint_y")
    
    flat_choice = st.selectbox("Select Flat", sorted(df_owners['flat'].unique()))
    owner_info = df_owners[df_owners['flat'] == flat_choice].iloc[0]
    
    # Global Calculations for the Flat
    f_open = clean_num(owner_info.get('opening_due', 0))
    f_paid_all = df_coll[df_coll['flat'] == flat_choice]['amount_received'].apply(clean_num).sum()
    f_due = (f_open + (total_months_elapsed * MONTHLY_MAINT)) - f_paid_all
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.metric("Current Due", f"₹{int(f_due):,}")
        st.write(f"**Member:** {owner_info['owner']}")
    with c2:
        st.write(f"**Payment History ({sel_year})**")
        yr_pats = df_coll[(df_coll['flat'] == flat_choice) & (df_coll['date_dt'].dt.year == sel_year)]
        st.dataframe(yr_pats[['date', 'months_paid', 'amount_received', 'mode']], use_container_width=True, hide_index=True)

# ----------------- TAB: MASTER LIST (The Dues Grid) -----------------
with tabs[1]:
    st.subheader("📋 Society Master Dues List")
    
    master_data = []
    for _, row in df_owners.iterrows():
        f = row['flat']
        op = clean_num(row.get('opening_due', 0))
        pd_amt = df_coll[df_coll['flat'] == f]['amount_received'].apply(clean_num).sum()
        due = (op + (total_months_elapsed * MONTHLY_MAINT)) - pd_amt
        
        item = {"Flat": f, "Owner": row['owner'], "Current Outstanding": int(due)}
        if st.session_state.role == "admin":
            item["Total Paid"] = int(pd_amt)
        master_data.append(item)
    
    df_master = pd.DataFrame(master_data)
    
    # Styled Display
    st.dataframe(
        df_master.style.format(subset=["Current Outstanding"], formatter="₹{:,}")
        .applymap(lambda x: 'color: red' if x > 0 else 'color: green', subset=['Current Outstanding']),
        use_container_width=True, hide_index=True
    )

# ----------------- TAB: FINANCIAL REPORTS (Reports List) -----------------
with tabs[2]:
    st.header("📊 Financial Reports")
    
    # 1. Yearly Report
    st.subheader("📅 Yearly Summary")
    rpt_year = st.selectbox("Select Year", all_years, key="rpt_y")
    
    y_in = df_coll[df_coll['date_dt'].dt.year == rpt_year]['amount_received'].apply(clean_num).sum()
    y_out = df_exp[df_exp['date_dt'].dt.year == rpt_year]['amount'].apply(clean_num).sum()
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Yearly Income", f"₹{int(y_in):,}")
    m2.metric("Yearly Expense", f"₹{int(y_out):,}")
    m3.metric("Balance", f"₹{int(y_in - y_out):,}")
    
    st.divider()
    
    # 2. Monthly Report with Opening/Closing from Balance Sheet
    st.subheader("🗓️ Monthly Cash Flow")
    m_list = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = st.selectbox("Select Month", m_names if 'm_names' in locals() else m_list, index=current_date.month-1)
    
    # Lookup Opening from 'Balance' Sheet
    bal_match = df_bal[df_bal['month'].str.contains(sel_m, na=False, case=False)]
    op_c = clean_num(bal_match.iloc[0].get('opening_cash', 0)) if not bal_match.empty else 0
    op_b = clean_num(bal_match.iloc[0].get('opening_bank', 0)) if not bal_match.empty else 0
    
    # Current Month Collections & Expenses
    m_inc = df_coll[df_coll['months_paid'].str.contains(sel_m, na=False, case=False)]
    m_exp = df_exp[df_exp['month'].str.contains(sel_m, na=False, case=False)]
    
    # Split Cash/Bank
    c_in = m_inc[m_inc['mode'].str.lower().str.contains('cash', na=False)]['amount_received'].apply(clean_num).sum()
    c_out = m_exp[m_exp['mode'].str.lower().str.contains('cash', na=False)]['amount'].apply(clean_num).sum()
    b_in = m_inc[~m_inc['mode'].str.lower().str.contains('cash', na=False)]['amount_received'].apply(clean_num).sum()
    b_out = m_exp[~m_exp['mode'].str.lower().str.contains('cash', na=False)]['amount'].apply(clean_num).sum()

    col_c, col_b = st.columns(2)
    with col_c:
        st.info("💵 Cash Flow")
        st.write(f"Opening: ₹{int(op_c):,}")
        st.write(f"In: ₹{int(c_in):,}")
        st.write(f"Out: ₹{int(c_out):,}")
        st.markdown(f"**Closing Cash: ₹{int(op_c + c_in - c_out):,}**")

    with col_b:
        st.success("🏦 Bank Flow")
        st.write(f"Opening: ₹{int(op_b):,}")
        st.write(f"In: ₹{int(b_in):,}")
        st.write(f"Out: ₹{int(b_out):,}")
        st.markdown(f"**Closing Bank: ₹{int(op_b + b_in - b_out):,}**")

    st.write("### 📝 Detailed Monthly Expenses")
    st.dataframe(m_exp[['date', 'head', 'description', 'amount', 'mode']], use_container_width=True, hide_index=True)

# ----------------- TAB: ADMIN DB -----------------
if st.session_state.role == "admin":
    with tabs[3]:
        st.subheader("Raw Data Inspection")
        db_choice = st.radio("Select Sheet", ["Owners", "Collections", "Expenses", "Balance"], horizontal=True)
        if db_choice == "Owners": st.dataframe(df_owners)
        elif db_choice == "Collections": st.dataframe(df_coll)
        elif db_choice == "Expenses": st.dataframe(df_exp)
        elif db_choice == "Balance": st.dataframe(df_bal)

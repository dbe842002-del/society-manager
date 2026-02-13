import streamlit as st
import pandas as pd
from datetime import datetime
import re

# ================= 1. THEME & UI STYLING =================
st.set_page_config(page_title="DBE Society Portal", layout="wide")

# Custom CSS for a professional look
st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    .stMetric { background-color: #ffffff; padding: 15px; border-radius: 10px; box-shadow: 0 2px 4px rgba(0,0,0,0.05); border: 1px solid #eee; }
    div[data-testid="stExpander"] { background-color: white; border-radius: 10px; }
    .stButton>button { width: 100%; border-radius: 5px; height: 3em; background-color: #007bff; color: white; }
    .stTabs [data-baseweb="tab-list"] { gap: 8px; }
    .stTabs [data-baseweb="tab"] { 
        background-color: #e9ecef; border-radius: 5px 5px 0 0; padding: 10px 20px;
    }
    .stTabs [aria-selected="true"] { background-color: #007bff !important; color: white !important; }
    </style>
    """, unsafe_all_caller_id=True)

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
    st.title("🏢 DBE Residency Management Portal")
    st.markdown("---")
    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.image("https://images.unsplash.com/photo-1574362848149-11496d93a7c7?q=80&w=1000", use_container_width=True)
    with c2:
        st.subheader("🔐 Secure Access")
        role = st.selectbox("I am a:", ["Viewer (Resident)", "Admin (Management)"])
        pwd = st.text_input("Enter Password", type="password")
        if st.button("Enter Portal"):
            if role == "Admin (Management)" and pwd == st.secrets.get("admin_password", "admin123"):
                st.session_state.authenticated, st.session_state.role = True, "admin"
                st.rerun()
            elif role == "Viewer (Resident)" and pwd == st.secrets.get("view_password", "society123"):
                st.session_state.authenticated, st.session_state.role = True, "viewer"
                st.rerun()
            else: st.error("❌ Incorrect credentials")
    st.stop()

# ================= 4. LOAD CORE DATA =================
df_owners = load_data("Owners")
df_coll = load_data("Collections")
df_exp = load_data("Expenses")
df_bal = load_data("Balance")

# Set global constraints
MONTHLY_MAINT = 2100
current_date = datetime.now()
total_months_elapsed = (current_date.year - 2025) * 12 + current_date.month

# ================= 5. APP INTERFACE =================
st.sidebar.title("🏢 DBE Portal")
st.sidebar.write(f"Logged in as: **{st.session_state.role.upper()}**")
if st.sidebar.button("Log Out"):
    st.session_state.authenticated = False
    st.rerun()

# Defined Tabs
if st.session_state.role == "admin":
    t1, t2, t3, t4 = st.tabs(["💰 Maintenance Due", "📋 Master List", "📊 Financial Reports", "⚙️ Database"])
else:
    t1, t2, t3 = st.tabs(["💰 Maintenance Due", "📋 Master List", "📊 Financial Reports"])

# ----------------- TAB 1: MAINTENANCE DUE (Individual Search) -----------------
with t1:
    st.subheader("🔎 Individual Statement")
    
    # Year Selection Filter (Requirement Met)
    available_years = sorted(df_coll['date_dt'].dt.year.dropna().unique().astype(int), reverse=True)
    if not available_years: available_years = [2025, 2026]
    sel_year_maint = st.selectbox("Select Year to view Statement", available_years, key="y_maint")
    
    col_a, col_b = st.columns([1, 2])
    with col_a:
        search_flat = st.selectbox("Flat Number", sorted(df_owners['flat'].unique()))
        o_row = df_owners[df_owners['flat'] == search_flat].iloc[0]
        
        # Math
        f_open = clean_num(o_row.get('opening_due', 0))
        f_paid_total = df_coll[df_coll['flat'] == search_flat]['amount_received'].apply(clean_num).sum()
        f_due = (f_open + (total_months_elapsed * MONTHLY_MAINT)) - f_paid_total
        
        st.metric("Current Balance", f"₹{int(f_due):,}", delta="Pending" if f_due > 0 else "Cleared", delta_color="inverse")
        st.write(f"**Owner:** {o_row['owner']}")

    with col_b:
        st.write(f"**Transaction History ({sel_year_maint})**")
        p_hist = df_coll[(df_coll['flat'] == search_flat) & (df_coll['date_dt'].dt.year == sel_year_maint)]
        st.dataframe(p_hist[['date', 'months_paid', 'amount_received', 'mode']], use_container_width=True, hide_index=True)

# ----------------- TAB 2: MASTER LIST (The Dues Grid) -----------------
with t2:
    st.subheader("📋 Society Dues Master List")
    
    report_list = []
    for _, row in df_owners.iterrows():
        flat = row['flat']
        opening = clean_num(row.get('opening_due', 0))
        paid = df_coll[df_coll['flat'] == flat]['amount_received'].apply(clean_num).sum()
        accrued = total_months_elapsed * MONTHLY_MAINT
        due = (opening + accrued) - paid
        
        entry = {"Flat": flat, "Owner": row['owner'], "Current Outstanding": int(due)}
        if st.session_state.role == "admin":
            entry["Total Paid"] = int(paid)
        report_list.append(entry)
    
    df_master = pd.DataFrame(report_list)
    
    # Styled Table
    def color_dues(val):
        color = '#ff4b4b' if val > 0 else '#09ab3b'
        return f'color: {color}; font-weight: bold'

    st.dataframe(df_master.style.applymap(color_dues, subset=['Current Outstanding']), use_container_width=True, hide_index=True)

# ----------------- TAB 3: FINANCIAL REPORTS (Cash Flow & Yearly) -----------------
with t3:
    # 1. Yearly Section
    st.header("📅 Yearly Summary")
    # Year Selection (Requirement Met)
    sel_year_rpt = st.selectbox("Select Year for Financial Report", available_years, key="y_rpt")
    
    y_inc = df_coll[df_coll['date_dt'].dt.year == sel_year_rpt]['amount_received'].apply(clean_num).sum()
    y_exp = df_exp[df_exp['date_dt'].dt.year == sel_year_rpt]['amount'].apply(clean_num).sum()
    
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Total Income ({sel_year_rpt})", f"₹{int(y_inc):,}")
    m2.metric(f"Total Expense ({sel_year_rpt})", f"₹{int(y_exp):,}")
    m3.metric("Net Surplus", f"₹{int(y_inc - y_exp):,}")

    st.divider()

    # 2. Monthly Section (Integration with Balance Sheet)
    st.header("🗓️ Monthly Cash Flow")
    m_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = st.selectbox("View Monthly Details", m_names, index=current_date.month-1)

    # Balance Sheet Integration
    bal_match = df_bal[df_bal['month'].str.contains(sel_m, na=False, case=False)]
    if not bal_match.empty:
        op_cash = clean_num(bal_match.iloc[0].get('opening_cash', 0))
        op_bank = clean_num(bal_match.iloc[0].get('opening_bank', 0))
    else:
        op_cash, op_bank = 0, 0
        st.caption(f"ℹ️ No opening balances found in 'Balance' tab for {sel_m}")

    # Month filtering
    m_inc = df_coll[df_coll['months_paid'].str.contains(sel_m, na=False, case=False)]
    m_exp = df_exp[df_exp['month'].str.contains(sel_m, na=False, case=False)]

    # Cash vs Bank Logic
    c_in = m_inc[m_inc['mode'].str.lower().str.contains('cash', na=False)]['amount_received'].apply(clean_num).sum()
    c_out = m_exp[m_exp['mode'].str.lower().str.contains('cash', na=False)]['amount'].apply(clean_num).sum()
    b_in = m_inc[~m_inc['mode'].str.lower().str.contains('cash', na=False)]['amount_received'].apply(clean_num).sum()
    b_out = m_exp[~m_exp['mode'].str.lower().str.contains('cash', na=False)]['amount'].apply(clean_num).sum()

    col_cash, col_bank = st.columns(2)
    with col_cash:
        st.subheader("💵 Cash Account")
        st.write(f"Opening: ₹{int(op_cash):,}")
        st.write(f"Collections: ₹{int(c_in):,}")
        st.write(f"Expenses: ₹{int(c_out):,}")
        st.markdown(f"**Closing Cash: ₹{int(op_cash + c_in - c_out):,}**")

    with col_bank:
        st.subheader("🏦 Bank Account")
        st.write(f"Opening: ₹{int(op_bank):,}")
        st.write(f"Collections: ₹{int(b_in):,}")
        st.write(f"Expenses: ₹{int(b_out):,}")
        st.markdown(f"**Closing Bank: ₹{int(op_bank + b_in - b_out):,}**")

    st.write("### 📝 Head-wise Expenses")
    if not m_exp.empty:
        st.dataframe(m_exp[['date', 'head', 'description', 'amount', 'mode']], use_container_width=True, hide_index=True)
    else:
        st.info("No expense records for this month.")

# ----------------- TAB 4: ADMIN ONLY -----------------
if st.session_state.role == "admin":
    with t4:
        st.subheader("Raw Data Inspection")
        tab_sel = st.radio("Select Sheet", ["Balance", "Owners", "Expenses", "Collections"], horizontal=True)
        if tab_sel == "Balance": st.dataframe(df_bal)
        elif tab_sel == "Owners": st.dataframe(df_owners)
        elif tab_sel == "Expenses": st.dataframe(df_exp)
        else: st.dataframe(df_coll)

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
        # Standardize columns to lowercase
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        # Standardize Date column
        date_col = 'date' if 'date' in df.columns else None
        if date_col:
            df['date_dt'] = pd.to_datetime(df[date_col], errors='coerce')
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

# ================= 4. LOAD & PREPARE DATA =================
df_owners = load_data("Owners")
df_coll = load_data("Collections")
df_exp = load_data("Expenses")

# Pre-calculate totals for calculations
today = datetime.now()
total_months = (today.year - 2025) * 12 + today.month

# ================= 5. TABS LOGIC =================
if st.session_state.role == "admin":
    t_maint, t_master, t_reports, t_db = st.tabs(["💰 Maintenance Due", "📋 Master List", "📊 Financial Reports", "⚙️ Admin DB"])
else:
    t_maint, t_master, t_reports = st.tabs(["💰 Maintenance Due", "📋 Master List", "📊 Financial Reports"])

# ----------------- TAB: MAINTENANCE DUE (Individual) -----------------
with t_maint:
    st.subheader("Individual Resident Statement")
    
    # Year Selection for filtering history
    available_years = sorted(df_coll['date_dt'].dt.year.dropna().unique().astype(int), reverse=True)
    sel_year_maint = st.selectbox("Select Year to view History", available_years, key="maint_year")
    
    search_flat = st.selectbox("Select Your Flat", sorted(df_owners['flat'].unique()))
    
    o_row = df_owners[df_owners['flat'] == search_flat].iloc[0]
    p_history_all = df_coll[df_coll['flat'] == search_flat]
    p_history_year = p_history_all[p_history_all['date_dt'].dt.year == sel_year_maint]
    
    f_opening = clean_num(o_row.get('opening_due', 0))
    f_paid_total = p_history_all['amount_received'].apply(clean_num).sum()
    f_due = (f_opening + (total_months * MONTHLY_MAINT)) - f_paid_total
    
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"👤 **Owner:** {o_row['owner']}")
        st.metric("Total Balance Outstanding", f"₹{int(f_due):,}")
    with c2:
        st.write(f"**Payment History for {sel_year_maint}**")
        st.dataframe(p_history_year[['date', 'months_paid', 'amount_received', 'mode']], use_container_width=True, hide_index=True)

# ----------------- TAB: MASTER LIST (All Flats) -----------------
with t_master:
    st.subheader("📋 Master Dues Status (As of Today)")
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
    # --- 1. YEARLY SUMMARY (Previous Year Jan-Dec) ---
    prev_year = today.year - 1
    st.header(f"📅 Yearly Report: Jan to Dec {prev_year}")
    
    y_inc = df_coll[df_coll['date_dt'].dt.year == prev_year]['amount_received'].apply(clean_num).sum()
    y_exp = df_exp[df_exp['date_dt'].dt.year == prev_year]['amount'].apply(clean_num).sum()
    
    yc1, yc2, yc3 = st.columns(3)
    yc1.metric(f"Total Income ({prev_year})", f"₹{int(y_inc):,}")
    yc2.metric(f"Total Expense ({prev_year})", f"₹{int(y_exp):,}")
    yc3.metric("Yearly Net Savings", f"₹{int(y_inc - y_exp):,}")

    st.divider()

    # --- 2. MONTHLY CASH FLOW REPORT ---
    st.header("🗓️ Monthly Cash Flow & Expense Head-wise")
    m_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m_idx = today.month - 1
    sel_m = st.selectbox("Select Month for Detail", m_names, index=sel_m_idx)
    sel_y = st.selectbox("Select Year for Monthly Report", available_years)

    # Calculate exact Start and End dates for filtering
    sel_month_num = m_names.index(sel_m) + 1
    start_date = datetime(sel_y, sel_month_num, 1)
    
    # Filter Functions
    def filter_by_date(df, date_field, start, end):
        return df[(df[date_field] >= start) & (df[date_field] < end)]

    # Account Balance Logic
    def get_account_stats(df_c, df_e, mode_keywords, current_month_start):
        # Opening: All before this month
        op_inc = df_c[(df_c['date_dt'] < current_month_start) & (df_c['mode'].str.lower().str.contains('|'.join(mode_keywords), na=False, regex=True))]['amount_received'].apply(clean_num).sum()
        op_exp = df_e[(df_e['date_dt'] < current_month_start) & (df_e['mode'].str.lower().str.contains('|'.join(mode_keywords), na=False, regex=True))]['amount'].apply(clean_num).sum()
        opening_bal = op_inc - op_exp
        
        # Current Month
        next_month = (current_month_start.replace(day=28) + pd.Timedelta(days=4)).replace(day=1)
        curr_inc_df = df_c[(df_c['date_dt'] >= current_month_start) & (df_c['date_dt'] < next_month) & (df_c['mode'].str.lower().str.contains('|'.join(mode_keywords), na=False, regex=True))]
        curr_exp_df = df_e[(df_e['date_dt'] >= current_month_start) & (df_e['date_dt'] < next_month) & (df_e['mode'].str.lower().str.contains('|'.join(mode_keywords), na=False, regex=True))]
        
        curr_inc = curr_inc_df['amount_received'].apply(clean_num).sum()
        curr_exp = curr_exp_df['amount'].apply(clean_num).sum()
        
        return int(opening_bal), int(curr_inc), int(curr_exp), int(opening_bal + curr_inc - curr_exp), curr_exp_df

    # 1. Cash Stats
    c_op, c_in, c_out, c_cl, c_exp_df = get_account_stats(df_coll, df_exp, ['cash'], start_date)
    # 2. Bank Stats (Everything NOT cash)
    b_op, b_in, b_out, b_cl, b_exp_df = get_account_stats(df_coll, df_exp, ['online', 'chq', 'cheque', 'neft', 'upi'], start_date)

    # UI Display
    mc1, mc2 = st.columns(2)
    with mc1:
        st.subheader("💵 Cash Account")
        st.write(f"Opening Balance: ₹{c_op:,}")
        st.write(f"Cash Collections: ₹{c_in:,}")
        st.write(f"Cash Expenses: ₹{c_out:,}")
        st.markdown(f"**Closing Cash: ₹{c_cl:,}**")
        
    with mc2:
        st.subheader("🏦 Bank Account")
        st.write(f"Opening Balance: ₹{b_op:,}")
        st.write(f"Bank Collections: ₹{b_in:,}")
        st.write(f"Bank Expenses: ₹{b_out:,}")
        st.markdown(f"**Closing Bank: ₹{b_cl:,}**")

    st.write(f"---")
    st.write(f"**Detailed Expense List (Head-wise) for {sel_m} {sel_y}**")
    all_monthly_exp = pd.concat([c_exp_df, b_exp_df]).sort_values('date_dt')
    if not all_monthly_exp.empty:
        st.dataframe(all_monthly_exp[['date', 'head', 'description', 'amount', 'mode']], use_container_width=True, hide_index=True)
    else:
        st.info("No expenses found for this month.")

# ----------------- ADMIN ONLY -----------------
if st.session_state.role == "admin":
    with t_db:
        st.subheader("Internal Database View")
        st.write("Expenses Log")
        st.dataframe(df_exp)

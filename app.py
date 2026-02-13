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
        st.image("https://images.unsplash.com/photo-1590247813693-5541d1c609fd?auto=format&fit=crop&w=800", caption="DBE Residency", use_container_width=True)
    with col2:
        st.subheader("🔐 Secure Login")
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

# ================= 4. LOAD & CALCULATE =================
df_owners = load_data("Owners")
df_coll = load_data("Collections")
df_exp = load_data("Expenses")

# Date Conversions
df_coll['date_dt'] = pd.to_datetime(df_coll['date'], errors='coerce')
df_exp['date_dt'] = pd.to_datetime(df_exp['date'], errors='coerce')

today = datetime.now()
total_months = (today.year - 2025) * 12 + today.month # Assuming Jan 2025 start

# ================= 5. TABS LOGIC =================
if st.session_state.role == "admin":
    t_maint, t_master, t_reports, t_db = st.tabs(["💰 Maintenance Due", "📋 Master List", "📊 Financial Reports", "⚙️ Admin DB"])
else:
    # Viewer sees exactly as requested
    t_maint, t_master, t_reports = st.tabs(["💰 Maintenance Due", "📋 Master List", "📊 Financial Reports"])

# ----------------- TAB: MAINTENANCE DUE (Individual) -----------------
with t_maint:
    st.subheader("Individual Resident Statement")
    search_flat = st.selectbox("Select Your Flat", sorted(df_owners['flat'].unique()))
    
    o_row = df_owners[df_owners['flat'] == search_flat].iloc[0]
    p_history = df_coll[df_coll['flat'] == search_flat]
    
    f_opening = clean_num(o_row.get('opening_due', 0))
    f_paid = p_history['amount_received'].apply(clean_num).sum()
    f_due = (f_opening + (total_months * MONTHLY_MAINT)) - f_paid
    
    c1, c2 = st.columns(2)
    with c1:
        st.info(f"👤 **Owner:** {o_row['owner']}")
        st.metric("Total Balance Outstanding", f"₹{int(f_due):,}")
    with c2:
        st.write("**Payment History**")
        st.dataframe(p_history[['date', 'months_paid', 'amount_received', 'mode']], use_container_width=True, hide_index=True)

# ----------------- TAB: MASTER LIST (All Flats) -----------------
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
        # "Total Paid" is only added for Admin
        if st.session_state.role == "admin":
            entry["Total Paid"] = int(paid)
        report_list.append(entry)
    
    st.dataframe(pd.DataFrame(report_list), use_container_width=True)

# ----------------- TAB: FINANCIAL REPORTS -----------------
with t_reports:
    # --- Yearly Section ---
    st.header("📅 Yearly Financial Report")
    available_years = sorted(df_coll['date_dt'].dt.year.dropna().unique().astype(int), reverse=True)
    sel_year = st.selectbox("Select Year for Summary", available_years)
    
    y_inc = df_coll[df_coll['date_dt'].dt.year == sel_year]['amount_received'].apply(clean_num).sum()
    y_exp = df_exp[df_exp['date_dt'].dt.year == sel_year]['amount'].apply(clean_num).sum()
    
    yc1, yc2, yc3 = st.columns(3)
    yc1.metric(f"Total Income ({sel_year})", f"₹{int(y_inc):,}")
    yc2.metric(f"Total Expense ({sel_year})", f"₹{int(y_exp):,}")
    yc3.metric("Yearly Savings", f"₹{int(y_inc - y_exp):,}")

    st.divider()

    # --- Monthly Cash Flow Section ---
    st.header("🗓️ Monthly Cash Flow & Expense Details")
    m_list = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = st.selectbox("Select Month for Detail", m_list, index=today.month-1)

    # Filter data for month
    m_inc_data = df_coll[df_coll['months_paid'].str.contains(sel_m, na=False, case=False)]
    m_exp_data = df_exp[df_exp['month'].str.contains(sel_m, na=False, case=False)]

    # Cash vs Bank Logic
    cash_in = m_inc_data[m_inc_data['mode'].str.lower().contains('cash', na=False)]['amount_received'].apply(clean_num).sum()
    cash_out = m_exp_data[m_exp_data['mode'].str.lower().contains('cash', na=False)]['amount'].apply(clean_num).sum()
    
    bank_in = m_inc_data[~m_inc_data['mode'].str.lower().contains('cash', na=False)]['amount_received'].apply(clean_num).sum()
    bank_out = m_exp_data[~m_exp_data['mode'].str.lower().contains('cash', na=False)]['amount'].apply(clean_num).sum()

    mc1, mc2 = st.columns(2)
    with mc1:
        st.subheader("💵 Cash Account")
        st.write(f"Collections: ₹{int(cash_in):,}")
        st.write(f"Expenses: ₹{int(cash_out):,}")
        st.write(f"**Monthly Net Cash:** ₹{int(cash_in - cash_out):,}")
    with mc2:
        st.subheader("🏦 Bank Account")
        st.write(f"Collections: ₹{int(bank_in):,}")
        st.write(f"Expenses: ₹{int(bank_out):,}")
        st.write(f"**Monthly Net Bank:** ₹{int(bank_in - bank_out):,}")

    st.write(f"**Detailed Expenses (Head-wise) for {sel_m}**")
    if not m_exp_data.empty:
        st.dataframe(m_exp_data[['date', 'head', 'description', 'amount', 'mode']].sort_values('date'), use_container_width=True, hide_index=True)
    else:
        st.info("No expenses found for this month.")

# ----------------- ADMIN ONLY -----------------
if st.session_state.role == "admin":
    with t_db:
        st.subheader("Internal Database View")
        st.write("Expenses Log")
        st.dataframe(df_exp)

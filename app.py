import streamlit as st
import pandas as pd
from datetime import datetime
import re

# ================= 1. SETTINGS =================
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Portal", layout="wide")

if "role" not in st.session_state: st.session_state.role = None
if "authenticated" not in st.session_state: st.session_state.authenticated = False

# ================= 2. DATA PROCESSING HELPERS =================
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

# Global Math
today = datetime.now()
total_months = (today.year - 2025) * 12 + today.month # Months since Jan 2025

# ================= 5. TABS =================
if st.session_state.role == "admin":
    t_report, t_maint, t_db = st.tabs(["📊 Financial Reports", "💰 Maintenance Status", "⚙️ Admin DB"])
else:
    t_report, t_maint = st.tabs(["📊 Financial Reports", "💰 Maintenance Status"])

# ----------------- TAB: REPORTS -----------------
with t_report:
    # --- 1. YEARLY SUMMARY (Previous Year Jan-Dec) ---
    prev_year = today.year - 1
    st.header(f"📅 Yearly Report: {prev_year}")
    
    # Filter collections/expenses for previous year
    df_coll['date_dt'] = pd.to_datetime(df_coll['date'], errors='coerce')
    df_exp['date_dt'] = pd.to_datetime(df_exp['date'], errors='coerce')
    
    y_inc = df_coll[df_coll['date_dt'].dt.year == prev_year]['amount_received'].apply(clean_num).sum()
    y_exp = df_exp[df_exp['date_dt'].dt.year == prev_year]['amount'].apply(clean_num).sum()
    
    yc1, yc2, yc3 = st.columns(3)
    yc1.metric(f"Total Income ({prev_year})", f"₹{int(y_inc):,}")
    yc2.metric(f"Total Expense ({prev_year})", f"₹{int(y_exp):,}")
    yc3.metric("Yearly Savings", f"₹{int(y_inc - y_exp):,}")

    st.divider()

    # --- 2. MONTHLY CASH FLOW REPORT ---
    st.subheader("🗓️ Monthly Cash Flow & Expense Head-wise")
    m_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = st.selectbox("Select Month to view details", m_names, index=today.month-1)

    # Cash/Bank Logic (Filtering by Mode)
    def get_flow(df, month_str, mode_list):
        # Income for this month
        inc = df_coll[(df_coll['months_paid'].str.contains(month_str, na=False)) & (df_coll['mode'].isin(mode_list))]
        # Expenses for this month
        exp = df_exp[(df_exp['month'].str.contains(month_str, na=False)) & (df_exp['mode'].isin(mode_list))]
        
        # Calculate Opening (All sums prior to this month)
        # Note: For accurate opening, usually we sum all history up to month start
        return inc['amount_received'].apply(clean_num).sum(), exp['amount'].apply(clean_num).sum()

    cash_in, cash_out = get_flow(df_coll, sel_m, ["Cash", "cash"])
    bank_in, bank_out = get_flow(df_coll, sel_m, ["Online", "Chq", "Cheque"])

    mc1, mc2 = st.columns(2)
    with mc1:
        st.info("**Cash Account**")
        st.write(f"Collections: ₹{int(cash_in):,}")
        st.write(f"Expenses: ₹{int(cash_out):,}")
    with mc2:
        st.success("**Bank Account**")
        st.write(f"Collections: ₹{int(bank_in):,}")
        st.write(f"Expenses: ₹{int(bank_out):,}")

    st.write(f"**Detailed Expenses for {sel_m} (Head-wise)**")
    m_exp_detail = df_exp[df_exp['month'].str.contains(sel_m, na=False)]
    if not m_exp_detail.empty:
        st.dataframe(m_exp_detail[['date', 'head', 'description', 'amount', 'mode']], use_container_width=True, hide_index=True)
    else:
        st.write("No expenses recorded for this month.")

    st.divider()

    # --- 3. MASTER OWNER DUES LIST ---
    st.subheader("📋 Master Dues List")
    report_list = []
    for _, row in df_owners.iterrows():
        flat = row['flat']
        opening = clean_num(row.get('opening_due', 0))
        paid = clean_num(df_coll[df_coll['flat'] == flat]['amount_received'].sum())
        accrued = total_months * MONTHLY_MAINT
        due = (opening + accrued) - paid
        
        entry = {"Flat": flat, "Owner": row['owner'], "Current Outstanding": int(due)}
        # Add 'Total Paid' only if Admin
        if st.session_state.role == "admin":
            entry["Total Paid"] = int(paid)
        report_list.append(entry)
    
    df_final = pd.DataFrame(report_list)
    st.dataframe(df_final.style.applymap(lambda x: 'color: red' if isinstance(x, int) and x > 0 else '', subset=['Current Outstanding']), use_container_width=True)

# ----------------- TAB: MAINTENANCE STATUS -----------------
with t_maint:
    st.subheader("Resident Account Statement")
    target_flat = st.selectbox("Select Flat", sorted(df_owners['flat'].unique()))
    
    # Simple view for residents
    f_pats = df_coll[df_coll['flat'] == target_flat]
    total_f_paid = f_pats['amount_received'].apply(clean_num).sum()
    f_opening = clean_num(df_owners[df_owners['flat'] == target_flat].iloc[0].get('opening_due', 0))
    f_due = (f_opening + (total_months * MONTHLY_MAINT)) - total_f_paid
    
    c1, c2 = st.columns(2)
    c1.metric("Balance Outstanding", f"₹{int(f_due):,}")
    c2.write("**Your Payment History**")
    st.dataframe(f_pats[['date', 'months_paid', 'amount_received']], hide_index=True)

# ----------------- ADMIN ONLY -----------------
if st.session_state.role == "admin":
    with t_db:
        st.write("Raw Expense Log")
        st.dataframe(df_exp)

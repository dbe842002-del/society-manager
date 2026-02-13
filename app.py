import streamlit as st
import pandas as pd
from datetime import datetime
import re

# ================= 1. CONFIGURATION & AUTH =================
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Portal", layout="wide")

# Initialize Session States
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

# ================= 2. FAIL-SAFE DATA LOADER =================
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

# ================= 3. WELCOME & LOGIN PAGE =================
if not st.session_state.authenticated:
    st.title("🏢 DBE Society Management Portal")
    st.markdown("---")
    col1, col2 = st.columns([2, 1])
    
    with col1:
        st.image("https://img.freepik.com/free-vector/modern-city-skyline-background_79603-605.jpg", use_container_width=True)
        st.info("Welcome to the official resident portal. Please enter the viewing password to access records and financial reports.")
    
    with col2:
        st.subheader("Login to View")
        view_pwd = st.text_input("Access Password", type="password")
        if st.button("Enter Portal"):
            if view_pwd == st.secrets.get("view_password", "society123"):
                st.session_state.authenticated = True
                st.rerun()
            else:
                st.error("Incorrect Password")
    st.stop() # Stops execution here if not logged in

# ================= 4. LOAD DATA =================
df_owners = load_data("Owners")
df_coll = load_data("Collections")
df_exp = load_data("Expenses")

# ================= 5. APP CONTENT (HIDDEN UNTIL LOGIN) =================
st.sidebar.title("🏢 DBE Society")
if st.sidebar.button("Log Out"):
    st.session_state.authenticated = False
    st.rerun()

tab_report, tab_maint = st.tabs(["📊 Reports & Records", "💰 Maintenance Status"])

# ----------------- TAB: REPORTS (THE MAIN HUB) -----------------
with tab_report:
    st.header("Financial Performance Report")
    
    # Pre-calculate Dues for all owners
    today = datetime.now()
    total_months = (today.year - 2025) * 12 + today.month
    
    report_list = []
    for _, row in df_owners.iterrows():
        flat = row['flat']
        opening = clean_num(row.get('opening_due', 0))
        paid = clean_num(df_coll[df_coll['flat'] == flat]['amount_received'].sum())
        accrued = total_months * MONTHLY_MAINT
        due = (opening + accrued) - paid
        report_list.append({
            "Flat": flat,
            "Owner": row['owner'],
            "Total Paid": paid,
            "Current Due": due
        })
    
    df_report = pd.DataFrame(report_list)

    # Metrics Row
    m1, m2, m3 = st.columns(3)
    total_in = clean_num(df_coll['amount_received'].sum())
    total_out = clean_num(df_exp['amount'].sum())
    m1.metric("Total Collections (Life)", f"₹{total_in:,.0f}")
    m2.metric("Total Expenses (Life)", f"₹{total_out:,.0f}")
    m3.metric("Cash Balance", f"₹{(total_in - total_out):,.0f}")

    # Section 1: Monthly Financials
    st.subheader("📅 Monthly Financial Summary")
    # Using 'month' column from Expenses/Collections
    month_sel = st.selectbox("Select Month", ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"])
    
    m_col1, m_col2 = st.columns(2)
    with m_col1:
        st.write(f"**Income ({month_sel})**")
        # In Collections, we filter by date or months_paid string
        m_inc = df_coll[df_coll['months_paid'].str.contains(month_sel, na=False, case=False)]
        st.dataframe(m_inc[['date', 'flat', 'amount_received']], use_container_width=True)
    with m_col2:
        st.write(f"**Expenses ({month_sel})**")
        m_exp = df_exp[df_exp['month'].str.contains(month_sel, na=False, case=False)]
        st.dataframe(m_exp[['date', 'description', 'amount']], use_container_width=True)

    # Section 2: Owner Dues List
    st.subheader("📋 Resident Dues List")
    def color_due(val):
        color = 'red' if val > 0 else 'green'
        return f'color: {color}'
    
    st.dataframe(df_report.style.applymap(color_due, subset=['Current Due']), use_container_width=True)

# ----------------- TAB: MAINTENANCE (DETAILED VIEW) -----------------
with tab_maint:
    st.subheader("Detailed Flat Statement")
    sel_flat = st.selectbox("Select Flat Number", df_owners['flat'].unique())
    
    owner_info = df_owners[df_owners['flat'] == sel_flat].iloc[0]
    flat_payments = df_coll[df_coll['flat'] == sel_flat]
    
    c1, c2 = st.columns([1, 2])
    with c1:
        st.info(f"**Owner:** {owner_info['owner']}")
        st.write("**Payment History**")
        st.dataframe(flat_payments[['date', 'months_paid', 'amount_received']], hide_index=True)
    
    with c2:
        # Math Recap
        opening = clean_num(owner_info.get('opening_due', 0))
        total_paid = clean_num(flat_payments['amount_received'].sum())
        accrued = total_months * MONTHLY_MAINT
        balance = (opening + accrued) - total_paid
        
        st.write("### Balance Breakdown")
        st.markdown(f"""
        - **Opening Balance (Jan 2025):** ₹{opening:,.0f}
        - **Maintenance Accrued ({total_months} months):** ₹{accrued:,.0f}
        - **Total Amount Paid:** ₹{total_paid:,.0f}
        ---
        ### **Outstanding Due: ₹{balance:,.0f}**
        """)

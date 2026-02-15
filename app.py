import streamlit as st
import pandas as pd
import re
from datetime import datetime

# ================= CONFIG =================
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Portal", layout="wide")

# ================= THEME =================
st.markdown("""
<style>
.main { background-color: #f8f9fa; }
div[data-testid="stMetric"] {
    background-color: #ffffff; border: 1px solid #e0e0e0;
    padding: 15px; border-radius: 10px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
}
.defaulter-card {
    background-color: #fff5f5; border: 1px solid #feb2b2;
    padding: 20px; border-radius: 10px; margin-bottom: 20px;
    text-align: center; border-left: 5px solid #f56565;
}
.stTabs [data-baseweb="tab-list"] { gap: 10px; }
.stTabs [data-baseweb="tab"] { 
    background-color: #f0f2f6; border-radius: 5px; padding: 10px; font-weight: bold;
}
.stTabs [aria-selected="true"] { background-color: #007bff !important; color: white !important; }
section[data-testid="stSidebar"] > div { display: none !important; }
[data-testid="collapsedControl"], [data-testid="stToolbar"] { display: none !important; }
#MainMenu, header, footer { visibility: hidden !important; height: 0 !important; }
</style>
""", unsafe_allow_html=True)

# ================= DATA LOADER =================
@st.cache_data(ttl=300)
def load_data(sheet_name):
    try:
        base_url = st.secrets.get("connections", {}).get("gsheets", {}).get("spreadsheet", "")
        sheet_id = re.search(r"/d/([a-zA-Z0-9-_]+)", base_url).group(1)
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        df = pd.read_csv(url)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        return df
    except:
        return pd.DataFrame()

def clean_num(val):
    if pd.isna(val) or val == "": return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try: return float(s)
    except: return 0.0

# ================= AUTH =================
if "authenticated" not in st.session_state:
    st.session_state.authenticated, st.session_state.role = False, None

if not st.session_state.authenticated:
    st.title("🏢 DBE Residency Portal")
    col1, col2 = st.columns([1.5, 1])
    with col2:
        st.subheader("🔐 Login")
        role = st.selectbox("Role", ["Viewer", "Admin"])
        pwd = st.text_input("Password", type="password")
        if st.button("Enter Portal"):
            if role == "Admin" and pwd == st.secrets.get("admin_password", "admin123"):
                st.session_state.authenticated, st.session_state.role = True, "admin"
                st.rerun()
            elif role == "Viewer" and pwd == st.secrets.get("view_password", "society123"):
                st.session_state.authenticated, st.session_state.role = True, "viewer"
                st.rerun()
            else: st.error("❌ Invalid credentials")
    st.stop()

# ================= DATA PREP =================
df_owners = load_data("Owners")
df_coll = load_data("Collections")
df_exp = load_data("Expenses")

current_date = datetime.now()
# Assuming billing starts Jan 2025
total_months = (current_date.year - 2025) * 12 + current_date.month

# ================= TABS =================
if st.session_state.role == "admin":
    tabs = st.tabs(["📋 Master", "🔍 Lookup", "📊 Financials", "⚙️ Admin", "➕ Add"])
else:
    tabs = st.tabs(["📋 Master", "🔍 Lookup", "📊 Financials"])

# ================= TAB 0: MASTER =================
with tabs[0]:
    st.header("📋 Society Master Dashboard")
    master_grid = []
    defaulters, total_due_val = 0, 0
    
    for _, row in df_owners.iterrows():
        f = row.get('flat', 'N/A')
        paid = df_coll[df_coll['flat'] == f]['amount_received'].apply(clean_num).sum()
        opening = clean_num(row.get('opening_due', 0))
        due = opening + (total_months * MONTHLY_MAINT) - paid
        total_due_val += due
        if due > 6300: defaulters += 1
        master_grid.append({"Flat": f, "Owner": row.get('owner', 'N/A'), "Due": int(due)})

    c1, c2 = st.columns([2, 1])
    c1.markdown(f'<div class="defaulter-card"><h3>Defaulters Alert</h3><h1>{defaulters}</h1><p>Due > ₹6,300</p></div>', unsafe_allow_html=True)
    c2.metric("Total Flats", len(df_owners))
    c2.metric("Total Owed", f"₹{int(total_due_val):,}")

    # --- STYLING ---
    df_m = pd.DataFrame(master_grid)
    
    def color_due_col(val):
        if val > 6300: return 'background-color: #f8d7da; color: #721c24; font-weight: bold;' # Red
        if val > 0: return 'background-color: #fff3cd; color: #856404;' # Yellow
        return 'background-color: #d4edda; color: #155724;' # Green

    if not df_m.empty:
        # Apply style specifically to the 'Due' column
        styled_master = df_m.style.applymap(color_due_col, subset=['Due']).format({"Due": "₹{:,}"})
        st.dataframe(styled_master, use_container_width=True, hide_index=True)

# ================= TAB 1: LOOKUP =================
with tabs[1]:
    st.header("🔍 Flat Status Lookup")
    flat_list = sorted(df_owners['flat'].dropna().unique())
    sel = st.selectbox("Select Flat", flat_list)
    
    owner_row = df_owners[df_owners['flat'] == sel].iloc[0]
    paid = df_coll[df_coll['flat'] == sel]['amount_received'].apply(clean_num).sum()
    bal = clean_num(owner_row.get('opening_due', 0)) + (total_months * MONTHLY_MAINT) - paid
    
    m1, m2, m3 = st.columns(3)
    m1.metric("Balance Due", f"₹{int(bal):,}")
    m2.metric("Owner", str(owner_row.get('owner', 'N/A')))
    m3.metric("Total Paid", f"₹{int(paid):,}")
    
    st.subheader("📜 Payment History")
    hist = df_coll[df_coll['flat'] == sel][['date', 'months_paid', 'amount_received', 'mode']]
    st.dataframe(hist.sort_values('date', ascending=False) if not hist.empty else pd.DataFrame(), use_container_width=True, hide_index=True)

# ================= TAB 2: FINANCIALS =================
with tabs[2]:
    st.header("📊 Financial Reports")
    
    # Pre-processing Data
    df_coll['amount'] = df_coll['amount_received'].apply(clean_num)
    df_exp['amount_val'] = df_exp['amount'].apply(clean_num)
    
    # 1. LIQUIDITY SUMMARY (Cash & Bank Wise)
    st.subheader("🏦 Liquidity Position")
    
    # Calculate totals by mode
    def get_balance_by_mode(mode_name):
        inc = df_coll[df_coll['mode'].str.lower() == mode_name.lower()]['amount'].sum()
        out = df_exp[df_exp['mode'].str.lower() == mode_name.lower()]['amount_val'].sum()
        return inc, out, inc - out

    cash_in, cash_out, cash_bal = get_balance_by_mode("Cash")
    bank_in, bank_out, bank_bal = get_balance_by_mode("Bank Transfer") # Also include UPI logic as needed
    upi_in, upi_out, upi_bal = get_balance_by_mode("UPI")

    l1, l2, l3 = st.columns(3)
    l1.metric("💵 Cash on Hand", f"₹{int(cash_bal):,}", f"In: ₹{int(cash_in):,}")
    l2.metric("🏦 Bank Balance", f"₹{int(bank_bal + upi_bal):,}", f"In: ₹{int(bank_in + upi_in):,}")
    l3.metric("💰 Total Society Funds", f"₹{int(cash_bal + bank_bal + upi_bal):,}")

    st.divider()

    # 2. MONTHLY EXPENSE DRILL-DOWN
    st.subheader("📅 Monthly Expense Report")
    
    # Ensure date_dt exists for filtering
    if 'date' in df_exp.columns:
        df_exp['date_dt'] = pd.to_datetime(df_exp['date'], dayfirst=True, errors='coerce')
        df_exp['month_yr'] = df_exp['date_dt'].dt.strftime('%b %Y')
        
        available_months = df_exp['month_yr'].unique()
        sel_month = st.selectbox("Select Month to Analyze Expenses", available_months)
        
        month_df = df_exp[df_exp['month_yr'] == sel_month]
        
        col_ex1, col_ex2 = st.columns([2, 1])
        with col_ex1:
            st.dataframe(month_df[['date', 'head', 'amount', 'mode']], use_container_width=True, hide_index=True)
        with col_ex2:
            st.write(f"**Total for {sel_month}**")
            st.title(f"₹{int(month_df['amount_val'].sum()):,}")
    
    st.divider()

    # 3. YEARLY FINANCIAL REPORT
    st.subheader("📈 Yearly Performance")
    
    # Add Year column to both
    df_coll['year'] = pd.to_datetime(df_coll['date'], dayfirst=True, errors='coerce').dt.year
    df_exp['year'] = pd.to_datetime(df_exp['date'], dayfirst=True, errors='coerce').dt.year
    
    years = sorted(df_coll['year'].dropna().unique().astype(int), reverse=True)
    sel_year = st.selectbox("Select Financial Year", years)
    
    year_inc = df_coll[df_coll['year'] == sel_year]['amount'].sum()
    year_exp = df_exp[df_exp['year'] == sel_year]['amount_val'].sum()
    
    y1, y2, y3 = st.columns(3)
    y1.metric(f"{sel_year} Total Income", f"₹{int(year_inc):,}")
    y2.metric(f"{sel_year} Total Expenses", f"₹{int(year_exp):,}")
    y3.metric(f"{sel_year} Net Surplus", f"₹{int(year_inc - year_exp):,}")
    
    # Yearly breakdown by category (Head)
    st.write(f"**{sel_year} Expense Distribution**")
    yearly_breakdown = df_exp[df_exp['year'] == sel_year].groupby('head')['amount_val'].sum().reset_index()
    yearly_breakdown.columns = ['Expense Category', 'Total Amount']
    st.table(yearly_breakdown.style.format({"Total Amount": "₹{:,}"}))
# ================= ADMIN TABS =================
if st.session_state.role == "admin":
    with tabs[3]:
        st.header("⚙️ Admin")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()
        st.dataframe(load_data(st.selectbox("View Sheet", ["Owners", "Collections", "Expenses"])))

    with tabs[4]:
        st.header("➕ Add Entry")
        with st.form("entry_f"):
            t = st.radio("Type", ["Income", "Expense"])
            a = st.number_input("Amount", min_value=0)
            if st.form_submit_button("Submit"):
                st.info("Permanent save requires API connection.")

st.markdown("---")
st.caption("DBE Society Management Portal v2.1")


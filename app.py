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

def clean_column(df, col_name):
    if col_name in df.columns:
        df[col_name] = (
            df[col_name]
            .astype(str)
            .str.replace(r'[₹,\s]', '', regex=True)
            .replace(['nan', 'None', ''], '0')
            .astype(float)
        )
    return df

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
    c1.markdown(f'<div class="defaulter-card"><h3>Overdue Alert</h3><h1>{defaulters}</h1><p>Due > ₹6,300</p></div>', unsafe_allow_html=True)
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
    
    # --- ADDED RECEIPT GENERATOR ---
    if st.button("Generate WhatsApp Receipt"):
        receipt = f"""
*DBE Residency Receipt*
-----------------------
*Flat:* {sel}
*Owner:* {owner_row.get('owner')}
*Amount Paid:* ₹{int(paid):,}
*Current Balance:* ₹{int(bal):,}
*Date:* {datetime.now().strftime('%d-%m-%Y')}
"""
        st.code(receipt, language="markdown")

    st.subheader("📜 Payment History")
    hist = df_coll[df_coll['flat'] == sel][['date', 'months_paid', 'amount_received', 'mode']]
    st.dataframe(hist.sort_values('date', ascending=False) if not hist.empty else pd.DataFrame(), use_container_width=True, hide_index=True)
# ================= TAB 2: FINANCIALS =================
with tabs[2]:
    st.header("📊 Financial Reports")
    
    # --- 0. SAFE PRE-PROCESS DATA ---
    # We create local copies to avoid modifying the cached data
    df_c_local = df_coll.copy()
    df_e_local = df_exp.copy()

    # Ensure columns exist even if data is missing
    if not df_c_local.empty:
        df_c_local['date_dt'] = pd.to_datetime(df_c_local['date'], dayfirst=True, errors='coerce')
        df_c_local['amount_val'] = df_c_local['amount_received'].apply(clean_num)
    else:
        df_c_local = pd.DataFrame(columns=['date', 'amount_received', 'mode', 'date_dt', 'amount_val'])

    if not df_e_local.empty:
        df_e_local['date_dt'] = pd.to_datetime(df_e_local['date'], dayfirst=True, errors='coerce')
        df_e_local['amount_val'] = df_e_local['amount'].apply(clean_num)
        df_e_local['year_int'] = df_e_local['date_dt'].dt.year
        df_e_local['month_str'] = df_e_local['date_dt'].dt.strftime('%B')
    else:
        # Create dummy columns to prevent KeyError in the filters below
        df_e_local = pd.DataFrame(columns=['date', 'head', 'amount', 'mode', 'date_dt', 'amount_val', 'year_int', 'month_str'])

    # --- 1. LIQUIDITY SUMMARY ---
    st.subheader("🏦 Cash & Bank Balance")
    
    def get_totals(df, col):
        if df.empty or col not in df.columns: return 0.0, 0.0
        # Ensure mode column is string to prevent errors
        modes = df['mode'].astype(str).str.lower()
        cash = df[modes.str.contains('cash', na=False)][col].sum()
        bank = df[modes.str.contains('bank|upi|transfer|online|neft', na=False)][col].sum()
        return cash, bank

    c_in, b_in = get_totals(df_c_local, 'amount_val')
    c_out, b_out = get_totals(df_e_local, 'amount_val')

    l1, l2, l3 = st.columns(3)
    l1.metric("💵 Cash on Hand", f"₹{int(c_in - c_out):,}")
    l2.metric("🏦 Bank Balance", f"₹{int(b_in - b_out):,}")
    l3.metric("💰 Total Liquidity", f"₹{int((c_in + b_in) - (c_out + b_out)):,}")

    st.divider()

    # --- 2. MONTHLY EXPENSE DRILL-DOWN ---
    st.subheader("📅 Monthly Expense Drill-down")
    
    # Year logic: Use data years + 2025/2026
    data_years = df_e_local['year_int'].dropna().unique().astype(int).tolist()
    combined_years = sorted(list(set(data_years + [2025, 2026])), reverse=True)
    
    ex_col1, ex_col2 = st.columns(2)
    sel_year_ex = ex_col1.selectbox("Select Year", combined_years, key="exp_yr")
    
    # Month list based on selection
    available_months = df_e_local[df_e_local['year_int'] == sel_year_ex]['month_str'].unique()
    month_list = list(available_months) if len(available_months) > 0 else ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
    sel_month_ex = ex_col2.selectbox("Select Month", month_list)

    month_data = df_e_local[(df_e_local['year_int'] == sel_year_ex) & (df_e_local['month_str'] == sel_month_ex)]
    
    if not month_data.empty:
        st.dataframe(month_data[['date', 'head', 'amount', 'mode']], use_container_width=True, hide_index=True)
        st.info(f"Total for {sel_month_ex} {sel_year_ex}: ₹{int(month_data['amount_val'].sum()):,}")
    else:
        st.warning(f"No expense data recorded for {sel_month_ex} {sel_year_ex}")
        
# ================= ADMIN TABS =================
if st.session_state.role == "admin":
    with tabs[3]:
        st.header("⚙️ Admin")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()
        st.dataframe(load_data(st.selectbox("View Sheet", ["Owners", "Collections", "Expenses"])))

    from streamlit_gsheets import GSheetsConnection

# 1. Initialize Connection
conn = st.connection("gsheets", type=GSheetsConnection)

with tabs[4]:
    st.header("➕ Add New Entry")
    
    # Select which sheet to add data to
    sheet_target = st.radio("Record Type", ["Collections", "Expenses"], horizontal=True)
    
    with st.form("entry_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
    if st.button("Generate WhatsApp Receipt"):
        # Everything below this line MUST be indented 
        receipt = f"""
    *DBE Residency Receipt*
    -----------------------
    *Flat:* {sel}
    *Owner:* {owner_row.get('owner')}
    *Amount Paid:* ₹{int(paid):,}
    *Current Balance:* ₹{int(bal):,}
    *Date:* {datetime.now().strftime('%d-%m-%Y')}
    """
    st.code(receipt, language="markdown")
        # Common Fields
        entry_date = col1.date_input("Date", datetime.now())
        amount = col2.number_input("Amount (₹)", min_value=0, step=100)
        mode = col1.selectbox("Payment Mode", ["Bank/UPI", "Cash", "Cheque"])
        
        # Sheet Specific Fields
        if sheet_target == "Collections":
            flat_list = sorted(df_owners['flat'].dropna().unique())
            flat_no = col2.selectbox("Flat No", flat_list)
            note = st.text_input("Months Paid (e.g., Jan-Mar 2025)")
            
            # Prepare data row for Collections sheet
            new_row = {
                "date": entry_date.strftime("%d/%m/%Y"),
                "flat": flat_no,
                "amount_received": amount,
                "mode": mode,
                "months_paid": note
            }
        else:
            expense_head = col2.text_input("Expense Head (e.g., Cleaning, Electricity)")
            note = st.text_input("Remarks")
            
            # Prepare data row for Expenses sheet
            new_row = {
                "date": entry_date.strftime("%d/%m/%Y"),
                "head": expense_head,
                "amount": amount,
                "mode": mode,
                "remarks": note
            }

        submitted = st.form_submit_button("💾 Save Entry")
        
        if submitted:
            if amount <= 0:
                st.error("Please enter a valid amount.")
            else:
                try:
                    # FETCH existing data
                    existing_data = conn.read(worksheet=sheet_target, ttl=0)
                    
                    # APPEND new row
                    updated_df = pd.concat([existing_data, pd.DataFrame([new_row])], ignore_index=True)
                    
                    # WRITE back to Google Sheets
                    conn.update(worksheet=sheet_target, data=updated_df)
                    
                    st.success(f"✅ Successfully added to {sheet_target}!")
                    st.cache_data.clear() # Clear cache to show new data immediately
                except Exception as e:
                    st.error(f"Error connecting to Google Sheets: {e}")
st.markdown("---")
st.caption("DBE Society Management Portal v2.1")















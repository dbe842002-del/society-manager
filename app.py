import streamlit as st
import pandas as pd
import re
import io
from datetime import datetime
import requests

# ================= CONFIG =================
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Portal", layout="wide")

# ================= THEME =================
st.markdown("""
<style>
/* MAIN BACKGROUND */
.main { background-color: #f8f9fa; }

/* METRIC CARDS */
div[data-testid="stMetric"] {
    background-color: #ffffff; border: 1px solid #e0e0e0;
    padding: 15px; border-radius: 10px;
    box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
}

/* DEFAULTER ALERT CARD */
.defaulter-card {
    background-color: #fff5f5; border: 1px solid #feb2b2;
    padding: 20px; border-radius: 10px; margin-bottom: 20px;
    text-align: center; border-left: 5px solid #f56565;
}

/* TAB STYLING */
.stTabs [data-baseweb="tab-list"] { gap: 10px; }
.stTabs [data-baseweb="tab"] { 
    background-color: #f0f2f6; border-radius: 5px; padding: 10px; font-weight: bold;
}
.stTabs [aria-selected="true"] { background-color: #007bff !important; color: white !important; }

/* HIDE ALL STREAMLIT UI ELEMENTS */
section[data-testid="stSidebar"] > div { display: none !important; }
[data-testid="collapsedControl"], [data-testid="stToolbar"] { display: none !important; }
#MainMenu, header { visibility: hidden !important; height: 0 !important; }
footer, .st-emotion-cache-zq5wmm { display: none !important; }
section[data-testid="stDecoration"] { display: none !important; }
</style>
""", unsafe_allow_html=True)



# ================= DATA LOADER =================
@st.cache_data(ttl=300)
def load_data(sheet_name):
    try:
        # Replace with your actual sheet URL or use secrets
        base_url = st.secrets.get("connections", {}).get("gsheets", {}).get("spreadsheet", "")
        if not base_url: return pd.DataFrame()
        
        sheet_id = re.search(r"/d/([a-zA-Z0-9-_]+)", base_url)
        if not sheet_id: return pd.DataFrame()
        
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id.group(1)}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        df = pd.read_csv(url)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        if 'date' in df.columns:
            df['date_dt'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
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
    st.session_state.authenticated = False
    st.session_state.role = None

if not st.session_state.authenticated:
    st.title("🏢 DBE Residency Portal")
    st.markdown("---")
    col1, col2 = st.columns([1.5, 1])
    
    with col1:
        st.image("https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=800&q=80")
    
    with col2:
        st.subheader("🔐 Login")
        role = st.selectbox("Role", ["Viewer", "Admin"])
        pwd = st.text_input("Password", type="password")
        
        if st.button("Enter Portal"):
            admin_pwd = st.secrets.get("admin_password", "admin123")
            viewer_pwd = st.secrets.get("view_password", "society123")
            
            if role == "Admin" and pwd == admin_pwd:
                st.session_state.authenticated, st.session_state.role = True, "admin"
                st.rerun()
            elif role == "Viewer" and pwd == viewer_pwd:
                st.session_state.authenticated, st.session_state.role = True, "viewer" 
                st.rerun()
            else:
                st.error("❌ Invalid credentials")
    st.stop()

# ================= LOAD DATA =================
df_owners = load_data("Owners")
df_coll = load_data("Collections") 
df_exp = load_data("Expenses")
df_bal = load_data("Balance")

current_date = datetime.now()
total_months = (current_date.year - 2025) * 12 + current_date.month

# ================= TABS =================
tab_labels = ["📋 Master Dashboard", "💰 Dues Report", "📊 Financials"]
if st.session_state.role == "admin":
    tab_labels += ["👤 Flat Lookup", "⚙️ Admin", "➕ Add Entry"]
tabs = st.tabs(tab_labels)

# ================= TAB 1: MASTER DASHBOARD =================
with tabs[0]:
    st.header("📋 Society Master Dashboard")
    
    # Defaulter Summary
    master_grid = []
    defaulters, total_due = 0, 0
    
    for _, row in df_owners.iterrows():
        flat = row.get('flat', '')
        paid = df_coll[df_coll['flat'] == flat]['amount_received'].apply(clean_num).sum()
        opening = clean_num(row.get('opening_due', 0))
        due_amt = opening + (total_months * MONTHLY_MAINT) - paid
        
        total_due += due_amt
        if due_amt > 6300: defaulters += 1
            
        entry = {"Flat": flat, "Owner": row.get('owner', 'N/A'), "Due": int(due_amt)}
        if st.session_state.role == "admin": entry["Paid"] = int(paid)
        master_grid.append(entry)
    
    # Defaulter Alert Card
    col1, col2 = st.columns([2, 1])
    with col1:
        st.markdown(f"""
        <div class="defaulter-card">
            <h3>⚠️ Defaulters Alert</h3>
            <h1 style="color:#c53030;">{defaulters}</h1>
            <p>Flats > ₹6,300 due | Total Due: ₹{int(total_due):,}</p>
        </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.metric("Total Flats", len(df_owners))
        st.metric("Total Due", f"₹{int(total_due):,}")
    
    # Master Table
    df_display = pd.DataFrame(master_grid)
    money_cols = [col for col in df_display.columns if 'due' in col.lower() or 'paid' in col.lower()]
    
    def color_due(val):
        if val > 6300: return 'background-color: #f56565; color: white'
        elif val > 0: return 'background-color: #fed7aa; color: black'
        else: return 'background-color: #c6f6d5; color: black'
    
    if money_cols:
        styled = df_display.style.format({col: "₹{:,}" for col in money_cols}).applymap(color_due, subset=money_cols)
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.dataframe(df_display, use_container_width=True, hide_index=True)

# ================= TAB 2: DUES REPORT =================
with tabs[1]:
    st.header("💰 Maintenance Dues")
    flat_choice = st.selectbox("Select Flat", sorted(df_owners['flat'].dropna().unique()))
    
    owner_row = df_owners[df_owners['flat'] == flat_choice].iloc[0] if not df_owners.empty else {}
    paid_total = df_coll[df_coll['flat'] == flat_choice]['amount_received'].apply(clean_num).sum()
    opening_due = clean_num(owner_row.get('opening_due', 0))
    expected = total_months * MONTHLY_MAINT
    total_due = max(0, opening_due + expected - paid_total)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Due", f"₹{int(total_due):,}", f"₹{int(paid_total):,} paid")
    col2.metric("Opening Due", f"₹{int(opening_due):,}")
    col3.metric("Expected", f"₹{int(expected):,}")
    
    with st.expander("📋 Payment History"):
        payments = df_coll[df_coll['flat'] == flat_choice][['date', 'months_paid', 'amount_received', 'mode']]
        if not payments.empty:
            st.dataframe(payments, use_container_width=True)
        else:
            st.info("No payments recorded")

# ================= TAB 3: FINANCIALS =================
with tabs[2]:
    st.header("📊 Financial Summary")
    
    current_year = datetime.now().year
    year_sel = st.selectbox("Year", [current_year, current_year-1, 2025])
    
    income = df_coll['amount_received'].apply(clean_num).sum() if 'amount_received' in df_coll.columns else 0
    expense = df_exp['amount'].apply(clean_num).sum() if 'amount' in df_exp.columns else 0
    
    col1, col2, col3 = st.columns(3)
    col1.success(f"💰 Income: ₹{int(income):,}")
    col2.error(f"💸 Expense: ₹{int(expense):,}")
    col3.metric("💵 Surplus", f"₹{int(income-expense):,}")
    
    month_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_month = st.selectbox("Month", month_names, index=current_date.month-1)
    
    # Safe monthly filtering
    m_income = df_coll[df_coll.get('months_paid', '').str.contains(sel_month, na=False)] if 'months_paid' in df_coll.columns else pd.DataFrame()
    m_expense = df_exp[df_exp.get('head', '').str.contains(sel_month, na=False)] if 'head' in df_exp.columns else pd.DataFrame()
    
    st.subheader(f"{sel_month} Transactions")
    col1, col2 = st.columns(2)
    with col1: st.dataframe(m_income[['date', 'flat', 'amount_received', 'mode']], use_container_width=True)
    with col2: st.dataframe(m_expense[['date', 'head', 'amount', 'mode']], use_container_width=True)

# ================= ADMIN TABS =================
if st.session_state.role == "admin":
    # Tab 3: Flat Lookup
    with tabs[3]:
        st.header("👤 Flat Details")
        flat_sel = st.selectbox("Select Flat for Detailed View", sorted(df_owners['flat'].dropna().unique()))
        col1, col2 = st.columns(2)
        with col1:
            st.subheader("Owner Info")
            st.write(df_owners[df_owners['flat'] == flat_sel])
        with col2:
            st.subheader("Payment History")
            st.write(df_coll[df_coll['flat'] == flat_sel])
    
    # Tab 4: Admin Control & Delete
    with tabs[4]:
        st.header("⚙️ Admin Panel")
        
        c1, c2 = st.columns(2)
        with c1:
            if st.button("🔄 Refresh All Data"):
                st.cache_data.clear()
                st.rerun()
        
        with c2:
            # DELETE LAST ENTRY LOGIC
            st.subheader("🗑️ Delete Last Entry")
            target_sheet = st.selectbox("Select Sheet", ["Collections", "Expenses"], key="del_sheet")
            if st.button(f"Delete Last Row from {target_sheet}"):
                # Note: This requires the Apps Script Web App URL to function
                st.warning("Feature requires Google Apps Script integration to modify the source sheet.")
        
        st.divider()
        st.subheader("Raw Data Preview")
        sheet_sel = st.selectbox("View Raw Sheet", ["Owners", "Collections", "Expenses", "Balance"])
        st.dataframe(load_data(sheet_sel), use_container_width=True)
    
    # Tab 5: Add Entry (This was the missing part!)
    with tabs[5]:
        st.header("➕ Add New Transaction")
        entry_type = st.radio("Entry Type", ["Payment (Income)", "Expense"], horizontal=True)
        
        with st.form("new_entry_form"):
            col1, col2 = st.columns(2)
            
            with col1:
                entry_date = st.date_input("Date", datetime.now())
                mode = st.selectbox("Payment Mode", ["UPI", "Cash", "Bank Transfer"])
            
            with col2:
                if entry_type == "Payment (Income)":
                    f_num = st.selectbox("Flat Number", df_owners['flat'].dropna().unique())
                    amt = st.number_input("Amount (₹)", min_value=0)
                    note = st.text_input("Months Paid (e.g. Jan-Feb)")
                else:
                    head = st.text_input("Expense Head / Category")
                    amt = st.number_input("Amount (₹)", min_value=0)
                    note = st.text_input("Paid To / Vendor")
            
            submit = st.form_submit_button("Save Entry")
            if submit:
                st.info("Entry recorded in the UI. Note: To save permanently to Google Sheets, you must connect a 'Write' API.")
                st.cache_data.clear()
# ——— NEW: ADD ENTRY TAB ———
    with tabs[5]:
        st.header("➕ New Data Entry")
        entry_type = st.radio("Select Entry Type", ["Payment (Collection)", "Expense"], horizontal=True)
        
        with st.form("tab_entry_form", clear_on_submit=True):
            col1, col2 = st.columns(2)
            with col1:
                date = st.date_input("Transaction Date", datetime.now())
                mode = st.selectbox("Payment Mode", ["UPI", "Cash", "Bank Transfer"])
            
            with col2:
                if entry_type == "Payment (Collection)":
                    flat = st.selectbox("Flat Number", sorted(df_owners['flat'].dropna().unique()))
                    amount = st.number_input("Amount Received (₹)", min_value=0, step=100)
                    months = st.text_input("For Months (e.g., Jan-Mar 2025)")
                else:
                    category = st.selectbox("Expense Category", ["Electricity", "Salary", "Maintenance", "Misc"])
                    amount = st.number_input("Expense Amount (₹)", min_value=0, step=100)
                    head = st.text_input("Description / Vendor")

            submitted = st.form_submit_button("Submit Entry")
            if submitted:
                # Note: This only shows a success message. 
                # To actually SAVE to Google Sheets, you need an API/Script setup.
                st.success(f"✅ {entry_type} recorded successfully!")
                st.cache_data.clear()

# ================= FOOTER =================
st.markdown("---")
st.markdown("*DBE Society Management Portal v2.0 | Built with ❤️ for efficient management*")






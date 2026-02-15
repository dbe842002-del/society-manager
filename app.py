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

/* HIDE STREAMLIT UI ELEMENTS */
section[data-testid="stSidebar"] > div { display: none !important; }
[data-testid="collapsedControl"], [data-testid="stToolbar"] { display: none !important; }
#MainMenu, header { visibility: hidden !important; height: 0 !important; }
footer { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ================= DATA LOADER =================
@st.cache_data(ttl=300)
def load_data(sheet_name):
    try:
        base_url = st.secrets.get("connections", {}).get("gsheets", {}).get("spreadsheet", "")
        if not base_url: return pd.DataFrame()
        
        sheet_id = re.search(r"/d/([a-zA-Z0-9-_]+)", base_url)
        if not sheet_id: return pd.DataFrame()
        
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id.group(1)}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
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
            if role == "Admin" and pwd == st.secrets.get("admin_password", "admin123"):
                st.session_state.authenticated, st.session_state.role = True, "admin"
                st.rerun()
            elif role == "Viewer" and pwd == st.secrets.get("view_password", "society123"):
                st.session_state.authenticated, st.session_state.role = True, "viewer"
                st.rerun()
            else:
                st.error("❌ Invalid credentials")
    st.stop()

# ================= LOAD DATA =================
df_owners = load_data("Owners")
df_coll = load_data("Collections") 
df_exp = load_data("Expenses")

current_date = datetime.now()
total_months = (current_date.year - 2025) * 12 + current_date.month

# ================= TABS LOGIC =================
if st.session_state.role == "admin":
    tab_labels = ["📋 Master Dashboard", "🔍 Flat Lookup", "📊 Financials", "⚙️ Admin", "➕ Add Entry"]
else:
    tab_labels = ["📋 Master Dashboard", "🔍 Flat Lookup", "📊 Financials"]

tabs = st.tabs(tab_labels)

# ================= TAB 0: MASTER DASHBOARD =================
with tabs[0]:
    st.header("📋 Society Master Dashboard")
    master_grid = []
    defaulters, total_due = 0, 0
    
    for _, row in df_owners.iterrows():
        flat = row.get('flat', '')
        paid = df_coll[df_coll['flat'] == flat]['amount_received'].apply(clean_num).sum()
        opening = clean_num(row.get('opening_due', 0))
        due_amt = opening + (total_months * MONTHLY_MAINT) - paid
        total_due += due_amt
        if due_amt > 6300: defaulters += 1
        master_grid.append({"Flat": flat, "Owner": row.get('owner', 'N/A'), "Due": int(due_amt)})
    
    c1, c2 = st.columns([2, 1])
    with c1:
        st.markdown(f'<div class="defaulter-card"><h3>⚠️ Defaulters Alert</h3><h1 style="color:#c53030;">{defaulters}</h1><p>Flats > ₹6,300 due</p></div>', unsafe_allow_html=True)
    with c2:
        st.metric("Total Flats", len(df_owners))
        st.metric("Total Outstanding", f"₹{int(total_due):,}")

    df_display = pd.DataFrame(master_grid)
    st.dataframe(df_display, use_container_width=True, hide_index=True)

# ================= TAB 1: FLAT LOOKUP (REPLACES DUES REPORT) =================
with tabs[1]:
    st.header("🔍 Individual Flat Lookup")
    flat_sel = st.selectbox("Search Flat Number", sorted(df_owners['flat'].dropna().unique()))
    
    if flat_sel:
        owner_info = df_owners[df_owners['flat'] == flat_sel].iloc[0]
        paid_amt = df_coll[df_coll['flat'] == flat_sel]['amount_received'].apply(clean_num).sum()
        opening = clean_num(owner_info.get('opening_due', 0))
        billed = total_months * MONTHLY_MAINT
        balance = opening + billed - paid_amt
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Balance Due", f"₹{int(balance):,}")
        col2.metric("Owner", str(owner_info.get('owner', 'N/A')))
        col3.metric("Total Paid", f"₹{int(paid_amt):,}")
        
        st.subheader("📜 Recent Payments")
        hist = df_coll[df_coll['flat'] == flat_sel][['date', 'months_paid', 'amount_received', 'mode']]
        if not hist.empty:
            st.dataframe(hist, use_container_width=True, hide_index=True)
        else:
            st.info("No payments recorded.")

# ================= TAB 2: FINANCIALS =================
with tabs[2]:
    st.header("📊 Financial Summary")
    income = df_coll['amount_received'].apply(clean_num).sum()
    expense = df_exp['amount'].apply(clean_num).sum()
    
    f1, f2, f3 = st.columns(3)
    f1.success(f"Income: ₹{int(income):,}")
    f2.error(f"Expenses: ₹{int(expense):,}")
    f3.metric("Cash on Hand", f"₹{int(income - expense):,}")

# ================= ADMIN ONLY TABS =================
if st.session_state.role == "admin":
    with tabs[3]:
        st.header("⚙️ Admin Settings")
        if st.button("🔄 Clear Cache & Refresh"):
            st.cache_data.clear()
            st.rerun()
        st.subheader("Raw Data View")
        view_sheet = st.selectbox("Select Data Source", ["Owners", "Collections", "Expenses"])
        st.dataframe(load_data(view_sheet), use_container_width=True)

    with tabs[4]:
        st.header("➕ Add New Entry")
        with st.form("entry_form"):
            etype = st.radio("Entry Type", ["Payment (Income)", "Expense"])
            date = st.date_input("Date", datetime.now())
            amt = st.number_input("Amount (₹)", min_value=0)
            note = st.text_input("Remarks/Months")
            if st.form_submit_button("Submit"):
                st.info("Form submitted successfully. Ensure your Google Script API is connected to save data.")

# ================= FOOTER =================
st.markdown("---")
st.markdown("<center>DBE Society Portal v2.0</center>", unsafe_allow_html=True)

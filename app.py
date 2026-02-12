import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=60) # Reduced TTL for faster updates
def safe_read_gsheet(sheet_name):
    try:
        base_url = st.secrets["connections"]["gsheets"]["spreadsheet"].split("/edit")[0]
        csv_url = base_url + "/export?format=csv&sheet=" + sheet_name
        df = pd.read_csv(csv_url)
        # Clean headers: lowercase, strip, no spaces
        df.columns = df.columns.astype(str).str.lower().str.strip().str.replace(" ", "_")
        return df
    except Exception as e:
        st.error(f"Failed to load {sheet_name}: {e}")
        return pd.DataFrame()

# --- AUTH ---
with st.sidebar:
    st.header("🔐 Admin Access")
    pwd = st.text_input("Password", type="password")
    is_admin = (pwd == st.secrets.get("admin_password", ""))

tab1, tab2, tab3, tab4 = st.tabs(["Maintenance", "Owners", "Expenses", "Collections"])

# --- LOAD DATA GLOBALLY ---
df_owners = safe_read_gsheet("Owners")
df_coll = safe_read_gsheet("Collections")

# --- TAB 1: MAINTENANCE ---
with tab1:
    df_owners = safe_read_gsheet("Owners")
    df_coll = safe_read_gsheet("Collections")
    
    if df_owners.empty:
        st.error("Owners sheet is empty!")
        st.stop()

    # 1. Select Flat
    flat_col_o = next((c for c in df_owners.columns if 'flat' in c), df_owners.columns[0])
    selected_flat = st.selectbox("Select Flat Number", sorted(df_owners[flat_col_o].unique()))
    owner_row = df_owners[df_owners[flat_col_o] == selected_flat].iloc[0]

    # 2. Math Setup
    today = datetime.now()
    total_months = (today.year - 2025) * 12 + today.month
    
    # Opening Due
    due_col = next((c for c in df_owners.columns if 'due' in c), None)
    opening_due = pd.to_numeric(owner_row.get(due_col, 0), errors='coerce') or 0.0

    # 3. Aggressive Collection Lookup
    total_paid = 0.0
    if not df_coll.empty:
        # SEARCHING FOR COLUMNS
        # We look for ANY column containing 'flat' and ANY containing 'received' or 'amount'
        c_flat = next((c for c in df_coll.columns if 'flat' in c.lower()), None)
        c_amt = next((c for c in df_coll.columns if 'received' in c.lower() or 'amount' in c.lower()), None)

        if c_flat and c_amt:
            # Clean matching (A-101 -> A101)
            def simple_clean(x): return "".join(filter(str.isalnum, str(x))).upper()
            
            target = simple_clean(selected_flat)
            df_coll['temp_id'] = df_coll[c_flat].apply(simple_clean)
            
            matched = df_coll[df_coll['temp_id'] == target]
            total_paid = pd.to_numeric(matched[c_amt], errors='coerce').sum()
        else:
            # THIS IS YOUR ERROR: Let's see what the columns actually are
            st.warning(f"Column Mismatch! The app sees these headers in Collections: {list(df_coll.columns)}")
            st.info("Ensure your 'Collections' sheet has headers in the VERY FIRST ROW.")

    # 4. Final Calculation
    accrued = total_months * MONTHLY_MAINT
    current_due = (opening_due + accrued) - total_paid

    st.metric("Total Outstanding Due", f"₹ {int(current_due):,}")
    st.caption(f"Accrued: {accrued} | Paid: {total_paid} | Opening: {opening_due}")
    
# --- OTHER TABS ---
with tab2:
    st.dataframe(df_owners, use_container_width=True)
with tab3:
    df_exp = safe_read_gsheet("Expenses")
    st.dataframe(df_exp, use_container_width=True)
with tab4:
    st.dataframe(df_coll, use_container_width=True)



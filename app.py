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
        st.error("Owners sheet is empty or missing!")
        st.stop()

    # --- 1. Selection ---
    flat_col = next((c for c in df_owners.columns if 'flat' in c), df_owners.columns[0])
    selected_flat = st.selectbox("Select Flat", sorted(df_owners[flat_col].unique()))
    owner_row = df_owners[df_owners[flat_col] == selected_flat].iloc[0]

    # --- 2. The Math Engine ---
    today = datetime.now()
    total_months = (today.year - 2025) * 12 + today.month # Jan 2025 to now
    
    # Get Opening Due
    due_col = next((c for c in df_owners.columns if 'due' in c), None)
    opening_due = pd.to_numeric(owner_row.get(due_col, 0), errors='coerce')
    opening_due = 0.0 if pd.isna(opening_due) else float(opening_due)

    # --- 3. THE FIX: Aggressive Payment Search ---
    total_paid = 0.0
    if not df_coll.empty:
        # Find headers regardless of capitalization
        c_flat_col = next((c for c in df_coll.columns if 'flat' in c), None)
        c_amt_col = next((c for c in df_coll.columns if 'received' in c or 'amount' in c), None)

        if c_flat_col and c_amt_col:
            # CLEANING: Remove spaces, dashes, dots. "A-101" -> "A101"
            def ultra_clean(x): return "".join(filter(str.isalnum, str(x))).upper()
            
            target_id = ultra_clean(selected_flat)
            df_coll['match_id'] = df_coll[c_flat_col].apply(ultra_clean)
            
            # Filter rows
            matched_rows = df_coll[df_coll['match_id'] == target_id]
            
            # Sum the money
            paid_series = pd.to_numeric(matched_rows[c_amt_col], errors='coerce').fillna(0)
            total_paid = float(paid_series.sum())

            # --- DEBUG BLOCK (Check if this appears) ---
            if total_paid == 0:
                with st.expander("⚠️ Diagnostic: Why is Total Paid 0?"):
                    st.write(f"Looking for Flat ID: `{target_id}`")
                    st.write("First 5 Flat IDs found in your Collections sheet:")
                    st.write(df_coll['match_id'].head().tolist())
                    st.write(f"Column used for Amount: `{c_amt_col}`")
        else:
            st.error("Could not find 'Flat' or 'Amount' columns in Collections tab!")

    # --- 4. Final Display ---
    expected_accrual = total_months * MONTHLY_MAINT
    current_due = (opening_due + expected_accrual) - total_paid

    # Metric Display
    st.metric("Total Outstanding Due", f"₹ {int(current_due):,}", delta=f"Paid: ₹{int(total_paid)}")
    
    st.info(f"Summary: Expected (₹{int(expected_accrual)}) - Paid (₹{int(total_paid)}) + Opening (₹{int(opening_due)})")
# --- OTHER TABS ---
with tab2:
    st.dataframe(df_owners, use_container_width=True)
with tab3:
    df_exp = safe_read_gsheet("Expenses")
    st.dataframe(df_exp, use_container_width=True)
with tab4:
    st.dataframe(df_coll, use_container_width=True)


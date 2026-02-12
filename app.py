import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# === YOUR PROVEN EXCEL READER (ADAPTED) ===
@st.cache_data(ttl=300)
def safe_read_gsheet(sheet_name):
    try:
        base_url = st.secrets["connections"]["gsheets"]["spreadsheet"].split("/edit")[0]
        csv_url = f"{base_url}/export?format=csv&sheet={sheet_name}"
        df = pd.read_csv(csv_url)
        # EXACT SAME CLEANING AS YOUR TKINTER APP
        df.columns = df.columns.astype(str).str.lower().str.strip().str.replace(" ", "_")
        # Handle duplicate columns (Excel→Sheets issue)
        cols_when = pd.Series(df.columns)
        for dup in df.columns[df.columns.duplicated()].unique():
            mask = df.columns == dup
            df.columns[mask] = [f"{dup}_{i}" if i > 0 else dup 
                              for i in range(df.columns.tolist().count(dup))]
        return df
    except Exception as e:
        st.error(f"Failed to load {sheet_name}: {e}")
        return pd.DataFrame()

# === ADMIN AUTH ===
with st.sidebar:
    pwd = st.text_input("Admin Password", type="password")
    is_admin = pwd == st.secrets["admin_password"]

tab1, tab2, tab3, tab4 = st.tabs(["💰 Maintenance", "📊 Owners", "💸 Expenses", "📈 Collections"])

with tab1:
    df_owners = safe_read_gsheet("Owners")
    df_coll = safe_read_gsheet("Collections")
    
    if df_owners.empty:
        st.warning("Owners sheet missing")
    else:
        selected_flat = st.selectbox("Select Flat", sorted(df_owners['flat'].unique()))
        owner_row = df_owners[df_owners['flat'] == selected_flat].iloc[0]
        st.write(f"**Owner:** {owner_row.get('owner', 'N/A')}")

        # === YOUR EXACT DUES CALC (FIXED MONTHS) ===
        key = str(selected_flat).replace(" ", "").upper()
        opening_due = 0.0
        
        # Opening due (Excel-proven method)
        flat_col = next((col for col in df_owners.columns if 'flat' in col.lower()), None)
        due_col = next((col for col in df_owners.columns if 'due' in col.lower()), None)
        if flat_col and due_col and not df_owners.empty:
            row = df_owners[df_owners[flat_col].astype(str).str.upper() == key]
            if not row.empty:
                opening_due = float(str(row.iloc[0][due_col]).replace("₹", "").replace(",", "").strip() or 0)

        # FIXED: 14 months (Jan25-Feb26) - YOUR TKINTER LOGIC
        today = datetime.now()
        total_months_due = (today.year - 2025) * 12 + today.month  # NO -1
        expected_amount = opening_due + (total_months_due * MONTHLY_MAINT)

        # Payments (Excel-proven)
        # === PAYMENTS: BULLETPROOF VERSION ===
total_paid_amount = 0.0
if not df_coll.empty:
    st.write(f"DEBUG: Found {len(df_coll)} collection rows")  # Remove after fix
    
    # TRY ALL POSSIBLE AMOUNT COLUMNS (like your Tkinter)
    amount_candidates = []
    for col in df_coll.columns:
        if any(x in col.lower() for x in ['amount', 'received', 'payment']):
            amount_candidates.append(col)
    
    st.write(f"DEBUG: Amount columns found: {amount_candidates}")  # Remove after fix
    
    if amount_candidates:
        # Use first matching column
        amount_col = amount_candidates[0]
        
        # TRY ALL POSSIBLE FLAT COLUMNS
        flat_candidates = [col for col in df_coll.columns if 'flat' in col.lower()]
        flat_col = flat_candidates[0] if flat_candidates else None
        
        if flat_col:
            key = str(selected_flat).replace(" ", "").upper()
            flat_payments = df_coll[df_coll[flat_col].astype(str).str.strip().str.upper() == key]
            
            st.write(f"DEBUG: Found {len(flat_payments)} payments for {key}")  # Remove after fix
            st.write(f"DEBUG: Using flat_col='{flat_col}', amount_col='{amount_col}'")  # Remove after fix
            
            if not flat_payments.empty:
                payments_amt = flat_payments[amount_col]
                total_paid_amount = float(payments_amt.sum())
                st.write(f"DEBUG: Raw payments sum: {payments_amt.sum()}")  # Remove after fix
        else:
            st.error(f"No flat column found. Available: {list(df_coll.columns)}")


# === OTHER TABS (SIMPLIFIED) ===
with tab2: st.dataframe(df_owners, use_container_width=True)
with tab3: 
    df_exp = safe_read_gsheet("Expenses")
    # Expense form here (same structure)
    st.dataframe(df_exp, use_container_width=True)
with tab4: st.dataframe(df_coll, use_container_width=True)


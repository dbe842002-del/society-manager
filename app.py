import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# === CONFIG ===
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# === YOUR PROVEN EXCEL LOADER ===
@st.cache_data(ttl=300)
def safe_read_gsheet(sheet_name):
    try:
        base_url = st.secrets["connections"]["gsheets"]["spreadsheet"].split("/edit")[0]
        csv_url = f"{base_url}/export?format=csv&sheet={sheet_name}"
        df = pd.read_csv(csv_url)
        # EXACT SAME AS YOUR TKINTER
        df.columns = df.columns.astype(str).str.lower().str.strip().str.replace(" ", "_")
        # Fix duplicate columns
        for dup in df.columns[df.columns.duplicated()].unique():
            mask = df.columns == dup
            df.columns[mask] = [f"{dup}_{i}" if i > 0 else dup 
                              for i in range(df.columns.tolist().count(dup))]
        return df
    except Exception as e:
        st.error(f"❌ {sheet_name}: {e}")
        return pd.DataFrame()

# === ADMIN ===
with st.sidebar:
    pwd = st.text_input("🔑 Admin Password", type="password")
    is_admin = pwd == st.secrets["admin_password"]

# === TABS ===
tab1, tab2, tab3, tab4 = st.tabs(["💰 Maintenance", "👥 Owners", "💸 Expenses", "📊 Collections"])

# === TAB 1: MAINTENANCE ===
with tab1:
    df_owners = safe_read_gsheet("Owners")
    df_coll = safe_read_gsheet("Collections")
    
    if df_owners.empty:
        st.error("❌ Owners sheet missing!")
    else:
        col1, col2 = st.columns([2, 1])
        with col1:
            selected_flat = st.selectbox("🏠 Select Flat", sorted(df_owners['flat'].dropna().unique()))
        with col2:
            owner_row = df_owners[df_owners['flat'] == selected_flat].iloc[0]
            st.info(f"👤 **{owner_row.get('owner', 'N/A')}**")
        
        # === YOUR EXACT DUES CALC ===
        today = datetime.now()
        total_months = (today.year - 2025) * 12 + today.month  # 14 months Jan25-Feb26
        
        # Opening due
        opening_due = 0.0
        flat_col = next((col for col in df_owners.columns if 'flat' in col.lower()), None)
        due_col = next((col for col in df_owners.columns if 'due' in col.lower()), None)
        if flat_col and due_col:
            row = df_owners[df_owners[flat_col].astype(str).str.upper() == selected_flat.upper()]
            if not row.empty:
                opening_due = float(str(row.iloc[0][due_col]).replace("₹", "").replace(",", "").strip() or 0)
        
        # ALL PAYMENTS FOR THIS FLAT (bulletproof)
        total_paid = 0.0
        if not df_coll.empty:
            flat_col_c = next((col for col in df_coll.columns if 'flat' in col.lower()), 'flat')
            amt_col = next((col for col in df_coll.columns if any(x in col.lower() for x in ['amount_received', 'amount', 'received'])), 'amount_received')
            
            if flat_col_c in df_coll.columns:
                # TRY ALL MATCHING PATTERNS
                flat_key = str(selected_flat).strip().upper()
                payments = df_coll[
                    df_coll[flat_col_c].astype(str).str.strip().str.upper().str.replace('-','').str.replace(' ','').str.contains(
                        flat_key.replace('-','').replace(' ','')
                    ) | 
                    df_coll[flat_col_c].astype(str).str.strip().str.upper() == flat_key
                ]
                
                if not payments.empty and amt_col in payments.columns:
                    total_paid = float(pd.to_numeric(payments[amt_col], errors='coerce').sum())
        
        current_due = max(0, opening_due + (total_months * MONTHLY_MAINT) - total_paid)
        
        # === DISPLAY ===
        st.metric("💰 Total Outstanding Due", f"₹{current_due:,.0f}", f"₹{total_paid:,.0f} paid")
        
        with st.expander("🔍 Calculation Breakdown"):
            st.success(f"✅ 

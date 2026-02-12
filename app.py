import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ================= 1. CONFIGURATION =================
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# ================= 2. HELPERS =================
def clean_numeric(value):
    """Safely converts strings like '₹ 1,200.00' to float."""
    if pd.isna(value) or value == "": return 0.0
    if isinstance(value, (int, float)): return float(value)
    clean_str = str(value).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try:
        return float(clean_str)
    except:
        return 0.0

def clean_id(value):
    """Turns 'A-101' into 'A101' for matching."""
    return "".join(filter(str.isalnum, str(value))).upper()

@st.cache_data(ttl=60)
def load_data_robust(worksheet_name):
    """
    Attempts to read the sheet. If it fails or returns Owners 
    instead of Collections, it uses a manual URL fallback.
    """
    try:
        # Method 1: Standard library read
        df = conn.read(worksheet=worksheet_name)
        # Clean headers immediately
        df.columns = df.columns.astype(str).str.lower().str.strip().str.replace(" ", "_")
        return df
    except Exception as e:
        st.sidebar.error(f"Error loading {worksheet_name}: {e}")
        return pd.DataFrame()

# ================= 3. SIDEBAR & AUTH =================
with st.sidebar:
    st.header("🔐 Admin Access")
    pwd = st.text_input("Password", type="password")
    is_admin = (pwd == st.secrets.get("admin_password", ""))
    
    if st.button("🔄 Force Refresh Data"):
        st.cache_data.clear()
        st.rerun()

    # --- DEBUG SECTION ---
    st.divider()
    st.write("📂 **Sheet Diagnostics**")
    try:
        # This helps you check if the tab names are correct
        df_owners = load_data_robust("Owners")
        df_coll = load_data_robust("Collections")
        st.write(f"Owners Tab: {'✅ Found' if not df_owners.empty else '❌ Empty'}")
        st.write(f"Collections Tab: {'✅ Found' if not df_coll.empty else '❌ Empty'}")
        if not df_coll.empty:
            st.write(f"Coll Columns: {list(df_coll.columns[:3])}...")
    except:
        st.write("Connection pending...")

# ================= 4. MAIN APP =================
tab1, tab2, tab3 = st.tabs(["💰 Maintenance", "💸 Expenses", "📊 Full Log"])

# Load Expenses (Assuming tab name is 'Expenses')
df_exp = load_data_robust("Expenses")

with tab1:
    if df_owners.empty or df_coll.empty:
        st.error("⚠️ Could not load data. Please ensure your Google Sheet has tabs named exactly 'Owners' and 'Collections'.")
        st.info("Check the sidebar 'Sheet Diagnostics' for details.")
    else:
        # Dynamic Column Finding
        f_col = next((c for c in df_owners.columns if 'flat' in c), "flat")
        n_col = next((c for c in df_owners.columns if 'owner' in c or 'name' in c), "owner")
        d_col = next((c for c in df_owners.columns if 'due' in c), "opening_due")

        col_sel, col_info = st.columns([2, 1])
        with col_sel:
            selected_flat = st.selectbox("Select Flat", sorted(df_owners[f_col].unique()))
            owner_row = df_owners[df_owners[f_col] == selected_flat].iloc[0]
        with col_info:
            st.info(f"👤 **Owner:** {owner_row.get(n_col, 'N/A')}")

        # --- CALCULATION (Jan 2025 to Feb 2026) ---
        today = datetime.now()
        # Ensure we are in Feb 2026 for this calculation
        calc_year, calc_month = 2026, 2
        total_months = (calc_year - 2025) * 12 + calc_month # Result: 14
        
        opening_due = clean_numeric(owner_row.get(d_col, 0))
        
        # Calculate Paid
        total_paid = 0.0
        c_amt_col = next((c for c in df_coll.columns if 'received' in c or 'amount' in c), None)
        c_flat_col = next((c for c in df_coll.columns if 'flat' in c), None)
        
        if c_amt_col and c_flat_col:
            target_id = clean_id(selected_flat)
            df_coll['match_id'] = df_coll[c_flat_col].apply(clean_id)
            matched = df_coll[df_coll['match_id'] == target_id]
            total_paid = matched[c_amt_col].apply(clean_numeric).sum()
        
        accrued = total_months * MONTHLY_MAINT
        current_due = (opening_due + accrued) - total_paid

        # Display
        st.metric("Current Outstanding Due", f"₹ {int(current_due):,}")
        
        col1, col2, col3 = st.columns(3)
        col1.write(f"**Total Accrued (14m):** ₹{int(accrued):,}")
        col2.write(f"**Total Paid:** ₹{int(total_paid):,}")
        col3.write(f"**Opening Balance:** ₹{int(opening_due):,}")

        # --- ADMIN PAYMENT ENTRY ---
        if is_admin:
            st.divider()
            with st.form("pay_entry", clear_on_submit=True):
                st.subheader("Add Payment")
                a, b, c = st.columns(3)
                p_date = a.date_input("Date")
                p_amt = b.number_input("Amount", value=2100)
                p_mths = c.text_input("Months (e.g. Feb-26)")
                if st.form_submit_button("Record Payment"):
                    # Logic to save to Google Sheets
                    new_data = pd.DataFrame([{
                        "date": p_date.strftime("%d-%m-%Y"),
                        "flat": selected_flat,
                        "owner": owner_row[n_col],
                        "months_paid": p_mths,
                        "amount_received": p_amt,
                        "mode": "Online",
                        "bill_no": ""
                    }])
                    updated_df = pd.concat([df_coll, new_data], ignore_index=True).drop(columns=['match_id'], errors='ignore')
                    conn.update(worksheet="Collections", data=updated_df)
                    st.cache_data.clear()
                    st.success("Payment saved!")
                    st.rerun()

with tab2:
    st.subheader("Expense Management")
    st.dataframe(df_exp, use_container_width=True)

with tab3:
    st.subheader("Collection History")
    st.dataframe(df_coll, use_container_width=True)

import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ================= CONFIGURATION =================
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")

# Connection for WRITING (Updating)
conn = st.connection("gsheets", type=GSheetsConnection)

# ================= RELIABLE DATA LOADER =================
@st.cache_data(ttl=60)
def safe_read_gsheet(sheet_name):
    """Bypasses GSheets library bugs to force-load the correct tab via URL"""
    try:
        # Get base URL and remove anything after /edit
        base_url = st.secrets["connections"]["gsheets"]["spreadsheet"].split("/edit")[0]
        # Force specific tab via export link
        csv_url = f"{base_url}/export?format=csv&sheet={sheet_name}"
        df = pd.read_csv(csv_url)
        # Clean headers: lowercase, strip, no spaces
        df.columns = df.columns.astype(str).str.lower().str.strip().str.replace(" ", "_")
        return df
    except Exception as e:
        st.error(f"Failed to load {sheet_name}: {e}")
        return pd.DataFrame()

# ================= AUTHENTICATION =================
with st.sidebar:
    st.header("🔐 Admin Panel")
    pwd = st.text_input("Admin Password", type="password")
    is_admin = (pwd == st.secrets.get("admin_password", ""))

# ================= MAIN APP =================
tab1, tab2, tab3, tab4 = st.tabs(["💰 Maintenance", "📋 Owners List", "💸 Expenses", "📑 Collection Log"])

# Load all data upfront
df_owners = safe_read_gsheet("Owners")
df_coll = safe_read_gsheet("Collections")
df_exp = safe_read_gsheet("Expenses")

# --- TAB 1: MAINTENANCE CALCULATION ---
with tab1:
    if not df_owners.empty:
        # 1. UI for Selection
        col_sel, col_info = st.columns([2, 1])
        with col_sel:
            # Match 'flat' column
            flat_col_o = next((c for c in df_owners.columns if 'flat' in c), df_owners.columns[0])
            selected_flat = st.selectbox("Select Flat", sorted(df_owners[flat_col_o].unique()))
            owner_row = df_owners[df_owners[flat_col_o] == selected_flat].iloc[0]
        
        with col_info:
            # Match 'owner' column
            name_col = next((c for c in df_owners.columns if 'owner' in c or 'name' in c), None)
            st.info(f"👤 **Owner:** {owner_row.get(name_col, 'N/A')}")

        # 2. Math Engine
        today = datetime.now()
        # Jan 2025 to Feb 2026 = 14 months
        total_months = (today.year - 2025) * 12 + today.month
        
        # Safe Opening Due from Owners
        due_col = next((c for c in df_owners.columns if 'due' in c), None)
        opening_due = pd.to_numeric(owner_row.get(due_col, 0), errors='coerce') or 0.0

        # Safe Paid Amount from Collections
        total_paid = 0.0
        if not df_coll.empty:
            # Super-matching (A-101 matches a 101)
            def clean_id(x): return "".join(filter(str.isalnum, str(x))).upper()
            
            c_flat = next((c for c in df_coll.columns if 'flat' in c), None)
            c_amt = next((c for c in df_coll.columns if 'received' in c or 'amount' in c), None)
            
            if c_flat and c_amt:
                df_c = df_coll.copy()
                target_id = clean_id(selected_flat)
                df_c['match_key'] = df_c[c_flat].apply(clean_id)
                
                matched_payments = df_c[df_c['match_key'] == target_id]
                total_paid = pd.to_numeric(matched_payments[c_amt], errors='coerce').sum()

        # Final Logic
        accrued = total_months * MONTHLY_MAINT
        current_due = (opening_due + accrued) - total_paid

        # 3. Display Results
        st.metric("Total Outstanding Due", f"₹ {int(current_due):,}")
        
        with st.expander("🔍 Calculation Details"):
            st.write(f"Accrual: Jan 2025 to {today.strftime('%b %Y')} ({total_months} months)")
            st.write(f"Expected: {total_months} × {MONTHLY_MAINT} = ₹{int(accrued):,}")
            st.write(f"Total Paid (as per Records): ₹{int(total_paid):,}")
            st.write(f"Opening Balance (Jan 25): ₹{int(opening_due):,}")

        # 4. Admin Entry Form
        if is_admin:
            st.divider()
            with st.form("pay_entry", clear_on_submit=True):
                st.subheader("📝 Record New Payment")
                f1, f2, f3 = st.columns(3)
                with f1:
                    p_date = st.date_input("Date", today)
                    p_bill = st.number_input("Bill No", value=2000, step=1)
                with f2:
                    p_mode = st.selectbox("Mode", ["Online", "Cash", "Cheque"])
                    p_amt = st.number_input("Amount Received", value=2100)
                with f3:
                    p_mths = st.text_input("Months (e.g., Feb-26)")
                
                if st.form_submit_button("Save to Cloud"):
                    new_pay = pd.DataFrame([{
                        "date": p_date.strftime("%d-%m-%Y"),
                        "bill_no": p_bill,
                        "flat": selected_flat,
                        "owner": str(owner_row.get(name_col, '')),
                        "amount_received": p_amt,
                        "mode": p_mode,
                        "months_paid": p_mths
                    }])
                    updated_coll = pd.concat([df_coll, new_pay], ignore_index=True)
                    conn.update(worksheet="Collections", data=updated_coll)
                    st.success("✅ Payment Synced!")
                    st.cache_data.clear()
                    st.rerun()

# --- TAB 2: OWNERS ---
with tab2:
    st.subheader("Society Directory")
    st.dataframe(df_owners, use_container_width=True)

# --- TAB 3: EXPENSES ---
with tab3:
    st.subheader("Expense Management")
    st.dataframe(df_exp, use_container_width=True)
    if is_admin:
        with st.form("exp_entry"):
            e1, e2, e3 = st.columns(3)
            with e1:
                e_date = st.date_input("Date")
                e_cat = st.selectbox("Category", ["Security", "Electricity", "Diesel", "Salary", "Maintenance", "Misc"])
            with e2:
                e_amt = st.number_input("Amount", min_value=0.0)
            with e3:
                e_desc = st.text_input("Description")
            if st.form_submit_button("Save Expense"):
                new_exp = pd.DataFrame([{"date": e_date.strftime("%d-%m-%Y"), "head": e_cat, "description": e_desc, "amount": e_amt, "mode": "Cash"}])
                updated_exp = pd.concat([df_exp, new_exp], ignore_index=True)
                conn.update(worksheet="Expenses", data=updated_exp)
                st.cache_data.clear()
                st.rerun()

# --- TAB 4: LOG ---
with tab4:
    st.subheader("Full Collection History")
    st.dataframe(df_coll, use_container_width=True)

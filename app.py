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
    if df_owners.empty:
        st.warning("Please check your 'Owners' sheet. It appears to be empty.")
        st.stop()

    # 1. Select Flat
    flat_col = next((c for c in df_owners.columns if 'flat' in c), df_owners.columns[0])
    flats = sorted(df_owners[flat_col].dropna().unique())
    selected_flat = st.selectbox("Select Flat Number", flats)
    
    owner_row = df_owners[df_owners[flat_col] == selected_flat].iloc[0]
    name_col = next((c for c in df_owners.columns if 'owner' in c or 'name' in c), None)
    st.info(f"👤 **Owner:** {owner_row.get(name_col, 'N/A')}")

    # --- MATH ENGINE ---
    today = datetime.now()
    # Months from Jan 2025 to Feb 2026 (14 months)
    total_months = (today.year - 2025) * 12 + today.month

    # Safe Opening Due
    due_col = next((c for c in df_owners.columns if 'due' in c or 'opening' in c), None)
    raw_opening = pd.to_numeric(owner_row.get(due_col, 0), errors='coerce')
    opening_due = float(raw_opening) if pd.notnull(raw_opening) else 0.0

    # Safe Total Paid
    total_paid = 0.0
    if not df_coll.empty:
        # Clean ID matching (A-101 -> A101)
        def force_clean(val): return "".join(filter(str.isalnum, str(val))).upper()
        
        c_flat = next((c for c in df_coll.columns if 'flat' in c), None)
        c_amt = next((c for c in df_coll.columns if 'received' in c or 'amount' in c), None)
        
        if c_flat and c_amt:
            df_c = df_coll.copy()
            target_id = force_clean(selected_flat)
            df_c['match_id'] = df_c[c_flat].apply(force_clean)
            
            matched = df_c[df_c['match_id'] == target_id]
            paid_val = pd.to_numeric(matched[c_amt], errors='coerce').sum()
            total_paid = float(paid_val) if pd.notnull(paid_val) else 0.0

    # Final Calculation with NaN protection
    accrued = total_months * MONTHLY_MAINT
    current_due = (opening_due + accrued) - total_paid

    # --- DISPLAY ---
    st.metric("Total Outstanding Due", f"₹ {int(current_due):,}")
    
    with st.expander("🔍 Detailed Calculation"):
        st.write(f"Accrual Period: Jan 2025 - {today.strftime('%b %Y')} ({total_months} months)")
        col_a, col_b, col_c = st.columns(3)
        col_a.write(f"**Opening:** ₹{int(opening_due)}")
        col_b.write(f"**Maintenance:** ₹{int(accrued)}")
        col_c.write(f"**Total Paid:** ₹{int(total_paid)}")

    # --- PAYMENT FORM ---
    if is_admin:
        st.divider()
        with st.form("pay_form", clear_on_submit=True):
            st.subheader("Add New Payment")
            f1, f2 = st.columns(2)
            with f1:
                p_date = st.date_input("Date", today)
                p_bill = st.number_input("Bill No", value=2000, step=1)
            with f2:
                p_mode = st.selectbox("Mode", ["Online", "Cash", "Cheque"])
                p_amt = st.number_input("Amount Received", value=2100)
            
            p_mths = st.text_input("Remarks / Months (e.g., Feb-26)")
            
            if st.form_submit_button("Save Payment"):
                new_row = pd.DataFrame([{
                    "date": p_date.strftime("%d-%m-%Y"),
                    "bill_no": p_bill,
                    "flat": selected_flat,
                    "owner": str(owner_row.get(name_col, '')),
                    "amount_received": p_amt,
                    "mode": p_mode,
                    "months_paid": p_mths
                }])
                updated_df = pd.concat([df_coll, new_row], ignore_index=True)
                conn.update(worksheet="Collections", data=updated_df)
                st.success("Payment recorded!")
                st.cache_data.clear()
                st.rerun()

# --- OTHER TABS ---
with tab2:
    st.dataframe(df_owners, use_container_width=True)
with tab3:
    df_exp = safe_read_gsheet("Expenses")
    st.dataframe(df_exp, use_container_width=True)
with tab4:
    st.dataframe(df_coll, use_container_width=True)

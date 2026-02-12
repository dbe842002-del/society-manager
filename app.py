import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ================= 1. CONFIGURATION =================
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")

# Official Connection
conn = st.connection("gsheets", type=GSheetsConnection)

# ================= 2. HELPERS =================
def clean_numeric(value):
    """Safely converts currency strings like '₹ 1,200' to 1200.0"""
    if pd.isna(value) or value == "": return 0.0
    if isinstance(value, (int, float)): return float(value)
    # Remove currency symbols and formatting
    clean_str = str(value).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try:
        return float(clean_str)
    except:
        return 0.0

def clean_id(value):
    """Standardizes IDs: 'A-101' -> 'A101' to prevent matching errors"""
    return "".join(filter(str.isalnum, str(value))).upper()

@st.cache_data(ttl=300)
def load_tab(worksheet_name):
    """Uses the library's built-in method to fetch specific tabs"""
    try:
        # worksheet parameter is the key to fixing your 'Owners loading twice' bug
        df = conn.read(worksheet=worksheet_name)
        # Standardize headers
        df.columns = df.columns.astype(str).str.lower().str.strip().str.replace(" ", "_")
        return df
    except Exception as e:
        st.error(f"Error loading tab '{worksheet_name}': {e}")
        return pd.DataFrame()

# ================= 3. AUTH =================
with st.sidebar:
    st.header("🔐 Admin Access")
    pwd = st.text_input("Password", type="password")
    is_admin = (pwd == st.secrets.get("admin_password", ""))
    if st.button("🔄 Refresh Data"):
        st.cache_data.clear()
        st.rerun()

# ================= 4. DATA LOADING =================
# We load them using the library's worksheet-aware reader
df_owners = load_tab("Owners")
df_coll = load_tab("Collections")
df_exp = load_tab("Expenses")

tab1, tab2, tab3, tab4 = st.tabs(["💰 Maintenance", "📋 Owners", "💸 Expenses", "📊 Report"])

# ================= TAB 1: MAINTENANCE =================
with tab1:
    if df_owners.empty or df_coll.empty:
        st.warning("Loading data from Google Sheets... If this takes too long, verify your Tab names are 'Owners' and 'Collections'.")
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
            st.info(f"**Owner:** {owner_row.get(n_col, 'N/A')}")

        # --- CALCULATION ENGINE ---
        today = datetime.now()
        # Period: Jan 2025 to NOW
        total_months = (today.year - 2025) * 12 + today.month
        
        # 1. Clean Opening Due from Owners Sheet
        opening_due = clean_numeric(owner_row.get(d_col, 0))
        
        # 2. Total Paid from Collections Sheet
        total_paid = 0.0
        # Verify we have the correct Collections data
        if 'amount_received' in df_coll.columns:
            c_flat = next((c for c in df_coll.columns if 'flat' in c), "flat")
            c_amt = "amount_received"
            
            target_id = clean_id(selected_flat)
            df_match = df_coll.copy()
            df_match['match_id'] = df_match[c_flat].apply(clean_id)
            
            matched = df_match[df_match['match_id'] == target_id]
            total_paid = matched[c_amt].apply(clean_numeric).sum()
        else:
            st.error("Collections tab loaded but 'amount_received' column not found.")

        # 3. Final Calculation
        accrued = total_months * MONTHLY_MAINT
        current_due = (opening_due + accrued) - total_paid

        # --- DISPLAY ---
        st.metric("Total Outstanding Due", f"₹ {int(current_due):,}")
        
        with st.expander("🔍 View Detailed Calculation"):
            st.write(f"**Period:** Jan 2025 to {today.strftime('%b %Y')} ({total_months} months)")
            st.write(f"**Maintenance Accrued:** {total_months} × ₹2,100 = ₹{int(accrued):,}")
            st.write(f"**Total Payments Found:** ₹{int(total_paid):,}")
            st.write(f"**Opening Balance (Jan 25):** ₹{int(opening_due):,}")

        # --- PAYMENT ENTRY FORM ---
        if is_admin:
            st.divider()
            with st.form("pay_form", clear_on_submit=True):
                st.subheader("Record a New Payment")
                c1, c2, c3 = st.columns(3)
                with c1:
                    p_date = st.date_input("Payment Date")
                    p_bill = st.number_input("Bill No", value=1001, step=1)
                with c2:
                    p_mode = st.selectbox("Mode", ["Online", "Cash", "Cheque"])
                    p_amt = st.number_input("Amount Paid", value=2100)
                with c3:
                    p_mths = st.text_input("For Months (e.g., Feb-26)")
                
                if st.form_submit_button("Submit Payment"):
                    new_row = pd.DataFrame([{
                        "date": p_date.strftime("%d-%m-%Y"),
                        "flat": selected_flat,
                        "owner": owner_row[n_col],
                        "months_paid": p_mths,
                        "amount_received": p_amt,
                        "mode": p_mode,
                        "bill_no": p_bill
                    }])
                    updated = pd.concat([df_coll, new_row], ignore_index=True)
                    conn.update(worksheet="Collections", data=updated)
                    st.cache_data.clear()
                    st.success("✅ Payment Saved!")
                    st.rerun()

# ================= TAB 2: OWNERS =================
with tab2:
    st.dataframe(df_owners, use_container_width=True)

# ================= TAB 3: EXPENSES =================
with tab3:
    st.dataframe(df_exp, use_container_width=True)

# ================= TAB 4: REPORT =================
with tab4:
    total_in = df_coll['amount_received'].apply(clean_numeric).sum() if not df_coll.empty else 0
    total_out = df_exp['amount'].apply(clean_numeric).sum() if not df_exp.empty else 0
    
    col1, col2, col3 = st.columns(3)
    col1.metric("Total Collections", f"₹ {int(total_in):,}")
    col2.metric("Total Expenses", f"₹ {int(total_out):,}")
    col3.metric("Balance in Hand", f"₹ {int(total_in - total_out):,}")

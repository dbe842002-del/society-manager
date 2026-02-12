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
    """Handles ₹, commas, and NaN values."""
    if pd.isna(value) or value == "": return 0.0
    if isinstance(value, (int, float)): return float(value)
    clean_str = str(value).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try:
        return float(clean_str)
    except:
        return 0.0

def clean_id(value):
    """Standardizes IDs: 'A-101' -> 'A101'"""
    return "".join(filter(str.isalnum, str(value))).upper()

@st.cache_data(ttl=60)
def safe_read_gsheet(sheet_name):
    """Direct CSV export to force-load the correct tab."""
    try:
        base_url = st.secrets["connections"]["gsheets"]["spreadsheet"].split("/edit")[0]
        csv_url = f"{base_url}/export?format=csv&sheet={sheet_name}"
        df = pd.read_csv(csv_url)
        # Clean headers: lowercase and underscores
        df.columns = df.columns.astype(str).str.lower().str.strip().str.replace(" ", "_")
        return df
    except Exception as e:
        st.error(f"Failed to load {sheet_name}: {e}")
        return pd.DataFrame()

# ================= 3. AUTH =================
with st.sidebar:
    st.header("🔐 Admin Access")
    pwd = st.text_input("Password", type="password")
    is_admin = (pwd == st.secrets.get("admin_password", ""))

# ================= 4. DATA LOADING =================
df_owners = safe_read_gsheet("Owners")
df_coll = safe_read_gsheet("Collections")
df_exp = safe_read_gsheet("Expenses")

tab1, tab2, tab3, tab4 = st.tabs(["💰 Maintenance", "💸 Expenses", "📋 Records", "📊 Report"])

# ================= TAB 1: MAINTENANCE =================
with tab1:
    if not df_owners.empty:
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

        # --- MATH ENGINE ---
        today = datetime.now()
        total_months = (today.year - 2025) * 12 + today.month
        
        opening_due = clean_numeric(owner_row.get(d_col, 0))
        
        total_paid = 0.0
        if not df_coll.empty:
            # FIX: More robust column detection for Collections
            c_flat = next((c for c in df_coll.columns if 'flat' in c), None)
            # Look for 'received' first, then 'amount'
            c_amt = next((c for c in df_coll.columns if 'received' in c), 
                         next((c for c in df_coll.columns if 'amount' in c), None))
            
            if c_flat and c_amt:
                target_id = clean_id(selected_flat)
                # Create match column
                df_match = df_coll.copy()
                df_match['match_id'] = df_match[c_flat].apply(clean_id)
                
                matched = df_match[df_match['match_id'] == target_id]
                total_paid = matched[c_amt].apply(clean_numeric).sum()
            else:
                st.sidebar.error(f"Missing columns in Collections. Found: {list(df_coll.columns)}")

        accrued = total_months * MONTHLY_MAINT
        current_due = (opening_due + accrued) - total_paid

        st.metric("Total Outstanding Due", f"₹ {int(current_due):,}")
        
        with st.expander("🔍 Breakdown"):
            st.write(f"Period: Jan 2025 - {today.strftime('%b %Y')} ({total_months} months)")
            st.write(f"Accrued: ₹ {int(accrued):,}")
            st.write(f"Paid: ₹ {int(total_paid):,}")
            st.write(f"Opening: ₹ {int(opening_due):,}")

        if is_admin:
            st.divider()
            with st.form("pay_form", clear_on_submit=True):
                st.subheader("Add Payment Record")
                c1, c2, c3 = st.columns(3)
                with c1:
                    p_date = st.date_input("Date")
                    p_bill = st.number_input("Bill No", value=1001)
                with c2:
                    p_mode = st.selectbox("Mode", ["Online", "Cash", "Cheque"])
                    p_amt = st.number_input("Amount", value=2100)
                with c3:
                    p_mths = st.text_input("Months Paid (e.g. Feb-26)")
                
                if st.form_submit_button("Save Payment"):
                    # Use the EXACT headers that were detected
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
                    st.success("Payment saved!")
                    st.cache_data.clear()
                    st.rerun()

# --- OTHER TABS (SIMPLIFIED) ---
with tab2:
    st.dataframe(df_exp, use_container_width=True)
with tab3:
    st.write("### Owners Database")
    st.dataframe(df_owners, use_container_width=True)
    st.write("### Collection History")
    st.dataframe(df_coll, use_container_width=True)
with tab4:
    st.metric("Total Collections", f"₹ {int(df_coll[next((c for c in df_coll.columns if 'received' in c or 'amount' in c), df_coll.columns[0])].apply(clean_numeric).sum()):,}")

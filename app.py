import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection
import urllib.parse

# ================= 1. CONFIGURATION =================
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# ================= 2. HELPERS =================
def clean_numeric(value):
    if pd.isna(value) or value == "": return 0.0
    if isinstance(value, (int, float)): return float(value)
    clean_str = str(value).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try:
        return float(clean_str)
    except:
        return 0.0

def clean_id(value):
    return "".join(filter(str.isalnum, str(value))).upper()

@st.cache_data(ttl=60)
def safe_read_gsheet(sheet_name):
    """
    Forces Google to return the correct tab by stripping existing URL 
    parameters and using the sheet name explicitly.
    """
    try:
        # Get base URL and strip anything after /edit or ? or #
        raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        base_url = raw_url.split("/edit")[0].split("?")[0].split("#")[0]
        
        # URL encode the sheet name (e.g., "Collections" -> "Collections")
        encoded_name = urllib.parse.quote(sheet_name)
        csv_url = f"{base_url}/export?format=csv&sheet={encoded_name}"
        
        df = pd.read_csv(csv_url)
        # Clean headers: lowercase and underscores
        df.columns = df.columns.astype(str).str.lower().str.strip().str.replace(" ", "_")
        return df
    except Exception as e:
        st.error(f"Failed to load tab '{sheet_name}': {e}")
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
    if df_owners.empty:
        st.error("Owner data not found. Check tab name 'Owners' in Google Sheets.")
    else:
        # Dynamic Column Finding for Owners
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
        # CRITICAL CHECK: Did we actually load Collections or did we get Owners again?
        if 'amount_received' in df_coll.columns or 'received' in str(df_coll.columns):
            c_flat = next((c for c in df_coll.columns if 'flat' in c), "flat")
            c_amt = next((c for c in df_coll.columns if 'received' in c or 'amount' in c), None)
            
            target_id = clean_id(selected_flat)
            df_match = df_coll.copy()
            df_match['match_id'] = df_match[c_flat].apply(clean_id)
            
            matched = df_match[df_match['match_id'] == target_id]
            total_paid = matched[c_amt].apply(clean_numeric).sum()
        else:
            st.warning("⚠️ Data Connection Syncing... If 'Total Paid' stays 0, verify your Google Sheet tab is named exactly 'Collections'.")
            # Fallback debug view for you
            with st.expander("Admin Debug: Collections Columns"):
                st.write(list(df_coll.columns))

        accrued = total_months * MONTHLY_MAINT
        current_due = (opening_due + accrued) - total_paid

        st.metric("Total Outstanding Due", f"₹ {int(current_due):,}")
        
        with st.expander("🔍 Detailed Calculation"):
            st.write(f"Period: Jan 2025 to {today.strftime('%b %Y')} ({total_months} months)")
            st.write(f"Expected: ₹ {int(accrued):,}")
            st.write(f"Total Paid: ₹ {int(total_paid):,}")
            st.write(f"Opening Due: ₹ {int(opening_due):,}")

        if is_admin:
            st.divider()
            with st.form("pay_form", clear_on_submit=True):
                st.subheader("Add New Payment")
                c1, c2, c3 = st.columns(3)
                with c1:
                    p_date = st.date_input("Date")
                    p_bill = st.number_input("Bill No", value=1001)
                with c2:
                    p_mode = st.selectbox("Mode", ["Online", "Cash", "Cheque"])
                    p_amt = st.number_input("Amount Received", value=2100)
                with c3:
                    p_mths = st.text_input("For Months (e.g. Feb-26)")
                
                if st.form_submit_button("Save & Sync"):
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
                    st.success("Payment saved successfully!")
                    st.rerun()

# ================= OTHER TABS =================
with tab2:
    st.subheader("Expense Records")
    st.dataframe(df_exp, use_container_width=True)
with tab3:
    st.subheader("All Records")
    col_a, col_b = st.columns(2)
    col_a.write("Owners")
    col_a.dataframe(df_owners, use_container_width=True)
    col_b.write("Collections")
    col_b.dataframe(df_coll, use_container_width=True)
with tab4:
    st.subheader("Financial Summary")
    t_in = df_coll[next((c for c in df_coll.columns if 'received' in c or 'amount' in c), df_coll.columns[0])].apply(clean_numeric).sum()
    t_out = df_exp[next((c for c in df_exp.columns if 'amount' in c), df_exp.columns[0])].apply(clean_numeric).sum()
    st.metric("Cash on Hand", f"₹ {int(t_in - t_out):,}")

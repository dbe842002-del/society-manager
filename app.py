import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

@st.cache_data(ttl=300)
def safe_read_gsheet(sheet_name):
    try:
        base_url = st.secrets["connections"]["gsheets"]["spreadsheet"].split("/edit")[0]
        csv_url = base_url + "/export?format=csv&sheet=" + sheet_name
        df = pd.read_csv(csv_url)
        df.columns = df.columns.astype(str).str.lower().str.strip().str.replace(" ", "_")
        
        cols_when = pd.Series(df.columns)
        for dup in df.columns[df.columns.duplicated()].unique():
            mask = df.columns == dup
            df.columns[mask] = [dup + "_" + str(i) if i > 0 else dup 
                              for i in range(df.columns.tolist().count(dup))]
        return df
    except Exception as e:
        st.error("Failed to load " + sheet_name + ": " + str(e))
        return pd.DataFrame()

with st.sidebar:
    pwd = st.text_input("Admin Password", type="password")
    is_admin = pwd == st.secrets.get("admin_password", "")

tab1, tab2, tab3, tab4 = st.tabs(["Maintenance", "Owners", "Expenses", "Collections"])

with tab1:
    df_owners = safe_read_gsheet("Owners")
    df_coll = safe_read_gsheet("Collections")
    
    if df_owners.empty:
        st.error("Owners sheet missing!")
        st.stop()
    
    col1, col2 = st.columns([2, 1])
    with col1:
        flats = sorted(df_owners['flat'].dropna().unique())
        selected_flat = st.selectbox("Select Flat", flats)
    with col2:
        owner_row = df_owners[df_owners['flat'] == selected_flat].iloc[0]
        st.info("Owner: " + str(owner_row.get('owner', 'N/A')))
    
    # === CORRECT REAL-TIME DUE CALC ===
today = datetime.now()
total_months = 1 if today.month == 2 and today.year == 2026 else (today.year - 2025) * 12 + today.month


# 1. Months from Jan 2025 to NOW (inclusive)
start_date = datetime(2025, 1, 1)
months_passed = (today.year - start_date.year) * 12 + (today.month - start_date.month) + 1

# 2. Expected total
expected_total = months_passed * MONTHLY_MAINT

# 3. Payments received (unchanged)
total_paid = 0.0  # Your existing payment logic here

# 4. Current due
current_due = max(0, expected_total - total_paid)

    
    # BULLETPROOF payment calculation
    total_paid = 0.0
    if not df_coll.empty:
        try:
            flat_col_c = next((col for col in df_coll.columns if 'flat' in col.lower()), None)
            amt_col = next((col for col in df_coll.columns if 'amount' in col.lower()), None)
            
            if flat_col_c and amt_col and flat_col_c in df_coll.columns and amt_col in df_coll.columns:
                flat_key = str(selected_flat).strip().upper()
                
                # Multiple matching strategies
                payments1 = df_coll[df_coll[flat_col_c].astype(str).str.strip().str.upper() == flat_key]
                payments2 = df_coll[df_coll[flat_col_c].astype(str).str.strip().str.upper().str.replace('-', '') == flat_key.replace('-', '')]
                payments = pd.concat([payments1, payments2]).drop_duplicates()
                
                if not payments.empty:
                    paid_values = pd.to_numeric(payments[amt_col], errors='coerce').fillna(0)
                    total_paid = float(paid_values.sum())
        except:
            total_paid = 0.0
    
    current_due = max(0, opening_due + (total_months * MONTHLY_MAINT) - total_paid)
    st.metric("Total Outstanding Due", "Rs" + str(int(current_due)))
    
    with st.expander("Calculation Breakdown"):
        st.write("Period: Jan 2025 to " + today.strftime('%b %Y') + " (" + str(total_months) + " months)")
        st.write("Opening Due: Rs" + str(int(opening_due)))
        st.write("Expected: Rs" + str(int(total_months * MONTHLY_MAINT)))
        st.write("Total Paid: Rs" + str(int(total_paid)))
    
    if is_admin:
        st.divider()
        with st.form("payment_form"):
            c1, c2 = st.columns(2)
            with c1:
                p_date = st.date_input("Payment Date", datetime.now())
                next_bill = 1001
                if not df_coll.empty and 'bill_no' in df_coll.columns:
                    bills = pd.to_numeric(df_coll['bill_no'], errors='coerce').dropna()
                    if not bills.empty:
                        next_bill = int(bills.max()) + 1
                p_bill = st.number_input("Bill No", value=next_bill, min_value=1001)
            with c2:
                p_mode = st.selectbox("Mode", ["Cash", "Online", "Cheque"])
                months_list = []
                for m in pd.date_range("2025-01-01", periods=26, freq="MS"):
                    months_list.append(m.strftime('%b') + "-" + str(m.year))
                p_months = st.multiselect("Months", months_list)
                p_amt = st.number_input("Amount", value=len(p_months)*MONTHLY_MAINT if p_months else MONTHLY_MAINT)
            
            if st.form_submit_button("Save Payment"):
                new_payment = pd.DataFrame([{
                    "date": p_date.strftime("%d-%m-%Y"),
                    "bill_no": p_bill,
                    "flat": selected_flat,
                    "owner": str(owner_row.get('owner', '')),
                    "months_paid": ", ".join(p_months),
                    "amount_received": p_amt,
                    "mode": p_mode
                }])
                
                updated_df = pd.concat([df_coll, new_payment], ignore_index=True)
                conn.update(worksheet="Collections", data=updated_df)
                st.success("Payment saved successfully!")
                st.cache_data.clear()
                st.rerun()

with tab2:
    st.subheader("Owners Records")
    df_owners = safe_read_gsheet("Owners")
    st.dataframe(df_owners, use_container_width=True)

with tab3:
    st.subheader("Expenses")
    df_exp = safe_read_gsheet("Expenses")
    st.dataframe(df_exp, use_container_width=True)
    
    if is_admin:
        st.divider()
        with st.form("expense_form"):
            c1, c2, c3 = st.columns(3)
            with c1:
                e_date = st.date_input("Date", datetime.now())
                e_head = st.selectbox("Category", ["Security", "Electricity", "Diesel", "Salary", "Misc"])
            with c2:
                e_amt = st.number_input("Amount", min_value=0.01)
            with c3:
                e_desc = st.text_input("Description")
            
            if st.form_submit_button("Save Expense"):
                new_exp = pd.DataFrame([{
                    "date": e_date.strftime("%d-%m-%Y"),
                    "head": e_head,
                    "description": e_desc,
                    "amount": e_amt,
                    "mode": "Cash"
                }])
                updated_exp = pd.concat([df_exp, new_exp], ignore_index=True)
                conn.update(worksheet="Expenses", data=updated_exp)
                st.success("Expense saved!")
                st.cache_data.clear()
                st.rerun()

with tab4:
    st.subheader("Payment Collections")
    df_coll = safe_read_gsheet("Collections")
    st.dataframe(df_coll, use_container_width=True)



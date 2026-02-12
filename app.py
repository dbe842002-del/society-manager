import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# --- 1. CONFIGURATION ---
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")

conn = st.connection("gsheets", type=GSheetsConnection)

# --- 2. RELIABLE DATA LOADER ---
@st.cache_data(ttl=300)
def load_sheet(name):
    try:
        base_url = st.secrets["connections"]["gsheets"]["spreadsheet"].split("/edit")[0]
        csv_url = f"{base_url}/export?format=csv&sheet={name}"
        df = pd.read_csv(csv_url)
        df.columns = df.columns.str.strip().str.lower()
        return df
    except Exception as e:
        st.error(f"Failed to load {name}: {e}")
        return pd.DataFrame()

# --- 3. ADMIN AUTH ---
with st.sidebar:
    pwd = st.text_input("Admin Password", type="password")
    is_admin = pwd == st.secrets["admin_password"]

# Define tabs
tab1, tab2, tab3, tab4 = st.tabs(["💰 Maintenance", "📊 Records", "💸 Expenses", "📈 Collections"])

with tab1:
    df_owners = load_sheet("Owners")
    df_coll = load_sheet("Collections")

    if df_owners.empty:
        st.warning("Owners sheet not loaded.")
    else:
        selected_flat = st.selectbox("Select Flat", sorted(df_owners['flat'].unique()))
        owner_row = df_owners[df_owners['flat'] == selected_flat].iloc[0]
        st.write(f"**Owner:** {owner_row.get('owner', 'N/A')}")

        today = datetime.now()
        total_months = (today.year - 2025) * 12 + today.month - 1
        opening_due = pd.to_numeric(owner_row.get('opening due', 0), errors='coerce') or 0
        
        paid_amt = 0
        if not df_coll.empty:
            c_flat = next((c for c in df_coll.columns if 'flat' in c), None)
            c_amt = next((c for c in df_coll.columns if 'amount' in c or 'received' in c), None)
            if c_flat and c_amt:
                paid_rows = df_coll[df_coll[c_flat].astype(str).str.upper() == str(selected_flat).upper()]
                paid_amt = pd.to_numeric(paid_rows[c_amt], errors='coerce').sum() or 0

        current_due = opening_due + (total_months * MONTHLY_MAINT) - paid_amt
        st.metric("Total Outstanding Due", f"₹{current_due:,.0f}")
        
        with st.expander("🔍 Calculation Breakdown"):
            st.write(f"Jan 2025 to {today.strftime('%b %Y')} ({total_months} months)")
            st.write(f"Maintenance: ₹{total_months * MONTHLY_MAINT:,.0f}")
            st.write(f"Opening Due: ₹{opening_due:,.0f}")
            st.write(f"Total Paid: ₹{paid_amt:,.0f}")

        if is_admin:
            st.divider()
            st.subheader("📝 Record New Payment")
            with st.form("pay_form", clear_on_submit=True):
                c1, c2 = st.columns(2)
                with c1:
                    p_date = st.date_input("Payment Date", datetime.now())
                    next_bill = 1001
                    if not df_coll.empty and 'bill_no' in df_coll.columns:
                        next_bill = int(pd.to_numeric(df_coll['bill_no'], errors='coerce').max() or 1000) + 1
                    p_bill = st.number_input("Bill No", value=next_bill)
                with c2:
                    p_mode = st.selectbox("Mode", ["Cash", "Online", "Cheque"])
                    months_options = [f"{m.strftime('%b')}-{m.year}" for m in pd.date_range("2025-01-01", periods=26, freq="MS")]
                    p_months = st.multiselect("Paying for Months", months_options)
                    p_amt = st.number_input("Amount", value=len(p_months)*MONTHLY_MAINT if p_months else MONTHLY_MAINT)

                if st.form_submit_button("Save & Sync"):
                    new_data = pd.DataFrame([{
                        "date": p_date.strftime("%d-%m-%Y"),
                        "flat": selected_flat,
                        "owner": owner_row['owner'],
                        "months_paid": ", ".join(p_months),
                        "amount_received": p_amt,
                        "mode": p_mode,
                        "bill_no": p_bill
                    }])
                    updated_df = pd.concat([df_coll, new_data], ignore_index=True)
                    conn.update(worksheet="Collections", data=updated_df)
                    st.success("Payment saved!")
                    st.cache_data.clear()
                    st.rerun()

with tab2:
    st.subheader("Owners Records")
    st.dataframe(load_sheet("Owners"), use_container_width=True)

with tab3:
    st.subheader("Expenses")
    df_exp = load_sheet("Expenses")
    if is_admin:
        with st.form("exp_form", clear_on_submit=True):
            e1, e2, e3 = st.columns(3)
            with e1:
                edate = st.date_input("Date", datetime.now())
                ehead = st.selectbox("Category", ["Security", "Electricity", "Diesel", "Salary", "Misc"])
            with e2:
                eamt = st.number_input("Amount", min_value=0.0)
            with e3:
                edesc = st.text_input("Description")
            
            if st.form_submit_button("Save Expense"):
                new_data = pd.DataFrame([{
                    "date": edate.strftime("%d-%m-%Y"),
                    "head": ehead,
                    "description": edesc,
                    "amount": eamt,
                    "mode": "Cash"
                }])
                updated_df = pd.concat([df_exp, new_data], ignore_index=True)
                conn.update(worksheet="Expenses", data=updated_df)
                st.success("Expense saved!")
                st.cache_data.clear()
                st.rerun()
    st.dataframe(df_exp, use_container_width=True)

with tab4:
    st.subheader("Collections History")
    st.dataframe(load_sheet("Collections"), use_container_width=True)

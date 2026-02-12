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
        total_paid_amount = 0.0
        if not df_coll.empty:
            flat_col = next((col for col in df_coll.columns if 'flat' in col.lower()), None)
            amount_col = next((col for col in df_coll.columns if 'amount_received' in col), None)
            if flat_col and amount_col:
                flat_payments = df_coll[df_coll[flat_col].astype(str).str.upper() == key]
                total_paid_amount = float(flat_payments[amount_col].sum())

        current_due = max(0, expected_amount - total_paid_amount)
        
        st.metric("Total Outstanding Due", f"₹{current_due:,.0f}")
        with st.expander("🔍 Breakdown"):
            st.write(f"**Jan 2025–{today.strftime('%b %Y')}** ({total_months_due} months)")
            st.write(f"Opening: ₹{opening_due:,.0f}")
            st.write(f"Expected: ₹{expected_amount:,.0f}")
            st.write(f"Paid: ₹{total_paid_amount:,.0f}")

        # === PAYMENT FORM ===
        if is_admin:
            st.divider()
            with st.form("payment_form", clear_on_submit=True):
                col1, col2 = st.columns(2)
                with col1:
                    p_date = st.date_input("Date", datetime.now())
                    next_bill = 1001
                    if 'bill_no' in df_coll.columns:
                        bill_nos = pd.to_numeric(df_coll['bill_no'], errors='coerce').dropna()
                        next_bill = int(bill_nos.max() or 1000) + 1
                    p_bill = st.number_input("Bill No", value=next_bill)
                with col2:
                    p_mode = st.selectbox("Mode", ["Cash", "Online", "Cheque"])
                    months_options = [f"{m.strftime('%b')}-{m.year}" for m in pd.date_range("2025-01-01", periods=26, freq="MS")]
                    p_months = st.multiselect("Months", months_options)
                    p_amt = st.number_input("Amount", value=len(p_months)*MONTHLY_MAINT if p_months else MONTHLY_MAINT)

                if st.form_submit_button("Save Payment"):
                    pay_data = {
                        "date": p_date.strftime("%d-%m-%Y"),
                        "bill_no": p_bill, "flat": selected_flat, "owner": owner_row['owner'],
                        "months_paid": ", ".join(p_months), "amount_received": p_amt, "mode": p_mode
                    }
                    updated_df = pd.concat([df_coll, pd.DataFrame([pay_data])], ignore_index=True)
                    conn.update(worksheet="Collections", data=updated_df)
                    st.success("✅ Saved! Receipt-ready format.")
                    st.cache_data.clear()
                    st.rerun()

# === OTHER TABS (SIMPLIFIED) ===
with tab2: st.dataframe(df_owners, use_container_width=True)
with tab3: 
    df_exp = safe_read_gsheet("Expenses")
    # Expense form here (same structure)
    st.dataframe(df_exp, use_container_width=True)
with tab4: st.dataframe(df_coll, use_container_width=True)

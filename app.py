import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ================= 1. SETTINGS =================
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")

# This is the official way to connect
conn = st.connection("gsheets", type=GSheetsConnection)

# ================= 2. THE "NO-FAIL" LOADER =================
@st.cache_data(ttl=60)
def load_sheet_data(tab_name):
    try:
        # We use the built-in worksheet parameter
        df = conn.read(worksheet=tab_name)
        if df.empty:
            return pd.DataFrame()
        # Clean headers: "Opening Due" -> "opening_due"
        df.columns = df.columns.astype(str).str.lower().str.strip().str.replace(" ", "_")
        return df
    except Exception as e:
        st.sidebar.error(f"Could not find tab '{tab_name}'")
        return pd.DataFrame()

# ================= 3. SIDEBAR & REFRESH =================
with st.sidebar:
    st.header("🔐 Admin Panel")
    pwd = st.text_input("Password", type="password")
    is_admin = (pwd == st.secrets.get("admin_password", "admin123"))
    
    if st.button("🔄 Clear Cache & Refresh"):
        st.cache_data.clear()
        st.rerun()

# ================= 4. LOAD DATA =================
df_owners = load_sheet_data("Owners")
df_coll = load_sheet_data("Collections")
df_exp = load_sheet_data("Expenses")

# ================= 5. MAIN INTERFACE =================
tab1, tab2, tab3 = st.tabs(["💰 Maintenance", "📋 All Records", "💸 Expenses"])

with tab1:
    if df_owners.empty or df_coll.empty:
        st.error("🛑 Data Loading Error")
        st.info("Ensure your Google Sheet tabs are named exactly: **Owners**, **Collections**, and **Expenses**.")
        # Diagnostics
        if st.checkbox("Show Debug Info"):
            st.write("Current Owners columns:", list(df_owners.columns) if not df_owners.empty else "Empty")
            st.write("Current Collections columns:", list(df_coll.columns) if not df_coll.empty else "Empty")
    else:
        # Selection
        selected_flat = st.selectbox("Select Flat", sorted(df_owners['flat'].unique()))
        owner_row = df_owners[df_owners['flat'] == selected_flat].iloc[0]
        
        st.info(f"👤 **Owner:** {owner_row['owner']}")

        # --- MATH ENGINE ---
        # Calculation for Feb 2026 (14 months from Jan 2025)
        total_months = 14 
        
        # 1. Opening Due (Clean ₹ and commas)
        raw_opening = str(owner_row.get('opening_due', '0'))
        clean_opening = "".join(c for c in raw_opening if c.isdigit() or c == '.')
        opening_due = float(clean_opening) if clean_opening else 0.0

        # 2. Total Paid (Search Collections)
        # We search for the flat and sum the 'amount_received' column
        payments = df_coll[df_coll['flat'] == selected_flat]
        total_paid = pd.to_numeric(payments['amount_received'], errors='coerce').sum()

        # 3. Final Calculation
        accrued = total_months * MONTHLY_MAINT
        current_due = (opening_due + accrued) - total_paid

        # --- DISPLAY ---
        st.metric("Total Outstanding Due", f"₹ {int(current_due):,}")
        
        c1, c2, c3 = st.columns(3)
        c1.write(f"**Expected (14m):** ₹{int(accrued):,}")
        c2.write(f"**Total Paid:** ₹{int(total_paid):,}")
        c3.write(f"**Opening:** ₹{int(opening_due):,}")

        # --- ADMIN PAYMENT ENTRY ---
        if is_admin:
            st.divider()
            with st.form("new_pay"):
                st.subheader("Add New Payment")
                f1, f2, f3 = st.columns(3)
                p_date = f1.date_input("Date")
                p_amt = f2.number_input("Amount", value=2100)
                p_mths = f3.text_input("Month(s)")
                if st.form_submit_button("Save Payment"):
                    new_entry = pd.DataFrame([{
                        "date": p_date.strftime("%d-%b-%Y"),
                        "flat": selected_flat,
                        "owner": owner_row['owner'],
                        "months_paid": p_mths,
                        "amount_received": p_amt,
                        "mode": "Online",
                        "bill_no": ""
                    }])
                    updated_df = pd.concat([df_coll, new_entry], ignore_index=True)
                    # Sync back to Google Sheets
                    conn.update(worksheet="Collections", data=updated_df)
                    st.cache_data.clear()
                    st.success("Payment recorded!")
                    st.rerun()

with tab2:
    st.subheader("Collection History")
    st.dataframe(df_coll, use_container_width=True)
    st.subheader("Owners List")
    st.dataframe(df_owners, use_container_width=True)

with tab3:
    st.subheader("Expense Log")
    if not df_exp.empty:
        st.dataframe(df_exp, use_container_width=True)
        total_exp = pd.to_numeric(df_exp['amount'], errors='coerce').sum()
        st.metric("Total Expenses", f"₹ {int(total_exp):,}")

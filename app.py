import streamlit as st
import pandas as pd
from datetime import datetime
from streamlit_gsheets import GSheetsConnection

# ================= 1. SETUP =================
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")
conn = st.connection("gsheets", type=GSheetsConnection)

# ================= 2. THE ULTIMATE LOADER =================
def clean_numeric(val):
    if pd.isna(val) or val == "": return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).replace('₹', '').replace(',', '').strip()
    try: return float(s)
    except: return 0.0

@st.cache_data(ttl=10)
def fetch_data(sheet_name):
    """Fetches data and ensures headers are standardized."""
    try:
        # Force fresh read by ignoring cache
        df = conn.read(worksheet=sheet_name, ttl=0)
        if df is not None and not df.empty:
            # Standardize: "Opening Due" -> "opening_due"
            df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
            return df
    except Exception as e:
        st.sidebar.warning(f"Note: Retrying {sheet_name} connection...")
    return pd.DataFrame()

# ================= 3. LOAD & DIAGNOSE =================
df_owners = fetch_data("Owners")
df_coll = fetch_data("Collections")
df_exp = fetch_data("Expenses")

with st.sidebar:
    st.header("🔐 Admin")
    pwd = st.text_input("Password", type="password")
    is_admin = (pwd == st.secrets.get("admin_password", "admin123"))
    
    st.divider()
    st.write("📊 **System Health**")
    st.write(f"Owners: {'✅' if not df_owners.empty else '❌'}")
    st.write(f"Collections: {'✅' if not df_coll.empty else '❌'}")
    
    if st.button("🔄 Clear App Cache"):
        st.cache_data.clear()
        st.rerun()

# ================= 4. MAIN APP =================
if df_owners.empty or df_coll.empty:
    st.error("🛑 Data Connection Error")
    st.info("Please check: 1. Your URL in Secrets must end in exactly `/edit`. 2. Your Tab names must be 'Owners' and 'Collections'.")
    st.stop()

tab1, tab2, tab3 = st.tabs(["💰 Maintenance", "💸 Expenses", "📋 Records"])

with tab1:
    # 1. Selection
    flats = sorted(df_owners['flat'].unique())
    selected_flat = st.selectbox("Select Flat Number", flats)
    owner_data = df_owners[df_owners['flat'] == selected_flat].iloc[0]
    
    st.subheader(f"Account: {owner_data['owner']}")

    # 2. Calculation (For Feb 2026 = 14 months)
    total_months = 14 
    
    # Opening Due from Owners Sheet
    opening_due = clean_numeric(owner_data.get('opening_due', 0))
    
    # Total Paid from Collections Sheet
    # Note: We use 'amount_received' based on your file structure
    payments = df_coll[df_coll['flat'] == selected_flat]
    total_paid = payments['amount_received'].apply(clean_numeric).sum()

    accrued = total_months * MONTHLY_MAINT
    balance = (opening_due + accrued) - total_paid

    # 3. Display
    c1, c2 = st.columns(2)
    c1.metric("Current Balance Due", f"₹ {int(balance):,}", delta_color="inverse")
    c2.metric("Total Months Paid", f"{int(total_paid/MONTHLY_MAINT)} / {total_months}")

    with st.expander("🔍 View Math"):
        st.write(f"Maintenance (Jan 25 - Feb 26): {total_months} months × ₹2,100 = ₹{int(accrued):,}")
        st.write(f"Add: Opening Balance = ₹{int(opening_due):,}")
        st.write(f"Less: Total Paid = ₹{int(total_paid):,}")
        st.markdown(f"**Final Total: ₹{int(balance):,}**")

    # 4. Admin Entry
    if is_admin:
        st.divider()
        with st.form("payment_form", clear_on_submit=True):
            st.write("### 📝 Record New Payment")
            col1, col2, col3 = st.columns(3)
            p_date = col1.date_input("Date")
            p_amt = col2.number_input("Amount", value=2100)
            p_mth = col3.text_input("Month(s) Paid")
            
            if st.form_submit_button("Submit to Google Sheets"):
                new_row = pd.DataFrame([{
                    "date": p_date.strftime("%d-%b-%Y"),
                    "flat": selected_flat,
                    "owner": owner_data['owner'],
                    "months_paid": p_mth,
                    "amount_received": p_amt,
                    "mode": "Online",
                    "bill_no": ""
                }])
                # Append and Update
                updated_df = pd.concat([df_coll, new_row], ignore_index=True)
                conn.update(worksheet="Collections", data=updated_df)
                st.cache_data.clear()
                st.success("✅ Payment Synced!")
                st.rerun()

with tab2:
    st.subheader("Expense Log")
    if not df_exp.empty:
        st.dataframe(df_exp, use_container_width=True)
        total_exp = df_exp['amount'].apply(clean_numeric).sum()
        st.metric("Total Expenses", f"₹ {int(total_exp):,}")

with tab3:
    st.subheader("Collection History")
    st.dataframe(df_coll, use_container_width=True)

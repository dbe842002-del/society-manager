import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- 1. CONFIGURATION ---
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")

# --- 2. CONNECTION SETUP ---
# This uses the 'sheet_url' from your Secrets automatically
conn = st.connection("gsheets", type=GSheetsConnection)

def load_sheet(name):
    try:
        # Get the base URL from secrets and strip everything after /edit
        base_url = st.secrets["connections"]["gsheets"]["spreadsheet"].split("/edit")[0]
        # Direct export link for the specific tab name
        csv_url = f"{base_url}/export?format=csv&sheet={name}"
        return pd.read_csv(csv_url)
    except Exception as e:
        st.error(f"Failed to load {name}: {e}")
        return pd.DataFrame()

# --- 3. AUTHENTICATION ---
with st.sidebar:
    st.header("🔐 Admin Access")
    pwd = st.text_input("Password", type="password")
    is_admin = (pwd == st.secrets["admin_password"])

# --- 4. MAIN INTERFACE ---
st.title("🏢 DBE Society Management Pro")
tab1, tab2, tab3 = st.tabs(["💰 Maintenance", "💸 Expenses", "📊 Master Records"])

# --- TAB 1: MAINTENANCE & PAYMENTS ---
with tab1:
    # 1. Load Data
    df_owners = load_sheet("Owners")
    df_coll = load_sheet("Collections")

    # 2. FORCE DATA CORRECTION
    # If df_coll has 'opening due', it definitely loaded the wrong sheet.
    # We will try to reload it or show a specific fix.
    if 'opening due' in [str(c).lower() for c in df_coll.columns]:
        st.error("⚠️ **Tab Name Mismatch!**")
        st.info("The app is trying to find a tab named **'Collections'**, but it is accidentally loading the 'Owners' tab instead.")
        st.write("Please check your Google Sheet. Is the tab named **'Collections'** (plural) or **'Collection'** (singular)?")
        
        # Emergency Fallback: If it's named 'Collection' (singular), try loading that:
        df_coll = load_sheet("Collection")

    if not df_owners.empty:
        # Standardize Owners
        df_owners.columns = df_owners.columns.str.strip().str.lower()
        selected_flat = st.selectbox("Select Flat", df_owners['flat'].unique())
        owner_row = df_owners[df_owners['flat'] == selected_flat].iloc[0]
        
        st.write(f"**Owner:** {owner_row.get('owner', 'N/A')}")

        # --- 3. DUES CALCULATION ---
        today = datetime.now()
        total_months = (today.year - 2025) * 12 + today.month
        
        # Safe way to get opening due
        due_col = next((c for c in df_owners.columns if 'due' in c), None)
        opening_val = pd.to_numeric(owner_row[due_col], errors='coerce') if due_col else 0
        opening_due = 0 if pd.isna(opening_val) else opening_val
        
        # --- 4. PAID CALCULATION ---
        paid_amt = 0
        if not df_coll.empty:
            df_coll.columns = df_coll.columns.str.strip()
            # Find Amount Column
            c_amt_col = next((c for c in df_coll.columns if 'received' in c.lower() or 'amount' in c.lower()), None)
            c_flat_col = next((c for c in df_coll.columns if c.lower() == 'flat'), None)

            if c_amt_col and c_flat_col:
                paid_rows = df_coll[df_coll[c_flat_col].astype(str).str.upper() == str(selected_flat).upper()]
                paid_amt = pd.to_numeric(paid_rows[c_amt_col], errors='coerce').sum()

        # --- 5. RESULT ---
        current_due = (opening_due + (total_months * 2100)) - paid_amt
        st.metric("Total Outstanding", f"₹ {current_due:,.0f}")
                    

# --- TAB 2: EXPENSES ---
with tab2:
    df_exp = load_sheet("Expenses")
    if is_admin:
        with st.form("exp_form", clear_on_submit=True):
            st.subheader("Add Expense")
            e1, e2, e3 = st.columns(3)
            with e1:
                edate = st.date_input("Date")
                ehead = st.selectbox("Category", ["Security", "Electricity", "Diesel", "Salary", "Misc"])
            with e2:
                eamt = st.number_input("Amount", min_value=0)
            with e3:
                edesc = st.text_input("Description")
            
            if st.form_submit_button("Save Expense"):
                new_exp = pd.DataFrame([{
                    "date": edate.strftime("%d-%m-%Y"),
                    "head": ehead,
                    "description": edesc,
                    "amount": eamt,
                    "mode": "Cash"
                }])
                updated_exp = pd.concat([df_exp, new_exp], ignore_index=True)
                conn.update(worksheet="Expenses", data=updated_exp)
                st.success("Expense Saved!")
                st.rerun()
    st.dataframe(df_exp, width="stretch")

# --- TAB 3: RECORDS ---
with tab3:
    st.dataframe(load_sheet("Collections"), width="stretch")








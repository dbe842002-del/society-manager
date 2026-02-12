import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
from datetime import datetime

# --- CONFIGURATION ---
# These must match your Streamlit Secrets exactly
try:
    ADMIN_PASSWORD = st.secrets["admin_password"]
    SHEET_URL = st.secrets["sheet_url"]
except:
    st.error("Missing Secrets: Please add admin_password and sheet_url.")
    st.stop()

st.set_page_config(page_title="DBE Society Management", layout="wide")

# --- CONNECTION ---
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(worksheet_name):
    try:
        # We use the direct sheet name you provided
        return conn.read(spreadsheet=SHEET_URL, worksheet=worksheet_name, ttl=0)
    except Exception as e:
        st.error(f"Error loading '{worksheet_name}': {e}")
        # Return empty matching columns if load fails
        cols = {"Owners": ["flat", "owner"], "Collections": ["Date", "Flat", "Amount"], "Expenses": ["Date", "Item", "Amount"]}
        return pd.DataFrame(columns=cols.get(worksheet_name, []))

# --- SIDEBAR AUTH ---
st.sidebar.title("🔐 Admin Portal")
pwd = st.sidebar.text_input("Password", type="password")
is_admin = (pwd == ADMIN_PASSWORD)

if is_admin:
    st.sidebar.success("Logged in as Admin")
elif pwd:
    st.sidebar.error("Wrong password")

# --- MAIN APP ---
st.title("🏢 DBE Society Management")

tab1, tab2, tab3 = st.tabs(["💰 Maintenance", "💸 Expenses", "📊 Logs & Audit"])

with tab1:
    # This matches your 'Owners' tab
    df_owners = load_data("Owners")
    
    if not df_owners.empty:
        if is_admin:
            st.subheader("Record New Payment")
            # Selectbox using the 'flat' column from your Google Sheet
            flat_list = df_owners["flat"].tolist() if "flat" in df_owners.columns else []
            selected_flat = st.selectbox("Select Flat", flat_list)
            
            if st.button("Save Record"):
                st.info("Recording functionality active...")
        else:
            st.write("### Resident View")
            st.dataframe(df_owners, use_container_width=True)
    else:
        st.warning("No data found in the 'Owners' tab. Please check your Google Sheet.")

with tab3:
    # This allows you to view your 3 sheets
    view_choice = st.radio("Select Sheet", ["Owners", "Expenses", "Collections"], horizontal=True)
    df_view = load_data(view_choice)
    st.dataframe(df_view, use_container_width=True)

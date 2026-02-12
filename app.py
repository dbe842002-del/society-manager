import streamlit as st
from streamlit_gsheets import GSheetsConnection  # <--- MAKE SURE THIS IS HERE
import pandas as pd
import io

# Replace hardcoded values with st.secrets
ADMIN_PASSWORD = st.secrets["admin_password"]
SHEET_URL = st.secrets["sheet_url"]

# The connection will automatically find 'connections.gsheets' in secrets
conn = st.connection("gsheets", type=GSheetsConnection)

from streamlit_gsheets import GSheetsConnection
import pandas as pd
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ================= 1. CONFIGURATION =================
MONTHLY_MAINT = 2100
# Replace with your actual "Anyone with link can view" Google Sheet URL
SHEET_URL = "https://docs.google.com/spreadsheets/d/your_sheet_id/edit#gid=0"
ADMIN_PASSWORD = "admin123" # Change this to your desired password

st.set_page_config(page_title="Society Management Admin", layout="wide")

# ================= 2. DATABASE CONNECTION =================
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(worksheet_name):
    try:
        # Use the name of the tab directly
        return conn.read(worksheet=worksheet_name, ttl=0)
    except Exception as e:
        st.error(f"Connection Error: {e}")
        return pd.DataFrame()

def update_db(df, worksheet):
    conn.update(spreadsheet=SHEET_URL, worksheet=worksheet, data=df)
    st.cache_data.clear()
    st.success(f"Database updated in {worksheet}!")

# ================= 3. AUTHENTICATION UI =================
st.sidebar.title("🔐 Access Control")
password = st.sidebar.text_input("Enter Admin Password", type="password")
is_admin = (password == ADMIN_PASSWORD)

if is_admin:
    st.sidebar.success("Admin Access Granted")
else:
    if password:
        st.sidebar.error("Incorrect Password")
    st.sidebar.info("Limited to 'View Only' mode.")

# ================= 4. MAIN INTERFACE =================
st.title("🏢 Society Management Portal")

tab1, tab2, tab3 = st.tabs(["💰 Maintenance", "💸 Expenses", "📊 Logs & Audit"])

# --- TAB 1: MAINTENANCE ---
with tab1:
    owners_df = load_data("Owners")
    
    if is_admin:
        st.subheader("📝 Record New Payment")
        col1, col2 = st.columns(2)
        with col1:
            flat = st.selectbox("Select Flat", owners_df["flat"].tolist())
            bill_no = st.text_input("Bill No", value="1001")
        with col2:
            months = st.multiselect("Select Months", ["Jan-2026", "Feb-2026", "Mar-2026"])
            mode = st.selectbox("Mode", ["Cash", "Online", "Cheque"])

        if st.button("Save Payment", type="primary"):
            coll_df = load_data("Collections")
            new_row = pd.DataFrame([{
                "Date": datetime.now().strftime("%d-%m-%Y"),
                "Bill_No": bill_no,
                "Flat": flat,
                "Amount": len(months) * MONTHLY_MAINT,
                "Mode": mode,
                "Months": ", ".join(months)
            }])
            updated_df = pd.concat([coll_df, new_row], ignore_index=True)
            update_db(updated_df, "Collections")
    else:
        st.warning("Admin login required to record payments.")
        st.info("Please use the sidebar to authenticate.")

# --- TAB 3: ADMIN EDITING ---
with tab3:
    st.subheader("📋 Master Data Records")
    
    dataset = st.radio("Choose Table to View/Edit", ["Collections", "Expenses", "Owners"], horizontal=True)
    df = load_data(dataset)

    if is_admin:
        st.write(f"### Edit {dataset} Table")
        # The Data Editor allows you to change cells like Excel
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
        
        if st.button(f"Push Changes to {dataset}"):
            update_db(edited_df, dataset)
    else:
        st.write(f"### View {dataset} Table")
        st.dataframe(df, use_container_width=True)

# ================= 5. PDF RECEIPT (FOR ADMIN) =============
if is_admin:
    st.sidebar.divider()
    st.sidebar.subheader("Quick Receipt")
    if st.sidebar.button("Generate Last Receipt"):
        # Logic to get last row and generate PDF

        st.sidebar.write("Generating...")



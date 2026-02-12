import streamlit as st
from streamlit_gsheets import GSheetsConnection
import pandas as pd
import io
from datetime import datetime
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

# ================= 1. CONFIGURATION (STRICTLY FROM SECRETS) =================
# We pull these from the Streamlit Cloud Secrets tab
try:
    ADMIN_PASSWORD = st.secrets["admin_password"]
    SHEET_URL = st.secrets["sheet_url"]
except KeyError:
    st.error("Secrets not found! Please add admin_password and sheet_url to Streamlit Secrets.")
    st.stop()

MONTHLY_MAINT = 2100

st.set_page_config(page_title="Society Management Admin", layout="wide")

# ================= 2. DATABASE CONNECTION =================
conn = st.connection("gsheets", type=GSheetsConnection)

def load_data(worksheet_name):
    try:
        # Standard connection using the URL from secrets
        df = conn.read(spreadsheet=SHEET_URL, worksheet=worksheet_name, ttl=0)
        return df
    except Exception as e:
        st.error(f"⚠️ Could not find the '{worksheet_name}' tab.")
        return pd.DataFrame(columns=["flat", "owner", "due"])

def update_db(df, worksheet):
    try:
        conn.update(spreadsheet=SHEET_URL, worksheet=worksheet, data=df)
        st.cache_data.clear()
        st.success(f"✅ Database updated in {worksheet}!")
    except Exception as e:
        st.error(f"❌ Failed to update database: {e}")

# ================= 3. AUTHENTICATION UI =================
st.sidebar.title("🔐 Access Control")
# Use a unique key to prevent refresh issues
password_input = st.sidebar.text_input("Enter Admin Password", type="password", key="login_pwd")
is_admin = (password_input == ADMIN_PASSWORD)

if is_admin:
    st.sidebar.success("Admin Access Granted")
else:
    if password_input:
        st.sidebar.error("Incorrect Password")
    st.sidebar.info("Limited to 'View Only' mode.")

# ================= 4. MAIN INTERFACE =================
st.title("🏢 Society Management Portal")

# --- DEBUG SECTION ---
if st.sidebar.button("🔍 Debug: List All Tabs"):
    try:
        # This asks Google for the names of all tabs in that file
        all_tabs = conn.list_worksheets(spreadsheet=SHEET_URL)
        st.sidebar.write("Found these tabs:")
        st.sidebar.json(all_tabs)
    except Exception as e:
        st.sidebar.error(f"Debug failed: {e}")

tab1, tab2, tab3 = st.tabs(["💰 Maintenance", "💸 Expenses", "📊 Logs & Audit"])

# --- TAB 1: MAINTENANCE ---
with tab1:
    owners_df = load_data("Owners")
    
    if is_admin:
        st.subheader("📝 Record New Payment")
        col1, col2 = st.columns(2)
        with col1:
            if not owners_df.empty and "flat" in owners_df.columns:
                flat = st.selectbox("Select Flat", owners_df["flat"].tolist())
            else:
                st.error("No flat data found in 'Owners' tab.")
                flat = "N/A"
            bill_no = st.text_input("Bill No", value=datetime.now().strftime("%H%M%S"))
        with col2:
            months = st.multiselect("Select Months", ["Jan-2026", "Feb-2026", "Mar-2026", "Apr-2026", "May-2026", "Jun-2026"])
            mode = st.selectbox("Mode", ["Cash", "Online", "Cheque"])

        if st.button("Save Payment", type="primary"):
            if not months:
                st.warning("Please select at least one month.")
            else:
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
        edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, key=f"editor_{dataset}")
        
        if st.button(f"Push Changes to {dataset}"):
            update_db(edited_df, dataset)
    else:
        st.write(f"### View {dataset} Table")
        st.dataframe(df, use_container_width=True)


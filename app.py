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
        csv_url = f"{base_url}/export?format=csv&gid={name}"  # Use gid for sheets if named by index; adjust if tab names
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

# Define ALL tabs here
tab1, tab2, tab3, tab4 = st.tabs(["💰 Maintenance", "📊 Records", "💸 Expenses", "📈 Collections"])

with tab1:
    df_owners = load_sheet("Owners")  # Assume sheet names/tabs: "Owners", "Collections", etc.
    df_coll = load_sheet("Collections")

    if df_owners.empty:
        st.warning("Load Owners sheet first.")
    else:
        selected_flat = st.selectbox("Select Flat", sorted(df_owners['flat'].unique()))
        owner_row = df_owners[df_owners['flat'] == selected_flat].iloc[0]
        st.write(f"**Owner:** {owner_row.get('owner', 'N/A')}")

        # MATH ENGINE (fixed month count: -1 since Jan 2025 = month 1)
        today = datetime.now()
        total_months = (today.year - 2025) * 12 + today.month - 1
        opening_due = pd.to_numeric(owner_row.get('opening due', 0), errors='coerce') or 0
        
        paid_amt = 0
        if

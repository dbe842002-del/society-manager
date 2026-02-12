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
        cols = pd.Series(df.columns)
        for dup in df.columns[df.columns.duplicated()].unique():
            mask = df.columns == dup
            df.columns[mask] = [dup + "_" + str(i) if i > 0 else dup 
                              for i in range(df.columns.tolist().count(dup))]
        return df
    except:
        return pd.DataFrame()

with st.sidebar:
    pwd = st.text_input("Admin Password", type="password")
    is_admin = pwd == st.secrets["admin_password"]

tab1, tab2, tab3, tab4 = st.tabs(["Maintenance", "Owners", "Expenses", "Collections"])

with tab1:
    df_owners = safe_read_gsheet("Owners")
    df_coll = safe_read_gsheet("Collections")
    
    if df_owners.empty:
        st.error("Owners sheet missing!")
        st.stop()
    
    col1, col2 = st.columns([2, 1])
    with col1:
        selected_flat = st.selectbox("Select Flat", sorted(df_owners['flat'].dropna().unique()))
    with col2:
        owner_row = df_owners[df_owners['flat']

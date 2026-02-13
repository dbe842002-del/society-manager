import streamlit as st
import pandas as pd
from datetime import datetime
import re

# ================= 1. SETTINGS =================
MONTHLY_MAINT = 2100
st.set_page_config(page_title="DBE Society Management", layout="wide")

# ================= 2. THE FAIL-SAFE LOADER =================
def get_csv_url(sheet_name):
    """
    Extracts the Spreadsheet ID and builds a direct CSV export URL.
    This bypasses tab matching issues.
    """
    try:
        raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        # Extract ID using Regex (works for any Google Sheet URL format)
        match = re.search(r"/d/([a-zA-Z0-9-_]+)", raw_url)
        if not match:
            return None
        sheet_id = match.group(1)
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    except:
        return None

@st.cache_data(ttl=30)
def load_data(sheet_name):
    url = get_csv_url(sheet_name)
    if not url:
        return pd.DataFrame()
    try:
        # Direct CSV fetch
        df = pd.read_csv(url)
        # Standardize headers: "Opening Due" -> "opening_due"
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        return df
    except Exception as e:
        return pd.DataFrame()

def clean_num(val):
    if pd.isna(val) or val == "": return 0.0
    if isinstance(val, (int, float)): return float(val)
    # Handle ₹ symbols and commas
    s = str(val).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try: return float(s)
    except: return 0.0

# ================= 3. LOAD DATA =================
df_owners = load_data("Owners")
df_coll = load_data("Collections")
df_exp = load_data("Expenses")

# ================= 4. SIDEBAR & DIAGNOSTICS =================
with st.sidebar:
    st.header("🔐 Admin Access")
    pwd = st.text_input("Password", type="password")
    is_admin = (pwd == st.secrets.get("admin_password", "admin123"))
    
    st.divider()
    st.subheader("📡 Connection Status")
    if df_owners.empty:
        st.error("❌ Owners Tab: Not Found")
    else:
        st.success("✅ Owners Tab: Connected")
        
    if df_coll.empty:
        st.error("❌ Collections Tab: Not Found")
    else:
        st.success("✅ Collections Tab: Connected")
    
    if st.button("🔄 Force Refresh"):
        st.cache_data.clear()
        st.rerun()

# ================= 5. MAIN APP =================
if df_owners.empty or df_coll.empty:
    st.error("🛑 Data Connection Error")
    st.info("### How to fix this:")
    st.markdown("""
    1. **Check Tab Names:** Ensure your Google Sheet tabs are named exactly **Owners** and **Collections** (Case sensitive, no spaces).
    2. **Public Access:** In Google Sheets, click **Share** -> Change to **'Anyone with the link'** (Viewer).
    3. **Secrets URL:** Your URL in `secrets.toml` should look like this:  
       `spreadsheet = "https://docs.google.com/spreadsheets/d/YOUR_ID/edit"`
    """)
    st.stop()

tab1, tab2, tab3 = st.tabs(["💰 Maintenance", "💸 Expenses", "📋 Records"])

with tab1:
    # Logic for calculations
    flats = sorted(df_owners['flat'].unique())
    sel_flat = st.selectbox("Select Flat", flats)
    owner = df_owners[df_owners['flat'] == sel_flat].iloc[0]
    
    st.subheader(f"Account: {owner['owner']}")

   # This will calculate the months from Jan 2025 to today automatically
today = datetime.now()
total_months = (today.year - 2025) * 12 + today.month
    
    # Calculate Paid
    paid_col = 'amount_received' if 'amount_received' in df_coll.columns else df_coll.columns[4]
    payments = df_coll[df_coll['flat'] == sel_flat]
    total_paid = payments[paid_col].apply(clean_num).sum()
    
    accrued = total_months * MONTHLY_MAINT
    balance = (opening + accrued) - total_paid

    # Display Metrics
    c1, c2 = st.columns(2)
    c1.metric("Total Outstanding Due", f"₹ {int(balance):,}")
    
    with st.expander("🔍 Calculation Details"):
        st.write(f"Maintenance (Jan 25 - Feb 26): $14 \\times 2100 = ₹{int(accrued):,}$")
        st.write(f"Opening Balance: $₹{int(opening):,}$")
        st.write(f"Total Paid: $₹{int(total_paid):,}$")
        st.markdown(f"**Final Balance: $({int(opening)} + {int(accrued)}) - {int(total_paid)} = ₹{int(balance):,}$**")

with tab3:
    st.subheader("Collections Log")
    st.dataframe(df_coll, use_container_width=True)
    st.subheader("Owners List")
    st.dataframe(df_owners, use_container_width=True)


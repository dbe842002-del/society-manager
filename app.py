import streamlit as st
import pandas as pd
import re
import urllib.parse
from datetime import datetime

# ================= 1. CONFIG & BENCHMARKS =================
MONTHLY_MAINT = 2100
DEFAULTER_LIMIT = 6300 
st.set_page_config(page_title="DBE Maint Summery", layout="wide")

# Custom CSS for UI
st.markdown("""
<style>
    .main { background-color: #f8f9fa; }
    .scroller-container {
        background-color: #d63031; color: white; padding: 12px;
        border-radius: 8px; margin-bottom: 25px; font-weight: bold;
        border-left: 10px solid #2d3436;
    }
    div[data-testid="stMetric"] {
        background-color: #ffffff; border: 1px solid #e0e0e0;
        padding: 15px; border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .wa-btn {
        background-color: #25D366; color: white !important;
        padding: 8px 16px; border-radius: 8px; text-decoration: none;
        font-weight: bold; display: inline-flex; align-items: center; gap: 8px;
    }
    .audit-box {
        background-color: #f1f2f6; border-radius: 10px; padding: 20px;
        border: 1px solid #ced4da; margin-top: 10px;
    }
</style>
""", unsafe_allow_html=True)

# ================= 2. DATA LOADERS =================
@st.cache_data(ttl=300)
def load_data(sheet_name):
    try:
        base_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet_id = re.search(r"/d/([a-zA-Z0-9-_]+)", base_url).group(1)
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        df = pd.read_csv(url)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        return df
    except:
        return pd.DataFrame()

def clean_num(val):
    if pd.isna(val) or val == "": return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try: return float(s)
    except: return 0.0

# ================= 3. AUTHENTICATION =================
if "authenticated" not in st.session_state:
    st.session_state.authenticated, st.session_state.role = False, None

st.title("🏢 DBE Maint Summery")

if not st.session_state.authenticated:
    _, login_col, _ = st.columns([1, 1, 1])
    with login_col:
        role = st.selectbox("Role", ["Viewer", "Admin"])
        pwd = st.text_input("Password", type="password")
        if st.button("Enter Portal"):
            if role == "Admin" and pwd == st.secrets.get("admin_password", "admin123"):
                st.session_state.authenticated, st.session_state.role = True, "admin"
                st.rerun()
            elif role == "Viewer" and pwd == st.secrets.get("view_password", "society123"):
                st.session_state.authenticated, st.session_state.role = True, "viewer"
                st.rerun()
            else: st.error("❌ Invalid credentials")
    st.stop()

# ================= 4. CORE DATA & LOGIC =================
df_owners = load_data("Owners")
df_coll = load_data("Collections")
df_exp = load_data("Expenses")
df_other = load_data("Other_Income") # Ensure this sheet exists in your Google Sheet

current_date = datetime.now()
total_months = (current_date.year - 2025) * 12 + current_date.month
MONTHS_LIST = [f"{m}-{y}" for y in [2025, 2026] for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]]

def get_financial_summary(coll_df, exp_df, other_df):
    """Calculates Live Balance including Maintenance and Other Income."""
    def sum_mode(df, amt_col, is_cash=True):
        if df.empty: return 0.0
        df['m_tmp'] = df['mode'].astype(str).str.strip().str.lower()
        if is_cash: return df[df['m_tmp'] == 'cash'][amt_col].apply(clean_num).sum()
        return df[df['m_tmp'] != 'cash'][amt_col].apply(clean_num).sum()

    cash_in = sum_mode(coll_df, 'amount_received', True) + sum_mode(other_df, 'amount', True)
    bank_in = sum_mode(coll_df, 'amount_received', False) + sum_mode(other_df, 'amount', False)
    cash_out = sum_mode(exp_df, 'amount', True)
    bank_out = sum_mode(exp_df, 'amount', False)
    
    return (cash_in - cash_out), (bank_in - bank_out)

# ================= 5. APP TABS =================
tabs = st.tabs(["📋 Dashboard", "🔍 Receipt Search", "📊 Financials", "⚙️ Admin Controls"])

# --- TAB 0: DASHBOARD ---
with tabs[0]:
    master_grid, defaulter_ticker = [], []
    for _, row in df_owners.iterrows():
        f = row.get('flat', 'N/A')
        paid = df_coll[df_coll['flat'] == f]['amount_received'].apply(clean_num).sum()
        opening = clean_num(row.get('opening_due', 0))
        due = opening + (total_months * MONTHLY_MAINT) - paid
        master_grid.append({"Flat": f, "Owner": row.get('owner', 'N/A'), "Due": int(due)})
        if due >= DEFAULTER_LIMIT:
            defaulter_ticker.append(f"FLAT {f}: ₹{int(due):,}")

    if defaulter_ticker:
        ticker_text = "  🔥  OVERDUE NOTICE (₹6,300+):    " + "    ●    ".join(defaulter_ticker) + "    ●    "
        st.markdown(f'<div class="scroller-container"><marquee scrollamount="6">{ticker_text}</marquee></div>', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(master_grid).style.format({"Due": "₹{:,}"}), use_container_width=True, hide_index=True)

# --- TAB 1: RECEIPTS ---
with tabs[1]:
    st.header("🔍 Receipt Search")
    c1, c2 = st.columns(2)
    sel_f = c1.selectbox("Select Flat", sorted(df_owners['flat'].unique()))
    sel_m = c2.selectbox("Select Month", MONTHS_LIST, index=MONTHS_LIST.index(current_date.strftime("%b-%Y")))
    m_data = df_coll[(df_coll['flat'] == sel_f) & (df_coll['months_paid'].astype(str).str.contains(sel_m, case=False, na=False))]
    paid_for_month = sum([clean_num(r['amount_received'])/max(len(str(r['months_paid']).split(',')), 1) for _,r in m_data.iterrows()])
    
    bal_f = [x['Due'] for x in master_grid if x['Flat'] == sel_f][0]
    
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Paid for {sel_m}", f"₹{int(paid_for_month):,}")
    m2.metric("Current Balance", f"₹{int(bal_f):,}")
    m3.metric("Owner", df_owners[df_owners['flat'] == sel_f]['owner'].iloc[0])

# --- TAB 2: FINANCIALS (INTEGRATED REPORT) ---
with tabs[2]:
    st.header("📊 Financial Position")
    cur_cash, cur_bank = get_financial_summary(df_coll, df_exp, df_other)
    
    col1, col2, col3 = st.columns(3)
    col1.metric("💵 Current Cash", f"₹{int(cur_cash):,}")
    col2.metric("🏦 Current Bank", f"₹{int(cur_bank):,}")
    col3.metric("💰 Total Funds", f"₹{int(cur_cash + cur_bank):,}")
    
    st.divider()
    st.subheader("🗓️ Monthly Audit Statement (v7)")
    sel_rep_m = st.selectbox("Select Report Month", MONTHS_LIST, index=MONTHS_LIST.index(current_date.strftime("%b-%Y")))
    
    # Filter Data for Selected Month
    m_coll = df_coll[df_coll['months_paid'].astype(str).str.contains(sel_rep_m, case=False, na=False)]
    m_other = df_other[df_other['date'].astype(str).str.contains(sel_rep_m, case=False, na=False)]
    m_exp = df_exp[df_exp['date'].astype(str).str.contains(sel_rep_m, case=False, na=False)]
    
    # Income Calculations
    maint_cash = m_coll[m_coll['mode'].str.lower() == 'cash']['amount_received'].apply(clean_num).sum()
    maint_bank = m_coll[m_coll['mode'].str.lower() != 'cash']['amount_received'].apply(clean_num).sum()
    
    other_cash = m_other[m_other['mode'].str.lower() == 'cash']['amount'].apply(clean_num).sum()
    other_bank = m_other[m_other['mode'].str.lower() != 'cash']['amount'].apply(clean_num).sum()
    
    # Expense Calculations
    exp_cash = m_exp[m_exp['mode'].str.lower() == 'cash']['amount'].apply(clean_num).sum()
    exp_bank = m_exp[m_exp['mode'].str.lower() != 'cash']['amount'].apply(clean_num).sum()

    # --- THE DBE v7 FINANCIAL TABLE ---
    st.markdown(f"""
    <div class="audit-box">
        <h4 style="text-align:center;">Statement for {sel_rep_m}</h4>
        <table style="width:100%; border-collapse: collapse; font-family: sans-serif;">
            <tr style="background-color:#dfe6e9; border-bottom: 2px solid #2d3436;">
                <td style="padding:10px;"><b>PARTICULARS</b></td>
                <td align="right" style="padding:10px;"><b>CASH (₹)</b></td>
                <td align="right" style="padding:10px;"><b>BANK (₹)</b></td>
            </tr>
            <tr>
                <td style="padding:8px;">Maintenance Collection</td>
                <td align="right" style="color:green;">+{int(maint_cash):,}</td>
                <td align="right" style="color:green;">+{int(maint_bank):,}</td>
            </tr>
            <tr>
                <td style="padding:8px;">Other Income (Donations/Int)</td>
                <td align="right" style="color:green;">+{int(other_cash):,}</td>
                <td align="right" style="color:green;">+{int(other_bank):,}</td>
            </tr>
            <tr style="border-bottom: 1px solid #ccc;">
                <td style="padding:8px;">Total Monthly Expenses</td>
                <td align="right" style="color:red;">-{int(exp_cash):,}</td>
                <td align="right" style="color:red;">-{int(exp_bank):,}</td>
            </tr>
            <tr style="font-weight:bold; font-size: 1.1em; background-color: #f8f9fa;">
                <td style="padding:10px;">Monthly Net Surplus</td>
                <td align="right" style="padding:10px;">{int(maint_cash + other_cash - exp_cash):,}</td>
                <td align="right" style="padding:10px;">{int(maint_bank + other_bank - exp_bank):,}</td>
            </tr>
        </table>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("🧾 Monthly Expense Breakdown")
    if not m_exp.empty:
        st.dataframe(m_exp[['date', 'head', 'amount', 'mode', 'remarks']], use_container_width=True, hide_index=True)
    else:
        st.info("No expenses recorded for this month.")

# --- TAB 3: ADMIN ---
with tabs[3]:
    if st.session_state.role == "admin":
        st.header("⚙️ Admin Controls")
        if st.button("🔄 Refresh All Data"):
            st.cache_data.clear()
            st.rerun()
        
        st.divider()
        st.subheader("📥 Data Backups")
        csv_m = st.selectbox("Select Month for CSV Audit", MONTHS_LIST, key="csv_audit")
        audit_data = df_coll[df_coll['months_paid'].astype(str).str.contains(csv_m, case=False, na=False)]
        if not audit_data.empty:
            st.download_button("Download Collection CSV", audit_data.to_csv(index=False).encode('utf-8'), f"DBE_Audit_{csv_m}.csv", "text/csv")
    else:
        st.warning("Admin Access Only")

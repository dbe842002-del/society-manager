import streamlit as st
import pandas as pd
import re
import urllib.parse
from datetime import datetime

# ================= 1. CONFIG & BENCHMARKS =================
MONTHLY_MAINT = 2100
DEFAULTER_LIMIT = 6300 
# Sets the browser tab title
st.set_page_config(page_title="DBE Maint Summery", layout="wide")

# Custom CSS for UI and the Red Defaulter Scroller
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

# Main Page Heading
st.title("🏢 DBE Maint Summery")

if not st.session_state.authenticated:
    _, login_col, _ = st.columns([1, 1, 1])
    with login_col:
        st.subheader("🔐 Login")
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

# ================= 4. CORE CALCULATIONS =================
df_owners = load_data("Owners")
df_coll = load_data("Collections")
df_exp = load_data("Expenses")

current_date = datetime.now()
total_months = (current_date.year - 2025) * 12 + current_date.month
MONTHS_LIST = [f"{m}-{y}" for y in [2025, 2026] for m in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]]

def get_financial_summary(c_df, e_df):
    c_df['m'] = c_df['mode'].astype(str).str.strip().str.lower()
    e_df['m'] = e_df['mode'].astype(str).str.strip().str.lower()
    cash_in = c_df[c_df['m'] == 'cash']['amount_received'].apply(clean_num).sum()
    bank_in = c_df[c_df['m'] != 'cash']['amount_received'].apply(clean_num).sum()
    cash_out = e_df[e_df['m'] == 'cash']['amount'].apply(clean_num).sum()
    bank_out = e_df[e_df['m'] != 'cash']['amount'].apply(clean_num).sum()
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
    paid_for_month = sum([clean_num(r['amount_received'])/max(len(str(r['months_paid']).split(',')),1) for _,r in m_data.iterrows()])
    
    total_paid_f = df_coll[df_coll['flat'] == sel_f]['amount_received'].apply(clean_num).sum()
    bal_f = clean_num(df_owners[df_owners['flat'] == sel_f]['opening_due'].iloc[0]) + (total_months * MONTHLY_MAINT) - total_paid_f
    
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Paid for {sel_m}", f"₹{int(paid_for_month):,}")
    m2.metric("Current Balance", f"₹{int(bal_f):,}")
    m3.metric("Owner", df_owners[df_owners['flat'] == sel_f]['owner'].iloc[0])

    if st.session_state.role == "admin" and paid_for_month > 0:
        msg = f"*DBE Receipt*\nFlat: {sel_f}\nMonth: {sel_m}\nPaid: ₹{int(paid_for_month):,}\nBal: ₹{int(bal_f):,}"
        st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(msg)}" target="_blank" class="wa-btn">Send WhatsApp</a>', unsafe_allow_html=True)

# --- TAB 2: FINANCIALS ---
with tabs[2]:
    st.header("📊 Financial Position")
    cash, bank = get_financial_summary(df_coll, df_exp)
    st.columns(3)[0].metric("💵 Cash", f"₹{int(cash):,}")
    st.columns(3)[1].metric("🏦 Bank", f"₹{int(bank):,}")
    st.columns(3)[2].metric("💰 Total", f"₹{int(cash + bank):,}")

# --- TAB 3: ADMIN ---
with tabs[3]:
    if st.session_state.role == "admin":
        st.header("⚙️ Admin Controls")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

        st.divider()
        st.subheader("📂 Bulk Monthly Summary")
        sel_bulk = st.selectbox("Select Month for Summary", MONTHS_LIST, index=MONTHS_LIST.index(current_date.strftime("%b-%Y")), key="bulk")
        bulk_data = df_coll[df_coll['months_paid'].astype(str).str.contains(sel_bulk, case=False, na=False)]
        if not bulk_data.empty:
            txt = f"*DBE {sel_bulk} Summary*\n" + "\n".join([f"• Flat {r['flat']}: ₹{int(clean_num(r['amount_received']))}" for _,r in bulk_data.iterrows()])
            st.code(txt); st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(txt)}" target="_blank" class="wa-btn">Share Summary</a>', unsafe_allow_html=True)

        st.divider()
        st.subheader("📑 Audit & Backup")
        audit_col1, audit_col2 = st.columns([2, 1])
        sel_audit = audit_col1.selectbox("Select Month for Audit", MONTHS_LIST, index=MONTHS_LIST.index(current_date.strftime("%b-%Y")), key="audit_sel")
        audit_coll = df_coll[df_coll['months_paid'].astype(str).str.contains(sel_audit, case=False, na=False)]
        
        if not audit_coll.empty:
            csv = audit_coll[['date', 'flat', 'amount_received', 'mode', 'months_paid']].to_csv(index=False).encode('utf-8')
            audit_col2.write(" ")
            audit_col2.download_button(label="📥 Download CSV", data=csv, file_name=f"DBE_Audit_{sel_audit}.csv", mime="text/csv")
    else:
        st.warning("Admin Access Only")

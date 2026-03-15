import streamlit as st
import pandas as pd
import re
import urllib.parse
from datetime import datetime

# ================= 1. CONFIG & BENCHMARKS =================
MONTHLY_MAINT = 2100
DEFAULTER_LIMIT = 6300 
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

# ================= 4. CORE DATA & LOGIC =================
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

# --- TAB 2: FINANCIALS & FULL REPORT (DBE v7 Style) ---
with tabs[2]:
    st.header("📊 Financial Position")
    cur_cash, cur_bank = get_financial_summary(df_coll, df_exp)
    
    m1, m2, m3 = st.columns(3)
    m1.metric("💵 Current Cash", f"₹{int(cur_cash):,}")
    m2.metric("🏦 Current Bank", f"₹{int(cur_bank):,}")
    m3.metric("💰 Total Funds", f"₹{int(cur_cash + cur_bank):,}")
    
    st.divider()
    st.subheader("🗓️ Monthly Audit Statement (v7)")
    sel_rep_m = st.selectbox("Select Report Month", MONTHS_LIST, index=MONTHS_LIST.index(current_date.strftime("%b-%Y")))
    
    # Logic for Opening/Closing per Month
    rep_idx = MONTHS_LIST.index(sel_rep_m)
    past_months = MONTHS_LIST[:rep_idx]
    
    # Calculate Opening (Sum of all transactions BEFORE selected month)
    df_coll['m_mode'] = df_coll['mode'].astype(str).str.strip().str.lower()
    df_exp['m_mode'] = df_exp['mode'].astype(str).str.strip().str.lower()
    
    # Simple logic: If we don't have exact dates for every row, we filter by the 'months_paid' or 'date' string
    # For a precise v7 report, we use 'date' column string matching or month names
    def get_bal_upto(month_str, is_opening=True):
        m_idx = MONTHS_LIST.index(month_str)
        target_months = MONTHS_LIST[:m_idx] if is_opening else MONTHS_LIST[:m_idx+1]
        
        # This is a simplified calculation based on your flat maintenance logic
        # For a 100% accurate daily cashbook, 'date' sorting is required
        c_in = df_coll[df_coll['months_paid'].apply(lambda x: any(m in str(x) for m in target_months)) & (df_coll['m_mode'] == 'cash')]['amount_received'].apply(clean_num).sum()
        b_in = df_coll[df_coll['months_paid'].apply(lambda x: any(m in str(x) for m in target_months)) & (df_coll['m_mode'] != 'cash')]['amount_received'].apply(clean_num).sum()
        
        c_out = df_exp[df_exp['date'].apply(lambda x: any(m in str(x) for m in target_months)) & (df_exp['m_mode'] == 'cash')]['amount'].apply(clean_num).sum()
        b_out = df_exp[df_exp['date'].apply(lambda x: any(m in str(x) for m in target_months)) & (df_exp['m_mode'] != 'cash')]['amount'].apply(clean_num).sum()
        
        return (c_in - c_out), (b_in - b_out)

    op_cash, op_bank = get_bal_upto(sel_rep_m, True)
    cl_cash, cl_bank = get_bal_upto(sel_rep_m, False)
    
    # Monthly Activity
    m_coll = df_coll[df_coll['months_paid'].astype(str).str.contains(sel_rep_m, case=False, na=False)]
    m_exp = df_exp[df_exp['date'].astype(str).str.contains(sel_rep_m, case=False, na=False)]
    
    cash_coll = m_coll[m_coll['m_mode'] == 'cash']['amount_received'].apply(clean_num).sum()
    bank_coll = m_coll[m_coll['m_mode'] != 'cash']['amount_received'].apply(clean_num).sum()
    
    cash_ex = m_exp[m_exp['m_mode'] == 'cash']['amount'].apply(clean_num).sum()
    bank_ex = m_exp[m_exp['m_mode'] != 'cash']['amount'].apply(clean_num).sum()

    st.markdown(f"""
    <div class="audit-box">
        <h4 style="text-align:center; color:#2d3436;">DBE Statement for {sel_rep_m}</h4>
        <hr>
        <table style="width:100%; border-collapse: collapse;">
            <tr style="background-color:#dfe6e9;"><td><b>PARTICULARS</b></td><td align="right"><b>CASH (₹)</b></td><td align="right"><b>BANK (₹)</b></td></tr>
            <tr><td>Opening Balance</td><td align="right">{int(op_cash):,}</td><td align="right">{int(op_bank):,}</td></tr>
            <tr><td>(+) Maintenance Collection</td><td align="right" style="color:green;">{int(cash_coll):,}</td><td align="right" style="color:green;">{int(bank_coll):,}</td></tr>
            <tr><td>(-) Monthly Expenses</td><td align="right" style="color:red;">{int(cash_ex):,}</td><td align="right" style="color:red;">{int(bank_ex):,}</td></tr>
            <tr style="border-top:2px solid #2d3436; font-weight:bold;"><td>Closing Balance</td><td align="right">{int(cl_cash):,}</td><td align="right">{int(cl_bank):,}</td></tr>
        </table>
    </div>
    """, unsafe_allow_html=True)

    st.subheader("🧾 Detailed Expense Report")
    if not m_exp.empty:
        st.dataframe(m_exp[['date', 'head', 'amount', 'mode']], use_container_width=True, hide_index=True)
    else:
        st.info("No expenses recorded for this month.")

# --- TAB 3: ADMIN ---
with tabs[3]:
    if st.session_state.role == "admin":
        st.header("⚙️ Admin Controls")
        if st.button("🔄 Refresh Data"):
            st.cache_data.clear()
            st.rerun()

        st.divider()
        st.subheader("📑 Audit CSV Download")
        csv_m = st.selectbox("Select Month for CSV", MONTHS_LIST, key="csv_sel")
        audit_data = df_coll[df_coll['months_paid'].astype(str).str.contains(csv_m, case=False, na=False)]
        if not audit_data.empty:
            csv = audit_data.to_csv(index=False).encode('utf-8')
            st.download_button("📥 Download Transaction CSV", csv, f"DB_Audit_{csv_m}.csv", "text/csv")
    else:
        st.warning("Admin Access Only")

import streamlit as st
import pandas as pd
import re
import urllib.parse
from datetime import datetime

# 1. SETUP & BENCHMARKS
MONTHLY_MAINT = 2100
DEFAULTER_LIMIT = 6300 
st.set_page_config(page_title="DBE Society Portal", layout="wide")

st.markdown("""<style>.main { background-color: #f8f9fa; } 
.scroller-container { background-color: #d63031; color: white; padding: 12px; border-radius: 8px; margin-bottom: 25px; font-weight: bold; border-left: 10px solid #2d3436; }
div[data-testid="stMetric"] { background-color: #ffffff; border: 1px solid #e0e0e0; padding: 15px; border-radius: 10px; box-shadow: 2px 2px 5px rgba(0,0,0,0.05); }
.wa-btn { background-color: #25D366; color: white !important; padding: 8px 16px; border-radius: 8px; text-decoration: none; font-weight: bold; display: inline-flex; align-items: center; gap: 8px; }</style>""", unsafe_allow_html=True)

# 2. DATA ENGINE
@st.cache_data(ttl=300)
def load_data(sheet_name):
    try:
        base_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet_id = re.search(r"/d/([a-zA-Z0-9-_]+)", base_url).group(1)
        url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
        df = pd.read_csv(url)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        return df
    except: return pd.DataFrame()

def clean_num(val):
    try: return float(str(val).replace('₹','').replace(',','').strip())
    except: return 0.0

# 3. LOGIN
if "authenticated" not in st.session_state: st.session_state.authenticated, st.session_state.role = False, None
if not st.session_state.authenticated:
    st.title("🏢 DBE Residency Portal")
    role = st.selectbox("Role", ["Viewer", "Admin"])
    pwd = st.text_input("Password", type="password")
    if st.button("Enter Portal"):
        if role == "Admin" and pwd == st.secrets.get("admin_password", "admin123"):
            st.session_state.authenticated, st.session_state.role = True, "admin"
            st.rerun()
        elif role == "Viewer" and pwd == st.secrets.get("view_password", "society123"):
            st.session_state.authenticated, st.session_state.role = True, "viewer"
            st.rerun()
    st.stop()

# 4. LOGIC
df_owners, df_coll, df_exp = load_data("Owners"), load_data("Collections"), load_data("Expenses")
total_months = (datetime.now().year - 2025) * 12 + datetime.now().month
MONTHS = [f"{m}-{y}" for y in [2025, 2026] for m in ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"]]

def get_fin(c_df, e_df):
    c_df['m'] = c_df['mode'].astype(str).str.strip().str.lower()
    e_df['m'] = e_df['mode'].astype(str).str.strip().str.lower()
    cash = c_df[c_df['m']=='cash']['amount_received'].apply(clean_num).sum() - e_df[e_df['m']=='cash']['amount'].apply(clean_num).sum()
    bank = c_df[c_df['m']!='cash']['amount_received'].apply(clean_num).sum() - e_df[e_df['m']!='cash']['amount'].apply(clean_num).sum()
    return cash, bank

# 5. UI TABS
t = st.tabs(["📋 Dashboard", "🔍 Receipts", "📊 Financials", "⚙️ Admin"])

with t[0]:
    grid, tick = [], []
    for _, r in df_owners.iterrows():
        f = r.get('flat','N/A')
        due = clean_num(r.get('opening_due',0)) + (total_months * MONTHLY_MAINT) - df_coll[df_coll['flat']==f]['amount_received'].apply(clean_num).sum()
        grid.append({"Flat": f, "Owner": r.get('owner','N/A'), "Due": int(due)})
        if due >= DEFAULTER_LIMIT: tick.append(f"FLAT {f}: ₹{int(due):,}")
    if tick: st.markdown(f'<div class="scroller-container"><marquee scrollamount="6">🔥 OVERDUE: {" ● ".join(tick)}</marquee></div>', unsafe_allow_html=True)
    st.dataframe(pd.DataFrame(grid).style.format({"Due": "₹{:,}"}), use_container_width=True, hide_index=True)

with t[1]:
    sf = st.selectbox("Flat", sorted(df_owners['flat'].unique()))
    sm = st.selectbox("Month", MONTHS, index=MONTHS.index(datetime.now().strftime("%b-%Y")))
    m_pay = df_coll[(df_coll['flat']==sf) & (df_coll['months_paid'].astype(str).str.contains(sm, case=False))]
    portion = sum([clean_num(r['amount_received'])/max(len(str(r['months_paid']).split(',')),1) for _,r in m_pay.iterrows()])
    bal = [x['Due'] for x in grid if x['Flat']==sf][0]
    st.metric(f"Paid for {sm}", f"₹{int(portion):,}")
    st.metric("Balance", f"₹{int(bal):,}")
    if st.session_state.role=="admin" and portion>0:
        msg = f"*DBE Receipt*\nFlat: {sf}\nMonth: {sm}\nPaid: ₹{int(portion):,}\nBal: ₹{int(bal):,}"
        st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(msg)}" target="_blank" class="wa-btn">WhatsApp Receipt</a>', unsafe_allow_html=True)

with t[2]:
    c, b = get_fin(df_coll, df_exp)
    st.metric("💵 Cash", f"₹{int(c):,}"); st.metric("🏦 Bank", f"₹{int(b):,}")
    st.dataframe(df_coll.tail(10), use_container_width=True)

with t[3]:
    if st.session_state.role=="admin":
        if st.button("🔄 Refresh Data"): st.cache_data.clear(); st.rerun()
        sb = st.selectbox("Bulk Month", MONTHS, index=MONTHS.index(datetime.now().strftime("%b-%Y")))
        b_data = df_coll[df_coll['months_paid'].astype(str).str.contains(sb, case=False)]
        if not b_data.empty:
            txt = f"*DBE {sb} Summary*\n" + "\n".join([f"• {r['flat']}: ₹{int(clean_num(r['amount_received']))}" for _,r in b_data.iterrows()])
            st.code(txt); st.markdown(f'<a href="https://wa.me/?text={urllib.parse.quote(txt)}" target="_blank" class="wa-btn">Share Summary</a>', unsafe_allow_html=True)
    else: st.warning("Admin Only")

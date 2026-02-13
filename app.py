import streamlit as st
import pandas as pd
from datetime import datetime
import requests
from streamlit_gsheets import GSheetsConnection


# ================= 1. THEME & UI STYLING =================
st.set_page_config(page_title="DBE Society Portal", layout="wide")

st.markdown("""
    <style>
    .main { background-color: #f8f9fa; }
    div[data-testid="stMetric"] {
        background-color: #ffffff; border: 1px solid #e0e0e0;
        padding: 15px; border-radius: 10px;
        box-shadow: 2px 2px 5px rgba(0,0,0,0.05);
    }
    .defaulter-card {
        background-color: #fff5f5; border: 1px solid #feb2b2;
        padding: 20px; border-radius: 10px; margin-bottom: 20px;
        text-align: center; border-left: 5px solid #f56565;
    }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { 
        background-color: #f0f2f6; border-radius: 5px; padding: 10px; font-weight: bold;
    }
    .stTabs [aria-selected="true"] { background-color: #007bff !important; color: white !important; }
    .sync-container { 
        padding: 15px; border: 1px dashed #007bff; border-radius: 10px; 
        background-color: #f0f7ff; margin-bottom: 20px; 
    }
    </style>
    """, unsafe_allow_html=True)

# ================= 2. DATA LOADER =================
def get_csv_url(sheet_name):
    try:
        raw_url = st.secrets["connections"]["gsheets"]["spreadsheet"]
        sheet_id = re.search(r"/d/([a-zA-Z0-9-_]+)", raw_url).group(1)
        return f"https://docs.google.com/spreadsheets/d/{sheet_id}/gviz/tq?tqx=out:csv&sheet={sheet_name}"
    except: return None

@st.cache_data(ttl=300)
def load_data(sheet_name):
    url = get_csv_url(sheet_name)
    if not url: return pd.DataFrame()
    try:
        df = pd.read_csv(url)
        df.columns = [str(c).strip().lower().replace(" ", "_") for c in df.columns]
        if 'date' in df.columns:
            df['date_dt'] = pd.to_datetime(df['date'], dayfirst=True, errors='coerce')
        return df
    except: return pd.DataFrame()

def clean_num(val):
    if pd.isna(val) or val == "": return 0.0
    if isinstance(val, (int, float)): return float(val)
    s = str(val).replace('₹', '').replace(',', '').replace(' ', '').strip()
    try: return float(s)
    except: return 0.0

# ================= 3. AUTHENTICATION =================
if "authenticated" not in st.session_state:
    st.session_state.authenticated, st.session_state.role = False, None

if not st.session_state.authenticated:
    st.title("🏢 DBE Residency Portal")
    st.markdown("---")
    c1, c2 = st.columns([1.5, 1])
    with c1:
        st.image("https://images.unsplash.com/photo-1545324418-cc1a3fa10c00?auto=format&fit=crop&w=800&q=80")
    with c2:
        st.subheader("🔐 Secure Login")
        role_select = st.selectbox("Role", ["Viewer (Resident)", "Admin (Management)"])
        pwd = st.text_input("Password", type="password")
        if st.button("Access Portal"):
            if role_select == "Admin (Management)" and pwd == st.secrets.get("admin_password", "admin123"):
                st.session_state.authenticated, st.session_state.role = True, "admin"
                st.rerun()
            elif role_select == "Viewer (Resident)" and pwd == st.secrets.get("view_password", "society123"):
                st.session_state.authenticated, st.session_state.role = True, "viewer"
                st.rerun()
            else: st.error("Wrong password")
    st.stop()

# ================= 4. DATA PROCESSING =================
df_owners = load_data("Owners")
df_coll = load_data("Collections")
df_exp = load_data("Expenses")
df_bal = load_data("Balance")

MONTHLY_MAINT = 2100
current_date = datetime.now()
total_months_elapsed = (current_date.year - 2025) * 12 + current_date.month

# ================= 5. TABS =================
tab_labels = ["📋 Master List", "📊 Financial Reports"]
if st.session_state.role == "admin":
    tab_labels.extend(["💰 Maintenance Due", "⚙️ Admin Control"])
tabs = st.tabs(tab_labels)

# --- TAB 1: MASTER LIST ---
with tabs[0]:
    master_grid = []
    defaulters_count, total_society_due = 0, 0
    for _, row in df_owners.iterrows():
        f = row['flat']
        pd_total = df_coll[df_coll['flat'] == f]['amount_received'].apply(clean_num).sum()
        due = (clean_num(row.get('opening_due', 0)) + (total_months_elapsed * MONTHLY_MAINT)) - pd_total
        if due > 6300: defaulters_count += 1
        total_society_due += due
        entry = {"Flat": f, "Owner": row['owner'], "Outstanding Balance": int(due)}
        if st.session_state.role == "admin": entry["Total Paid"] = int(pd_total)
        master_grid.append(entry)
    
    st.markdown(f"""<div class="defaulter-card"><h3 style="margin:0; color:#c53030;">⚠️ Defaulter Alert</h3>
            <p style="margin:5px 0 0 0; font-size:18px;"><b>{defaulters_count}</b> flats with dues exceeding <b>₹6,300</b></p>
            <p style="font-size:14px; color:#718096;">Total Outstanding: ₹{int(total_society_due):,}</p></div>""", unsafe_allow_html=True)

    # ✅ FIXED (safe formatting)
    df_display = pd.DataFrame(master_grid)
    if "Outstanding Balance" in df_display.columns:
    st.dataframe(df_display.style.format(subset=["Outstanding Balance"], formatter="₹{:,}"))
    else:    .applymap(lambda x: 'color: red' if x > 6300 else ('color: orange' if x > 0 else 'color: green'), 
                          df = pd.DataFrame(master_grid)
st.dataframe(df, use_container_width=True, hide_index=True)


# --- TAB 2: FINANCIAL REPORTS ---
with tabs[1]:
    st.header("📊 Financial Reports")
    years_available = sorted(df_coll['date_dt'].dt.year.dropna().unique().astype(int), reverse=True)
    if not years_available: years_available = [2025, 2026]
    yr_rpt = st.selectbox("Financial Year", years_available)
    
    y_in = df_coll[df_coll['date_dt'].dt.year == yr_rpt]['amount_received'].apply(clean_num).sum()
    y_out = df_exp[df_exp['date_dt'].dt.year == yr_rpt]['amount'].apply(clean_num).sum()
    
    m1, m2, m3 = st.columns(3)
    m1.metric(f"Income {yr_rpt}", f"₹{int(y_in):,}")
    m2.metric(f"Expense {yr_rpt}", f"₹{int(y_out):,}")
    m3.metric("Net Surplus", f"₹{int(y_in - y_out):,}")
    
    st.divider()
    m_names = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    sel_m = st.selectbox("Monthly Detail", m_names, index=current_date.month-1)
    
    bal_match = df_bal[df_bal['month'].str.contains(sel_m, na=False, case=False)]
    op_c = clean_num(bal_match.iloc[0].get('opening_cash', 0)) if not bal_match.empty else 0
    op_b = clean_num(bal_match.iloc[0].get('opening_bank', 0)) if not bal_match.empty else 0
    m_inc = df_coll[df_coll['months_paid'].str.contains(sel_m, na=False, case=False)]
    m_exp = df_exp[df_exp['month'].str.contains(sel_m, na=False, case=False)]
    c_in = m_inc[m_inc['mode'].str.lower().str.contains('cash', na=False)]['amount_received'].apply(clean_num).sum()
    c_out = m_exp[m_exp['mode'].str.lower().str.contains('cash', na=False)]['amount'].apply(clean_num).sum()
    b_in = m_inc[~m_inc['mode'].str.lower().str.contains('cash', na=False)]['amount_received'].apply(clean_num).sum()
    b_out = m_exp[~m_exp['mode'].str.lower().str.contains('cash', na=False)]['amount'].apply(clean_num).sum()

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
        pd.DataFrame({"Description": ["Opening", "Income", "Expense", "Closing"],
                      "Cash": [op_c, c_in, c_out, (op_c+c_in-c_out)],
                      "Bank": [op_b, b_in, b_out, (op_b+b_in-b_out)]}).to_excel(writer, sheet_name='Summary', index=False)
        m_exp[['date', 'head', 'description', 'amount', 'mode']].to_excel(writer, sheet_name='Expenses', index=False)
    
    st.download_button(label=f"📥 Download {sel_m} Report", data=buffer.getvalue(), file_name=f"Report_{sel_m}.xlsx", mime="application/vnd.ms-excel")
    
    c1, c2 = st.columns(2)
    c1.info(f"💵 Cash Closing: **₹{int(op_c + c_in - c_out):,}**")
    c2.success(f"🏦 Bank Closing: **₹{int(op_b + b_in - b_out):,}**")
    st.dataframe(m_exp[['date', 'head', 'description', 'amount', 'mode']], use_container_width=True, hide_index=True)

# --- ADMIN TABS ---
if st.session_state.role == "admin":
    with tabs[2]:
        st.subheader("🔎 Individual Search")
        f_choice = st.selectbox("Select Flat", sorted(df_owners['flat'].unique()))
        o_data = df_owners[df_owners['flat'] == f_choice].iloc[0]
        pd_flat = df_coll[df_coll['flat'] == f_choice]['amount_received'].apply(clean_num).sum()
        due_flat = (clean_num(o_data.get('opening_due', 0)) + (total_months_elapsed * MONTHLY_MAINT)) - pd_flat
        st.metric("Balance Due", f"₹{int(due_flat):,}")
        st.dataframe(df_coll[df_coll['flat'] == f_choice][['date', 'months_paid', 'amount_received', 'mode']], use_container_width=True, hide_index=True)
    
    with tabs[3]:
        st.subheader("⚙️ Admin Control")
        if st.button("Refresh from Google Sheets (Sync Now)"):
            st.cache_data.clear()
            st.rerun()
        st.divider()
        db_choice = st.radio("Inspect Raw Data", ["Owners", "Collections", "Expenses", "Balance"], horizontal=True)
        st.dataframe(load_data(db_choice), use_container_width=True)

# ----------------- TAB 5: ADD ENTRY (Admin Only) -----------------
if st.session_state.get('role') == "admin":
    tab5 = st.tabs(["Maintenance", "Owners", "Expenses", "Collections", "📝 Quick Entry"])[-1]
    
    with tab5:
        st.subheader("📝 Quick Data Entry")
        
        entry_type = st.radio("What are you recording?", ["Collection (Income)", "Expense (Spending)"], horizontal=True)
        
        with st.form("entry_form", clear_on_submit=True):
            date_val = st.date_input("Date", datetime.now())
            date_str = date_val.strftime("%d/%m/%Y")
            
            if entry_type == "Collection (Income)":
                f_no = st.selectbox("Flat Number", sorted(df_owners['flat'].dropna().unique()))
                owner_name = df_owners[df_owners['flat'] == f_no]['owner'].iloc[0] if not df_owners.empty else "N/A"
                months_paid = st.text_input("Months Paid (e.g., Jan-Feb 25)")
                amount = st.number_input("Amount Received (₹)", min_value=0.0, step=100.0)
                mode = st.selectbox("Payment Mode", ["UPI", "Bank Transfer", "Cash", "Cheque"])
                
                payload = [date_str, f_no, months_paid, amount, mode]
                target_sheet = "Collections"
                
            else:  # Expense
                head = st.selectbox("Expense Head", ["Electricity", "Water", "Salary", "Repair", "Misc"])
                desc = st.text_input("Description/Vendor")
                amount = st.number_input("Amount Paid (₹)", min_value=0.0, step=10.0)
                mode = st.selectbox("Payment Mode", ["Cash", "Bank Transfer"])
                month_tag = date_val.strftime("%b")  # Auto-tag month
                
                payload = [date_str, month_tag, head, desc, amount, mode]
                target_sheet = "Expenses"

            submit = st.form_submit_button("🚀 Save to Google Sheet")
            
            if submit:
                if amount <= 0:
                    st.error("❌ Please enter a valid amount.")
                else:
                    try:
                        script_url = st.secrets["connections"]["gsheets"]["script_url"]
                        response = requests.post(f"{script_url}?sheet={target_sheet}", json=payload)
                        
                        if response.status_code == 200:
                            st.success(f"✅ Data saved to {target_sheet}!")
                            st.balloons()
                            st.cache_data.clear()
                            st.rerun()
                        else:
                            st.error(f"❌ Failed: {response.status_code}")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")







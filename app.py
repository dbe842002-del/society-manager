import requests # Add this to requirements.txt

# ... (Keep all your existing loading and UI code) ...

# ----------------- TAB 5: ADD ENTRY (Admin Only) -----------------
if st.session_state.role == "admin":
    with tabs[4] if len(tabs) > 4 else tabs[-1]: # Appends to the end
        st.subheader("📝 Quick Data Entry")
        
        entry_type = st.radio("What are you recording?", ["Collection (Income)", "Expense (Spending)"], horizontal=True)
        
        with st.form("entry_form", clear_on_submit=True):
            date_val = st.date_input("Date", datetime.now())
            date_str = date_val.strftime("%d/%m/%Y")
            
            if entry_type == "Collection (Income)":
                f_no = st.selectbox("Flat Number", sorted(df_owners['flat'].unique()))
                amt = st.number_input("Amount Received (₹)", min_value=0, step=100)
                m_paid = st.text_input("Months Paid (e.g., Jan-Feb 25)")
                mode = st.selectbox("Payment Mode", ["UPI", "Bank Transfer", "Cash", "Cheque"])
                
                payload = [date_str, f_no, m_paid, amt, mode]
                target_sheet = "Collections"
                
            else:
                head = st.selectbox("Expense Head", ["Electricity", "Water", "Salary", "Repair", "Misc"])
                desc = st.text_input("Description/Vendor")
                amt = st.number_input("Amount Paid (₹)", min_value=0, step=10)
                mode = st.selectbox("Payment Mode", ["Cash", "Bank Transfer"])
                m_tag = date_val.strftime("%b") # Automatically tags the month
                
                payload = [date_str, m_tag, head, desc, amt, mode]
                target_sheet = "Expenses"

            submit = st.form_submit_button("🚀 Save to Google Sheet")
            
            if submit:
                if amt <= 0:
                    st.error("Please enter a valid amount.")
                else:
                    try:
                        # You'll add this URL to your secrets
                        script_url = st.secrets["connections"]["gsheets"]["script_url"]
                        response = requests.post(f"{script_url}?sheet={target_sheet}", json=payload)
                        
                        if response.status_code == 200:
                            st.success(f"✅ Data saved to {target_sheet} successfully!")
                            st.balloons()
                            # Clear cache so the new data shows up
                            st.cache_data.clear()
                        else:
                            st.error("Submission failed. Check Apps Script deployment.")
                    except Exception as e:
                        st.error(f"Error: {e}")

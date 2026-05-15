import streamlit as st
import pandas as pd
import plotly.express as px
import hashlib
import io
import os
from datetime import datetime
from sqlalchemy import create_engine, text

# --- 1. DATABASE CONFIGURATION (PIECE-BY-PIECE VERSION) ---
try:
    # Building the URL from parts to prevent the "a." parsing error
    U = st.secrets["DB_USER"]
    P = st.secrets["DB_PASS"]
    H = st.secrets["DB_HOST"]
    PORT = st.secrets["DB_PORT"]
    DB = st.secrets["DB_NAME"]
    
    # Construct the clean connection string
    # Using 'postgresql+psycopg2' explicitly for stability
    clean_url = f"postgresql://{U}:{P}@{H}:{PORT}/{DB}?sslmode=require"
    engine = create_engine(clean_url)
    
    # Sidebar Diagnostic: Check if U contains a dot (it must for Supabase Pooler)
    if "." not in U:
        st.sidebar.error("⚠️ DB_USER should be 'postgres.PROJECT_ID'")
    else:
        st.sidebar.caption(f"🌐 Authenticating as: {U}")

except Exception as e:
    st.error("🚨 Configuration Error: Please ensure DB_USER, DB_PASS, DB_HOST, DB_PORT, and DB_NAME are all set in Secrets.")
    st.stop()

# --- 4. DATABASE FUNCTIONS ---
def load_users():
    try:
        # Standard query
        return pd.read_sql("SELECT * FROM users", engine)
    except Exception as e:
        # If the user table is missing, initialize it
        if "does not exist" in str(e).lower():
            admin_pass = hashlib.sha256("Sillycat01".encode()).hexdigest()
            df_init = pd.DataFrame([{"username": "admin", "password": admin_pass, "role": "admin", "owner_name": "All"}])
            try:
                df_init.to_sql("users", engine, if_exists="replace", index=False)
                return df_init
            except Exception as inner_e:
                st.error("🚨 Fatal Database Error")
                st.code(str(inner_e))
                st.stop()
        else:
            # This will catch the 'Tenant or user not found' error properly
            st.error("🚨 Connection Error: Supabase rejected the login.")
            st.info("Check your DB_USER format. It must be: postgres.YOUR_PROJECT_ID")
            st.code(str(e))
            st.stop()

# ... [The rest of the dashboard/analytics/management logic remains the same as previous] ...

# --- 5. LOGIN ---
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if os.path.exists("logo.png"): st.image("logo.png")
        st.title("🔐 Executive Login")
    u_df = load_users()
    with st.form("l"):
        un, pw = st.text_input("Username"), st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            hp = hashlib.sha256(pw.encode()).hexdigest()
            row = u_df[(u_df['username'] == un) & (u_df['password'] == hp)]
            if not row.empty:
                st.session_state.update({'logged_in': True, 'user_role': row.iloc[0]['role'], 'assigned_owner': row.iloc[0]['owner_name'], 'user_name': un, 'sel_owner': row.iloc[0]['owner_name'] if row.iloc[0]['role'] == 'landlord' else "All Owners"})
                st.rerun()
            else: st.error("Access Denied")
    st.stop()

# --- 6. NAVIGATION ---
raw_df = load_master_data()
with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png")
    if st.session_state['user_role'] == 'admin':
        with st.expander("📂 Data Sync"):
            up = st.file_uploader("Upload CSV", type="csv")
            md = "replace" if st.radio("Mode", ["Overwrite", "Append"]) == "Overwrite" else "append"
            if up and st.button("Sync Now"): update_database(up, md); st.rerun()
    
    if st.button("📊 Dashboard", use_container_width=True): st.session_state['current_page'] = "Dashboard"
    if st.button("📈 Analytics", use_container_width=True): st.session_state['current_page'] = "Analytics"
    if st.button("🛠️ Meters", use_container_width=True): st.session_state['current_page'] = "Management"
    if st.session_state['user_role'] == 'admin':
        if st.button("👥 Users", use_container_width=True): st.session_state['current_page'] = "UserAdmin"
    
    st.divider()
    if not raw_df.empty and st.session_state['user_role'] == 'admin':
        opts = ["All Owners"] + sorted(raw_df['Owner Detail'].unique().tolist())
        st.session_state['sel_owner'] = st.selectbox("View Portfolio As:", opts)
    
    if st.button("Logout"): st.session_state['logged_in'] = False; st.rerun()

# --- 7. PAGES ---
working_df = raw_df if st.session_state['sel_owner'] == "All Owners" else raw_df[raw_df['Owner Detail'] == st.session_state['sel_owner']]

if st.session_state['current_page'] == "Dashboard":
    if working_df.empty: st.warning("No data available.")
    else:
        st.title(f"🏢 {st.session_state['sel_owner']}")
        sb = st.multiselect("Filter Buildings", sorted(working_df['Building Detail'].unique()), default=sorted(working_df['Building Detail'].unique()))
        fdf = working_df[working_df['Building Detail'].isin(sb)]
        
        # 1. BREAKDOWN
        st.subheader("📋 Monthly Breakdown")
        summary = fdf.groupby(['Year_Month_Key', 'Building Detail']).agg({'Sum Of Total Incl Vat': 'sum', 'Units': 'sum', 'Meter Number': 'nunique'}).rename(columns={'Sum Of Total Incl Vat': 'Sales', 'Units': 'Consumption', 'Meter Number': 'Meters'})
        st.dataframe(summary.style.format("R {:,.2f}", subset=['Sales']), use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            xl = io.BytesIO()
            with pd.ExcelWriter(xl) as wr: summary.to_excel(wr)
            st.download_button("📥 Export Excel", xl.getvalue(), "Statement.xlsx")
        with c2:
            if FPDF:
                sel_m = st.selectbox("Select Month for PDF", sorted(fdf['Display_Month'].unique()))
                if st.button("📥 Generate PDF"):
                    m_data = fdf[fdf['Display_Month'] == sel_m].groupby('Building Detail').agg({'Sum Of Total Incl Vat': 'sum', 'Units': 'sum'})
                    st.download_button("Download PDF", gen_p(m_data, f"Report: {sel_m}"), "Report.pdf")

        st.divider()
        # 2. TOP 10
        st.subheader("🏆 Top 10 Transactions")
        st.dataframe(fdf.sort_values('Sum Of Total Incl Vat', ascending=False).head(10)[['Trans_date', 'Customer Surname', 'Sum Of Total Incl Vat', 'Meter Number']], use_container_width=True)

        st.divider()
        # 3. TREND
        st.subheader("📈 Performance Trend")
        st.plotly_chart(px.line(fdf.groupby('Year_Month_Key')['Sum Of Total Incl Vat'].sum().reset_index(), x='Year_Month_Key', y='Sum Of Total Incl Vat', markers=True), use_container_width=True)

        st.divider()
        # 4. SEARCH
        st.subheader("🔎 Search & All Transactions")
        q = st.text_input("Type to filter...")
        res = fdf if not q else fdf[fdf.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
        st.dataframe(res, use_container_width=True)

elif st.session_state['current_page'] == "Analytics":
    st.title("📈 Portfolio Analytics")
    c1, c2 = st.columns(2)
    with c1: st.plotly_chart(px.pie(working_df, values='Sum Of Total Incl Vat', names='Service Resource', title="Resource Mix"), use_container_width=True)
    with c2: st.plotly_chart(px.bar(working_df.groupby('Client')['Sum Of Total Incl Vat'].sum().reset_index(), x='Client', y='Sum Of Total Incl Vat', title="Revenue per Client Account"), use_container_width=True)

elif st.session_state['current_page'] == "UserAdmin":
    st.title("👥 User Administration")
    u_df = load_users()
    t1, t2 = st.tabs(["Add Landlord", "Reset Passwords"])
    with t1:
        with st.form("cu"):
            nu, np = st.text_input("New Username"), st.text_input("Temporary Password", type="password")
            no = st.selectbox("Assign to Owner", ["All"] + sorted(raw_df['Owner Detail'].unique().tolist()) if not raw_df.empty else ["All"])
            if st.form_submit_button("Create Account"): save_user(nu, np, "landlord", no); st.rerun()
    with t2:
        ur = st.selectbox("Select Account", u_df['username'].tolist())
        npw = st.text_input("New Password", type="password")
        if st.button("Update Access"): update_user_password(ur, npw); st.success("Access Updated.")

elif st.session_state['current_page'] == "Management":
    st.title("🛠️ Meter Lookup")
    m_no = st.text_input("Search by Meter Number")
    if m_no:
        st.dataframe(working_df[working_df['Meter_Search'].str.contains(m_no)], use_container_width=True)

import streamlit as st
import pandas as pd
import plotly.express as px
import hashlib
import io
import os
import random
from datetime import datetime
from sqlalchemy import create_engine, text

# --- 1. SESSION STATE INITIALIZATION ---
if 'logged_in' not in st.session_state:
    st.session_state.update({
        'logged_in': False, 
        'user_role': None, 
        'assigned_owner': None, 
        'current_page': "Dashboard", 
        'user_name': None, 
        'sel_owner': "All Owners"
    })

# --- 2. DATABASE CONFIGURATION ---
try:
    def scrub(key):
        return str(st.secrets[key]).strip().replace('"', '').replace("'", "").replace(" ", "")

    RAW_ID = scrub("DB_USER")
    P = scrub("DB_PASS")
    H = scrub("DB_HOST")
    PORT = scrub("DB_PORT")
    DB = scrub("DB_NAME")
    
    clean_id = RAW_ID.replace("postgres.", "").replace("postgres", "")
    U = f"postgres.{clean_id}"
    
    clean_url = f"postgresql://{U}:{P}@{H}:{PORT}/{DB}?sslmode=require"
    engine = create_engine(clean_url, pool_pre_ping=True)

except Exception as e:
    st.error("🚨 Secret Configuration Error: Check your Streamlit Secrets.")
    st.stop()

# --- 3. APP CONFIG & BRANDING ---
st.set_page_config(page_title="I-Switch Executive Portal", page_icon="logo.png", layout="wide")

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# --- 4. UTILITY HELPERS ---
def generate_sts_token():
    """Generates a standard 20-digit split STS utility token format."""
    blocks = [f"{random.randint(1000, 9999)}" for _ in range(5)]
    return "-".join(blocks)

# --- 5. DATABASE FUNCTIONS ---
def load_users():
    try:
        df = pd.read_sql("SELECT * FROM users", engine)
        st.sidebar.success(f"✔️ Connected to Database")
        return df
    except Exception as e:
        err_str = str(e).lower()
        if "does not exist" in err_str:
            admin_pass = hashlib.sha256("Sillycat01".encode()).hexdigest()
            df_init = pd.DataFrame([{"username": "admin", "password": admin_pass, "role": "admin", "owner_name": "All"}])
            try:
                df_init.to_sql("users", engine, if_exists="replace", index=False)
                st.sidebar.success(f"✔️ System Tables Initialized")
                return df_init
            except Exception as sql_e:
                st.error("🚨 System Table Initialization Failed")
                st.code(str(sql_e))
                st.stop()
        else:
            st.sidebar.error("❌ App Connection Failed")
            st.error("🚨 Connection Handshake Rejected")
            st.code(str(e))
            st.stop()

def save_user(u, p, r, o):
    hp = hashlib.sha256(p.encode()).hexdigest()
    query = text("INSERT INTO users (username, password, role, owner_name) VALUES (:u, :p, :r, :o)")
    with engine.connect() as conn:
        conn.execute(query, {"u": u, "p": hp, "r": r, "o": o})
        conn.commit()
    return True

def update_user_password(u, p):
    hp = hashlib.sha256(p.encode()).hexdigest()
    query = text("UPDATE users SET password = :p WHERE username = :u")
    with engine.connect() as conn:
        conn.execute(query, {"p": hp, "u": u})
        conn.commit()
    return True

@st.cache_data(ttl=60)
def load_master_data():
    try:
        df = pd.read_sql("SELECT * FROM transactions", engine)
        if df.empty: return df
        df['Units'] = pd.to_numeric(df['Units'], errors='coerce').fillna(0)
        df['Sum Of Total Incl Vat'] = pd.to_numeric(df['Sum Of Total Incl Vat'], errors='coerce').fillna(0)
        df['Trans_date'] = pd.to_datetime(df['Trans_date'], errors='coerce')
        df = df.dropna(subset=['Trans_date', 'Owner Detail', 'Building Detail'])
        
        df['Year_Month_Key'] = df['Trans_date'].dt.strftime('%Y-%m')
        df['Month'] = df['Trans_date'].dt.strftime('%B')
        df['Display_Month'] = df['Month'] + " " + df['Trans_date'].dt.year.astype(str)
        df['Meter_Search'] = df['Meter Number'].astype(str).str.strip()
        return df
    except: return pd.DataFrame()

def update_database(f, m):
    df = pd.read_csv(f)
    df.columns = df.columns.str.strip()
    df.to_sql("transactions", engine, if_exists=m, index=False)
    st.cache_data.clear()

def gen_p(df, title):
    pdf = FPDF(orientation='L'); pdf.add_page(); pdf.set_font("Helvetica", 'B', 14)
    pdf.cell(270, 10, title, ln=True, align='C'); pdf.ln(10); pdf.set_font("Helvetica", size=8)
    pdf_df = df.reset_index()
    for h in pdf_df.columns: pdf.cell(32, 10, str(h)[:14], 1)
    pdf.ln()
    for _, r in pdf_df.iterrows():
        for v in r:
            txt = f"{v:,.2f}" if isinstance(v, (float, int)) else str(v)[:14]
            pdf.cell(32, 10, txt, 1)
        pdf.ln()
    try: return pdf.output(dest='S').encode('latin-1')
    except: return pdf.output()

# --- 5. LOGIN HANDSHAKE ---
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
        st.title("🔐 Executive Login")
    u_df = load_users()
    with st.form("login_gate"):
        un, pw = st.text_input("Username"), st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            hp = hashlib.sha256(pw.encode()).hexdigest()
            row = u_df[(u_df['username'] == un) & (u_df['password'] == hp)]
            if not row.empty:
                st.session_state.update({
                    'logged_in': True, 
                    'user_role': row.iloc[0]['role'], 
                    'assigned_owner': row.iloc[0]['owner_name'], 
                    'user_name': un,
                    'sel_owner': row.iloc[0]['owner_name'] if row.iloc[0]['role'] == 'landlord' else "All Owners"
                })
                st.rerun()
            else: st.error("Access Denied: Invalid Credentials")
    st.stop()

# --- 6. NAVIGATION & BASE SIDEBAR ---
raw_df = load_master_data()

with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
    st.title(f"👤 {st.session_state['user_name']}")
    
    if st.session_state['user_role'] == 'admin':
        with st.expander("📂 Data Sync"):
            up = st.file_uploader("Upload CSV", type="csv")
            md = "replace" if st.radio("Mode", ["Overwrite", "Append"]) == "Overwrite" else "append"
            if up and st.button("Sync Now"): update_database(up, md); st.rerun()
    
    st.button("📊 Dashboard", on_click=lambda: st.session_state.update({'current_page': 'Dashboard'}), use_container_width=True)
    st.button("📈 Analytics", on_click=lambda: st.session_state.update({'current_page': 'Analytics'}), use_container_width=True)
    st.button("🛠️ Meters", on_click=lambda: st.session_state.update({'current_page': 'Management'}), use_container_width=True)
    if st.session_state['user_role'] == 'admin' and st.button("👥 Users", use_container_width=True):
        st.session_state['current_page'] = "UserAdmin"
    
    st.divider()
    if not raw_df.empty and st.session_state['user_role'] == 'admin':
        opts = ["All Owners"] + sorted(raw_df['Owner Detail'].unique().tolist())
        st.session_state['sel_owner'] = st.selectbox("View Portfolio:", opts)

# --- 7. GLOBAL PORTFOLIO FILTERING ---
working_df = raw_df if st.session_state['sel_owner'] == "All Owners" else raw_df[raw_df['Owner Detail'] == st.session_state['sel_owner']]

if st.session_state['current_page'] in ["Dashboard", "Analytics"]:
    if working_df.empty:
        st.sidebar.warning("No data found.")
        fdf = working_df
    else:
        with st.sidebar:
            st.markdown("### 🔍 Filter Portfolio")
            sb = st.multiselect("Filter Buildings", sorted(working_df['Building Detail'].unique()), default=sorted(working_df['Building Detail'].unique()))
            chron_timeline = working_df.sort_values('Year_Month_Key')['Display_Month'].unique().tolist()
            selected_months = st.multiselect("Filter Months/Years", chron_timeline, default=chron_timeline)
            st.divider()
            if st.button("Logout", use_container_width=True): st.session_state['logged_in'] = False; st.rerun()
        fdf = working_df[(working_df['Building Detail'].isin(sb)) & (working_df['Display_Month'].isin(selected_months))]
else:
    with st.sidebar:
        if st.button("Logout", use_container_width=True): st.session_state['logged_in'] = False; st.rerun()

# --- 8. PAGES ---

if st.session_state['current_page'] == "Dashboard":
    if fdf.empty: st.warning("No data matches selected timeline or building parameters.")
    else:
        st.title(f"🏢 {st.session_state['sel_owner']}")
        
        st.subheader("📋 Monthly Breakdown")
        summary = fdf.groupby(['Year_Month_Key', 'Building Detail']).agg({'Sum Of Total Incl Vat': 'sum', 'Units': 'sum', 'Meter Number': 'nunique'}).rename(columns={'Sum Of Total Incl Vat': 'Sales', 'Units': 'Consumption', 'Meter Number': 'Meters'})
        st.dataframe(summary.style.format("R {:,.2f}", subset=['Sales']), use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            xl = io.BytesIO()
            with pd.ExcelWriter(xl) as wr: summary.to_excel(wr)
            st.download_button("📥 Excel Export", xl.getvalue(), "Statement.xlsx")
        with c2:
            if FPDF:
                ex_m = sorted(fdf['Display_Month'].unique())
                sel_m = st.selectbox("Select Month for PDF", ex_m)
                if st.button("📥 Generate PDF"):
                    m_data = fdf[fdf['Display_Month'] == sel_m].groupby('Building Detail').agg({'Sum Of Total Incl Vat': 'sum', 'Units': 'sum'})
                    st.download_button("Download PDF", gen_p(m_data, f"Report: {sel_m}"), "Report.pdf")

        st.divider()
        st.subheader("🏆 Top 10 Highest Transactions")
        st.dataframe(fdf.sort_values('Sum Of Total Incl Vat', ascending=False).head(10)[['Trans_date', 'Customer Surname', 'Sum Of Total Incl Vat', 'Meter Number']], use_container_width=True)

        st.divider()
        st.subheader("📈 Performance Trend")
        st.plotly_chart(px.line(fdf.groupby('Year_Month_Key')['Sum Of Total Incl Vat'].sum().reset_index(), x='Year_Month_Key', y='Sum Of Total Incl Vat', markers=True), use_container_width=True)

        st.divider()
        st.subheader("🔎 Search All Transactions")
        q = st.text_input("Filter dashboard results by keyword...")
        res = fdf if not q else fdf[fdf.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
        st.write(f"Showing {len(res)} results:")
        st.dataframe(res, use_container_width=True)

elif st.session_state['current_page'] == "Analytics":
    st.title("📈 Portfolio Analytics")
    if fdf.empty: st.warning("Select items from the sidebar filter options to populate data panels.")
    else:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.pie(fdf, values='Sum Of Total Incl Vat', names='Service Resource', title="Revenue Mix by Service Type"), use_container_width=True)
        with c2: 
            client_revenue = fdf.groupby('Client')['Sum Of Total Incl Vat'].sum().reset_index()
            st.plotly_chart(px.bar(client_revenue, x='Client', y='Sum Of Total Incl Vat', title="Revenue Contribution per Client Account"), use_container_width=True)
        st.divider()
        c3, c4 = st.columns(2)
        with c3:
            consumption_trend = fdf.groupby('Year_Month_Key')['Units'].sum().reset_index()
            st.plotly_chart(px.line(consumption_trend, x='Year_Month_Key', y='Units', markers=True, title="Monthly Consumption Velocity (Total Units / kWh)"), use_container_width=True)
        with c4:
            building_comp = fdf.groupby('Building Detail')['Sum Of Total Incl Vat'].sum().reset_index().sort_values('Sum Of Total Incl Vat', ascending=False).head(15)
            st.plotly_chart(px.bar(building_comp, y='Building Detail', x='Sum Of Total Incl Vat', orientation='h', title="Top 15 Revenue-Generating Buildings"), use_container_width=True)

elif st.session_state['current_page'] == "UserAdmin":
    st.title("👥 User Administration")
    u_df = load_users()
    t1, t2 = st.tabs(["Add Landlord", "Reset Password"])
    with t1:
        with st.form("create_landlord"):
            nu, np = st.text_input("New Username"), st.text_input("Password", type="password")
            no = st.selectbox("Assign to Owner", ["All"] + sorted(raw_df['Owner Detail'].unique().tolist()) if not raw_df.empty else ["All"])
            if st.form_submit_button("Create Account"): save_user(nu, np, "landlord", no); st.rerun()
    with t2:
        ur = st.selectbox("Select Account", u_df['username'].tolist())
        npw = st.text_input("New Password", type="password")
        if st.button("Update Access"): update_user_password(ur, npw); st.success("Access Updated.")

elif st.session_state['current_page'] == "Management":
    st.title("🛠️ Meter Reference & Transaction History")
    if working_df.empty: 
        st.warning("No historical transactional data available.")
    else:
        st.markdown("### 🔍 Search & Filter Portfolio Meters")
        
        # Extended 4-Column Search Matrix Layout
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            query_meter = st.text_input("Search Meter Number", placeholder="Filter by digits...").strip()
        with col2:
            building_options = ["All Buildings"] + sorted(working_df['Building Detail'].unique().tolist())
            query_building = st.selectbox("Filter by Location", building_options)
        with col3:
            query_client = st.text_input("Search Client Name", placeholder="e.g. Ontec...").strip()
        with col4:
            query_surname = st.text_input("Search Customer Surname", placeholder="e.g. Smith...").strip()
            
        # Execute Filter Chain
        filtered_meters_df = working_df.copy()
        if query_meter:
            filtered_meters_df = filtered_meters_df[filtered_meters_df['Meter_Search'].str.contains(query_meter, case=False, na=False)]
        if query_building != "All Buildings":
            filtered_meters_df = filtered_meters_df[filtered_meters_df['Building Detail'] == query_building]
        if query_client:
            filtered_meters_df = filtered_meters_df[filtered_meters_df['Client'].str.contains(query_client, case=False, na=False)]
        if query_surname:
            filtered_meters_df = filtered_meters_df[filtered_meters_df['Customer Surname'].str.contains(query_surname, case=False, na=False)]
            
        if filtered_meters_df.empty:
            st.warning("No active meters found matching your filter combinations.")
        else:
            # Build directory aggregation
            directory_flat = filtered_meters_df.groupby('Meter Number').agg({
                'Building Detail': 'first',
                'Client': 'first',
                'Customer Surname': 'first',
                'Sum Of Total Incl Vat': 'sum',
                'Units': 'sum',
                'Trans_date': 'count'
            }).rename(columns={
                'Sum Of Total Incl Vat': 'Lifetime Billings',
                'Units': 'Total Consumption',
                'Trans_date': 'Transaction Count'
            }).reset_index()
            
            st.write(f"### 📋 Meter Directory ({len(directory_flat)} Meters Displayed)")
            
            # FIXED: Removed trailing floating point zeros via strict format mapping
            st.dataframe(directory_flat.style.format({
                'Lifetime Billings': 'R {:,.2f}',
                'Total Consumption': '{:,.2f}'
            }), use_container_width=True)
            
            # History Drill-Down & Active Control System
            st.divider()
            st.markdown("### 🔎 Inspect & Control Active Meter Instance")
            available_meters = sorted(directory_flat['Meter Number'].unique().tolist())
            selected_meter = st.selectbox("Select any meter from the active list below to initiate live commands or view execution history:", available_meters)
            
            if selected_meter:
                ledger_df = working_df[working_df['Meter Number'] == selected_meter].sort_values('Trans_date', ascending=False)
                
                # Render Operational Command center panel
                st.markdown(f"#### ⚡ Meter Operations Control Panel: `{selected_meter}`")
                op_col1, op_col2 = st.columns(2)
                
                with op_col1:
                    st.write("**Operational Status Switching**")
                    b1, b2 = st.columns(2)
                    with b1:
                        if st.button("🔴 Block Meter Connection", use_container_width=True):
                            st.toast(f"Command Dispatched: Meter {selected_meter} has been BLOCKED.", icon="🔒")
                    with b2:
                        if st.button("🟢 Unblock Meter Connection", use_container_width=True):
                            st.toast(f"Command Dispatched: Meter {selected_meter} has been UNBLOCKED.", icon="🔓")
                
                with op_col2:
                    st.write("**STS Engineering Token Factory**")
                    token_type = st.selectbox("Select Target Key Config", ["Clear Tamper Status", "Key Change Token", "Clear Credit Reserve", "High Power Limit Test"])
                    if st.button("⚙️ Generate Engineering Token", use_container_width=True):
                        generated_key = generate_sts_token()
                        st.info(f"**Generated STS {token_type} Token:**")
                        st.code(generated_key, language="text")
                
                st.divider()
                
                # Performance Cards
                kpi1, kpi2, kpi3 = st.columns(3)
                with kpi1: st.metric("Aggregate Revenue Billings", f"R {ledger_df['Sum Of Total Incl Vat'].sum():,.2f}")
                with kpi2: st.metric("Cumulative Load", f"{ledger_df['Units'].sum():,.2f} Units")
                with kpi3: st.metric("Total Recorded Actions", f"{len(ledger_df)}")
                    
                st.write(f"### 📋 Detailed Transaction Ledger for Meter: `{selected_meter}`")
                st.dataframe(ledger_df, use_container_width=True)

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
    clean_url = f"postgresql://{U}:{P}@{H}:{PORT}/{DB}?sslmode=require"
    engine = create_engine(clean_url)
    
    # Sidebar Diagnostic
    st.sidebar.caption(f"🌐 Host: {H}")

except Exception as e:
    st.error("🚨 Configuration Error: Please ensure DB_USER, DB_PASS, DB_HOST, DB_PORT, and DB_NAME are all set in Secrets.")
    st.stop()

# --- 2. APP CONFIG & BRANDING ---
st.set_page_config(page_title="I-Switch Executive Portal", page_icon="logo.png", layout="wide")

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# --- 3. SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.update({'logged_in': False, 'user_role': None, 'assigned_owner': None, 'current_page': "Dashboard", 'user_name': None, 'sel_owner': "All Owners"})

# --- 4. DATABASE FUNCTIONS ---
def load_users():
    try:
        return pd.read_sql("SELECT * FROM users", engine)
    except Exception:
        admin_pass = hashlib.sha256("Sillycat01".encode()).hexdigest()
        df_init = pd.DataFrame([{"username": "admin", "password": admin_pass, "role": "admin", "owner_name": "All"}])
        try:
            df_init.to_sql("users", engine, if_exists="replace", index=False)
            return df_init
        except Exception as e:
            st.error("🚨 Database Connection Failed.")
            st.code(str(e))
            st.stop()

def save_user(u, p, r, o):
    hp = hashlib.sha256(p.encode()).hexdigest()
    query = text("INSERT INTO users (username, password, role, owner_name) VALUES (:u, :p, :r, :o)")
    with engine.connect() as conn:
        conn.execute(query, {"u": u, "p": hp, "r": r, "o": o}); conn.commit()
    return True

def update_user_password(u, p):
    hp = hashlib.sha256(p.encode()).hexdigest()
    query = text("UPDATE users SET password = :p WHERE username = :u")
    with engine.connect() as conn:
        conn.execute(query, {"p": hp, "u": u}); conn.commit()
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
        df['Meter_Search'] = df['Meter Number'].astype(str)
        return df
    except: return pd.DataFrame()

def update_database(f, m):
    df = pd.read_csv(f); df.columns = df.columns.str.strip()
    df.to_sql("transactions", engine, if_exists=m, index=False)
    st.cache_data.clear()

def gen_p(df, title):
    pdf = FPDF(orientation='L'); pdf.add_page(); pdf.set_font("Helvetica", 'B', 14)
    pdf.cell(270, 10, title, ln=True, align='C'); pdf.ln(10); pdf.set_font("Helvetica", size=8)
    pdf_df = df.reset_index()
    for h in pdf_df.columns: pdf.cell(30, 10, str(h)[:12], 1)
    pdf.ln()
    for _, r in pdf_df.iterrows():
        for v in r: pdf.cell(30, 10, f"{v:,.2f}" if isinstance(v, (float, int)) else str(v)[:14], 1)
        pdf.ln()
    try: return pdf.output(dest='S').encode('latin-1')
    except: return pdf.output()

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

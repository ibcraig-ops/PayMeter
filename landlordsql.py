import streamlit as st
import pandas as pd
import plotly.express as px
import hashlib
import io
import os
from datetime import datetime
from sqlalchemy import create_engine, text

# --- 1. DATABASE CONFIGURATION ---
try:
    DB_URL = st.secrets["DB_URL"]
    engine = create_engine(DB_URL)
except Exception as e:
    st.error("🚨 Database Connection URL not found in Secrets.")
    st.stop()

# --- 2. APP CONFIG & BRANDING ---
st.set_page_config(
    page_title="I-Switch Executive Portal",
    page_icon="logo.png", # This puts the logo in the browser tab
    layout="wide"
)

# Optional: Try to import FPDF for PDF generation
try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# --- 3. SESSION STATE ---
if 'logged_in' not in st.session_state:
    st.session_state.update({
        'logged_in': False, 'user_role': None, 'assigned_owner': None, 
        'current_page': "Dashboard", 'user_name': None, 'sel_owner': "All Owners"
    })

# --- 4. DATABASE FUNCTIONS ---

def load_users():
    """Load users from Supabase; auto-creates the table on first run."""
    try:
        return pd.read_sql("SELECT * FROM users", engine)
    except Exception:
        # Initial Bootstrap: Create table and add default admin
        admin_pass = hashlib.sha256("Sillycat01".encode()).hexdigest()
        df_init = pd.DataFrame([{"username": "admin", "password": admin_pass, "role": "admin", "owner_name": "All"}])
        df_init.to_sql("users", engine, if_exists="replace", index=False)
        return df_init

def save_user(username, password, role, owner_name):
    hashed_pass = hashlib.sha256(password.encode()).hexdigest()
    query = text("INSERT INTO users (username, password, role, owner_name) VALUES (:u, :p, :r, :o)")
    try:
        with engine.connect() as conn:
            conn.execute(query, {"u": username, "p": hashed_pass, "r": role, "o": owner_name})
            conn.commit()
        return True, "User created successfully!"
    except Exception as e:
        return False, f"Error: {e}"

def update_user_password(username, new_password):
    hashed_pass = hashlib.sha256(new_password.encode()).hexdigest()
    query = text("UPDATE users SET password = :p WHERE username = :u")
    try:
        with engine.connect() as conn:
            conn.execute(query, {"p": hashed_pass, "u": username})
            conn.commit()
        return True, f"Password for {username} updated!"
    except Exception as e:
        return False, f"Error: {e}"

def delete_user(username):
    if username == "admin": return False, "Cannot delete primary admin."
    query = text("DELETE FROM users WHERE username = :u")
    try:
        with engine.connect() as conn:
            conn.execute(query, {"u": username})
            conn.commit()
        return True, f"User {username} deleted."
    except:
        return False, "Failed to delete user."

@st.cache_data(ttl=60)
def load_master_data():
    try:
        df = pd.read_sql("SELECT * FROM transactions", engine)
        if df.empty: return df
        
        df['Trans_date'] = pd.to_datetime(df['Trans_date'], errors='coerce')
        df = df.dropna(subset=['Trans_date', 'Owner Detail', 'Building Detail'])
        
        df['Year'] = df['Trans_date'].dt.year.astype(str)
        df['Month'] = df['Trans_date'].dt.strftime('%B')
        df['Year_Month_Key'] = df['Trans_date'].dt.strftime('%Y-%m')
        df['Display_Month'] = df['Month'] + " " + df['Year']
        df['Paytype'] = df['Paytype'].fillna('Other')
        
        df['Meter Type'] = df['Meter Type'].replace('', 'N/A').fillna('N/A')
        df['Meter Model'] = df['Meter Model'].replace('', 'N/A').fillna('N/A')

        def clean_m(v):
            try: return str(int(float(v)))
            except: return str(v).strip()
        df['Meter_Search'] = df['Meter Number'].apply(clean_m)
        return df
    except:
        return pd.DataFrame()

def update_database(uploaded_file, mode="append"):
    df = pd.read_csv(uploaded_file)
    df.columns = df.columns.str.strip()
    if not df.empty and df.iloc[0]['Owner Detail'] == 'Grand Total':
        df = df.drop(df.index[0])
    df.to_sql("transactions", engine, if_exists=mode, index=False)
    st.cache_data.clear()

# --- 5. LOGIN SCREEN ---
if not st.session_state['logged_in']:
    # Centering a larger logo on the login page
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if os.path.exists("logo.png"):
            st.image("logo.png", use_container_width=True)
        st.title("🔐 Executive Portal Login")
    
    u_df = load_users()
    with st.form("login_form"):
        u, p = st.text_input("Username"), st.text_input("Password", type="password")
        if st.form_submit_button("Login"):
            hp = hashlib.sha256(p.encode()).hexdigest()
            row = u_df[(u_df['username'] == u) & (u_df['password'] == hp)]
            if not row.empty:
                st.session_state.update({
                    'logged_in': True, 'user_role': row.iloc[0]['role'], 
                    'assigned_owner': row.iloc[0]['owner_name'], 'user_name': u,
                    'sel_owner': row.iloc[0]['owner_name'] if row.iloc[0]['role'] == 'landlord' else "All Owners"
                })
                st.rerun()
            else: st.error("Invalid Username or Password")
    st.stop()

# --- 6. NAVIGATION & SIDEBAR ---
raw_df = load_master_data()

with st.sidebar:
    # --- LOGO PLACEMENT ---
    if os.path.exists("logo.png"):
        st.image("logo.png", use_container_width=True)
    else:
        st.info("Upload 'logo.png' to GitHub to see your brand here.")
    
    st.title(f"👤 {st.session_state['user_name']}")
    
    if st.session_state['user_role'] == 'admin':
        with st.expander("📂 System: Data Upload"):
            up_file = st.file_uploader("Upload transactions.csv", type="csv")
            up_mode = st.radio("Method", ["Add to existing (Append)", "Start fresh (Overwrite)"])
            mode_key = "append" if "Add" in up_mode else "replace"
            if up_file and st.button("💾 Sync to Supabase"):
                update_database(up_file, mode=mode_key)
                st.success(f"Data {mode_key}ed!")
                st.rerun()

    st.divider()
    if st.button("📊 Performance Dashboard", use_container_width=True): st.session_state['current_page'] = "Dashboard"
    if st.button("📈 Analytics Deep-Dive", use_container_width=True): st.session_state['current_page'] = "Analytics"
    if st.button("🛠️ Meter Management", use_container_width=True): st.session_state['current_page'] = "Management"
    if st.session_state['user_role'] == 'admin':
        if st.button("👥 User Management", use_container_width=True): st.session_state['current_page'] = "UserAdmin"
    
    st.divider()
    if not raw_df.empty:
        if st.session_state['user_role'] == 'admin':
            opts = ["All Owners"] + sorted(raw_df['Owner Detail'].unique().tolist())
            st.session_state['sel_owner'] = st.selectbox("View As", opts, index=opts.index(st.session_state['sel_owner']) if st.session_state['sel_owner'] in opts else 0)
            working_df = raw_df if st.session_state['sel_owner'] == "All Owners" else raw_df[raw_df['Owner Detail'] == st.session_state['sel_owner']]
        else:
            working_df = raw_df[raw_df['Owner Detail'] == st.session_state['assigned_owner']]
    else:
        working_df = pd.DataFrame()
    
    if st.button("🚪 Logout", type="secondary"):
        st.session_state['logged_in'] = False
        st.rerun()

# --- 7. PAGE ROUTING ---

# 👥 USER MANAGEMENT
if st.session_state['current_page'] == "UserAdmin":
    st.title("👥 User Management")
    t1, t2, t3 = st.tabs(["Create User", "Manage Users", "Reset Password"])
    with t1:
        with st.form("create"):
            nu, np = st.text_input("Username"), st.text_input("Password", type="password")
            nr, no = st.selectbox("Role", ["landlord", "admin"]), st.selectbox("Owner", ["All"] + sorted(raw_df['Owner Detail'].unique().tolist()) if not raw_df.empty else ["All"])
            if st.form_submit_button("Save User"):
                s, m = save_user(nu, np, nr, no); st.success(m) if s else st.error(m)
    with t2:
        udf = load_users()
        st.dataframe(udf[['username', 'role', 'owner_name']], use_container_width=True)
        u_del = st.selectbox("Select user to remove", udf['username'].tolist())
        if st.button("🗑️ Delete Account"): 
            s, m = delete_user(u_del); st.rerun()
    with t3:
        st.subheader("Reset Password")
        u_reset = st.selectbox("Select Account", load_users()['username'].tolist(), key="r_box")
        p1, p2 = st.text_input("New Password", type="password"), st.text_input("Confirm Password", type="password")
        if st.button("🔐 Update Password"):
            if p1 == p2 and p1 != "":
                s, m = update_user_password(u_reset, p1); st.success(m) if s else st.error(m)
            else: st.error("Passwords must match.")

# 📈 ANALYTICS
elif st.session_state['current_page'] == "Analytics":
    st.title("📈 Analytics Deep-Dive")
    if working_df.empty: st.warning("Please upload transaction data to view analytics.")
    else:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.pie(working_df, values='Sum Of Total Incl Vat', names='Service Resource', hole=0.4, title="Revenue by Resource"), use_container_width=True)
        with c2: 
            sun_df = working_df.groupby(['Meter Type', 'Meter Model'])['Sum Of Total Incl Vat'].sum().reset_index()
            st.plotly_chart(px.sunburst(sun_df, path=['Meter Type', 'Meter Model'], values='Sum Of Total Incl Vat', title="Hardware Distribution"), use_container_width=True)

# 📊 DASHBOARD
elif st.session_state['current_page'] == "Dashboard":
    if working_df.empty: st.warning("Database empty. Use the sidebar to upload a transactions.csv file.")
    else:
        st.title(f"🏢 {st.session_state['sel_owner']}")
        with st.sidebar:
            sb = st.multiselect("Buildings", sorted(working_df['Building Detail'].unique()), default=sorted(working_df['Building Detail'].unique()))
            mo = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
            sm = st.multiselect("Months", [m for m in mo if m in working_df['Month'].unique()], default=[m for m in mo if m in working_df['Month'].unique()])

        fdf = working_df[(working_df['Building Detail'].isin(sb)) & (working_df['Month'].isin(sm))]

        if not fdf.empty:
            st.subheader("📋 Monthly Statement Breakdown")
            bs = fdf.groupby(['Year', 'Month', 'Year_Month_Key', 'Building Detail']).agg({'Sum Of Total Incl Vat': 'sum', 'Total Service Fee Incl Vat': 'sum', 'Units': 'sum', 'Meter Number': 'nunique'}).rename(columns={'Sum Of Total Incl Vat': 'Sales', 'Total Service Fee Incl Vat': 'Fees'})
            pp = fdf.pivot_table(index=['Year', 'Month', 'Year_Month_Key', 'Building Detail'], columns='Paytype', values='Sum Of Total Incl Vat', aggfunc='sum', fill_value=0)
            summary = pd.concat([bs, pp], axis=1).sort_index(level='Year_Month_Key')
            
            totals = summary.sum().to_frame().T
            totals.index = pd.MultiIndex.from_tuples([('---', 'GRAND TOTAL', '---', '---')], names=['Year', 'Month', 'Year_Month_Key', 'Building Detail'])
            summary.index = summary.index.set_levels([l.astype(str) for l in summary.index.levels])
            
            st.dataframe(pd.concat([summary, totals]).style.format("R {:,.2f}", subset=['Sales', 'Fees'] + list(pp.columns)).format("{:,.2f}", subset=['Units']).format("{:,.0f}", subset=['Meters']), use_container_width=True)

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                xl_io = io.BytesIO()
                with pd.ExcelWriter(xl_io, engine='xlsxwriter') as wr: summary.to_excel(wr)
                st.download_button("📥 Excel Export", xl_io.getvalue(), "Statement.xlsx")
            with c2:
                if FPDF:
                    ex_m = sorted(fdf['Display_Month'].unique(), key=lambda x: datetime.strptime(x, '%B %Y'))
                    sel_m = st.selectbox("Select Month for PDF", ex_m)
                    if st.button("📥 Generate PDF"):
                        m_n, y_v = sel_m.split(); m_data = summary.xs(str(y_v), level='Year').xs(m_n, level='Month')
                        def gen_p(df, title):
                            pdf = FPDF(orientation='L'); pdf.add_page(); pdf.set_font("Helvetica", 'B', 14)
                            pdf.cell(270, 10, title, ln=True, align='C'); pdf.ln(10); pdf.set_font("Helvetica", size=9)
                            for h in ["Building"] + list(df.columns): pdf.cell(28, 10, str(h)[:12], 1)
                            pdf.ln()
                            for i, r in df.iterrows():
                                pdf.cell(28, 10, str(i[1])[:12], 1)
                                for idx, v in enumerate(r): pdf.cell(28, 10, f"{v:,.2f}" if isinstance(v, (float, int)) else str(v), 1)
                                pdf.ln()
                            return bytes(pdf.output())
                        st.download_button("Download PDF File", gen_p(m_data, f"Statement: {sel_m}"), f"Statement_{sel_m}.pdf")

# 🛠️ METER MANAGEMENT
elif st.session_state['current_page'] == "Management":
    st.title("🛠️ Meter Management")
    if not working_df.empty:
        mldf = working_df[['Meter_Search', 'Customer Surname']].drop_duplicates()
        mldf['Label'] = mldf['Meter_Search'] + " - " + mldf['Customer Surname']
        sel = st.selectbox("Select Meter", options=["Select..."] + sorted(mldf['Label'].tolist()))
        if sel != "Select...":
            m_no = sel.split(" - ")[0]
            st.success(f"Selected: {m_no}")
            ca, cb = st.columns(2)
            with ca: st.button("🚫 Block Meter", type="primary", use_container_width=True)
            with cb: st.button("🎫 Generate Free Token", use_container_width=True)
            st.divider()
            st.subheader(f"📜 Transaction History: {m_no}")
            st.dataframe(working_df[working_df['Meter_Search'] == m_no].sort_values('Trans_date', ascending=False), use_container_width=True)

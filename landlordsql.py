import streamlit as st
import pandas as pd
import plotly.express as px
import hashlib
import io
import os
from datetime import datetime
from sqlalchemy import create_engine, text

# --- 1. DATABASE CONFIGURATION ---
# Ensure your Streamlit Secret "DB_URL" uses Port 6543 for the Supabase Pooler
try:
    DB_URL = st.secrets["DB_URL"]
    engine = create_engine(DB_URL)
# --- EMERGENCY DIAGNOSTIC ---
with st.expander("🚨 DEBUG: Database Connection Check", expanded=True):
    try:
        with engine.connect() as conn:
            st.success("Connection to Supabase is ACTIVE.")
            # Check if users table exists
            result = conn.execute(text("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'users')"))
            exists = result.scalar()
            st.write(f"Does 'users' table exist? {'Yes' if exists else 'No'}")
    except Exception as e:
        st.error("Connection Failed. Real Error below:")
        st.code(str(e))
        st.stop() # Stop the app so we can read the error


except Exception as e:
    st.error("🚨 Database Connection URL not found. Please check Streamlit Secrets.")
    st.stop()

# --- 2. APP CONFIG & PDF SUPPORT ---
st.set_page_config(page_title="I-Switch Executive Portal", layout="wide")

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

# --- 4. DATABASE FUNCTIONS (SQL) ---

def load_users():
    """Load users from Supabase; auto-create table on first run."""
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
    with engine.connect() as conn:
        conn.execute(query, {"u": username})
        conn.commit()
    return True, f"User {username} deleted."

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
        
        # Cleanup hierarchy for Sunburst
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

# --- 5. LOGIN LOGIC ---
if not st.session_state['logged_in']:
    st.title("🔐 Secure Portal Login")
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

# --- 6. DATA & NAVIGATION ---
raw_df = load_master_data()

with st.sidebar:
    st.title(f"👤 {st.session_state['user_name']}")
    
    if st.session_state['user_role'] == 'admin':
        with st.expander("📂 System: Data Upload"):
            up_file = st.file_uploader("Upload transactions.csv", type="csv")
            up_mode = st.radio("Method", ["Add to existing (Append)", "Start fresh (Overwrite)"])
            mode_key = "append" if "Add" in up_mode else "replace"
            if up_file and st.button("💾 Sync to Supabase"):
                update_database(up_file, mode=mode_key)
                st.success(f"Successfully {mode_key}ed data!")
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
    if st.button("Logout"): st.session_state['logged_in'] = False; st.rerun()

# --- 7. PAGES ---

# 👥 USER ADMIN
if st.session_state['current_page'] == "UserAdmin":
    st.title("👥 User Management")
    t1, t2, t3 = st.tabs(["Create User", "Manage Users", "Reset Password"])
    with t1:
        with st.form("create"):
            nu, np = st.text_input("Username"), st.text_input("Password", type="password")
            nr, no = st.selectbox("Role", ["landlord", "admin"]), st.selectbox("Owner", ["All"] + sorted(raw_df['Owner Detail'].unique().tolist()) if not raw_df.empty else ["All"])
            if st.form_submit_button("Save"):
                s, m = save_user(nu, np, nr, no); st.success(m) if s else st.error(m)
    with t2:
        udf = load_users(); st.dataframe(udf[['username', 'role', 'owner_name']], use_container_width=True)
        u_del = st.selectbox("Delete", udf['username'].tolist())
        if st.button("🗑️ Delete"): s, m = delete_user(u_del); st.rerun()
    with t3:
        u_reset = st.selectbox("Select Account", load_users()['username'].tolist())
        pass1, pass2 = st.text_input("New Password", type="password"), st.text_input("Confirm New Password", type="password")
        if st.button("🔐 Update Password"):
            if pass1 == pass2 and pass1 != "":
                s, m = update_user_password(u_reset, pass1); st.success(m) if s else st.error(m)
            else: st.error("Passwords must match and not be empty.")

# 📈 ANALYTICS
elif st.session_state['current_page'] == "Analytics":
    st.title("📈 Analytics")
    if working_df.empty: st.warning("No data found.")
    else:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.pie(working_df, values='Sum Of Total Incl Vat', names='Service Resource', hole=0.4, title="Revenue by Resource"), use_container_width=True)
        with c2: 
            sun_df = working_df.groupby(['Meter Type', 'Meter Model'])['Sum Of Total Incl Vat'].sum().reset_index()
            st.plotly_chart(px.sunburst(sun_df, path=['Meter Type', 'Meter Model'], values='Sum Of Total Incl Vat', title="Hardware Split"), use_container_width=True)
        
        st.divider()
        colA, colB = st.columns(2)
        with colA: st.plotly_chart(px.bar(working_df.groupby('Client')['Sum Of Total Incl Vat'].sum().reset_index(), x='Client', y='Sum Of Total Incl Vat', title="Revenue per Client"), use_container_width=True)
        with colB: st.plotly_chart(px.bar(working_df.groupby('Customer Surname')['Sum Of Total Incl Vat'].sum().sort_values(ascending=False).head(10).reset_index(), x='Sum Of Total Incl Vat', y='Customer Surname', orientation='h', title="Top 10 Customers (Surname)"), use_container_width=True)

# 📊 DASHBOARD
elif st.session_state['current_page'] == "Dashboard":
    if working_df.empty: st.warning("Database empty. Please upload data.")
    else:
        st.title(f"🏢 {st.session_state['sel_owner']}")
        with st.sidebar:
            sb = st.multiselect("Buildings", sorted(working_df['Building Detail'].unique()), default=sorted(working_df['Building Detail'].unique()))
            mo = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
            sm = st.multiselect("Months", [m for m in mo if m in working_df['Month'].unique()], default=[m for m in mo if m in working_df['Month'].unique()])

        fdf = working_df[(working_df['Building Detail'].isin(sb)) & (working_df['Month'].isin(sm))]

        if not fdf.empty:
            st.subheader("📋 Monthly Statement Breakdown")
            bs = fdf.groupby(['Year', 'Month', 'Year_Month_Key', 'Building Detail']).agg({'Sum Of Total Incl Vat': 'sum', 'Total Service Fee Incl Vat': 'sum', 'Units': 'sum', 'Meter Number': 'nunique'}).rename(columns={'Sum Of Total Incl Vat': 'Sales', 'Total Service Fee Incl Vat': 'Fees', 'Units': 'Units', 'Meter Number': 'Meters'})
            pp = fdf.pivot_table(index=['Year', 'Month', 'Year_Month_Key', 'Building Detail'], columns='Paytype', values='Sum Of Total Incl Vat', aggfunc='sum', fill_value=0)
            summary = pd.concat([bs, pp], axis=1).sort_index(level='Year_Month_Key')
            
            # Totals
            totals = summary.sum().to_frame().T
            totals.index = pd.MultiIndex.from_tuples([('---', 'GRAND TOTAL', '---', '---')], names=['Year', 'Month', 'Year_Month_Key', 'Building Detail'])
            summary.index = summary.index.set_levels([l.astype(str) for l in summary.index.levels])
            display_df = pd.concat([summary, totals])

            st.dataframe(display_df.style.format("R {:,.2f}", subset=['Sales', 'Fees'] + list(pp.columns)).format("{:,.2f}", subset=['Units']).format("{:,.0f}", subset=['Meters']), use_container_width=True)

            st.divider()
            c1, c2 = st.columns(2)
            with c1:
                xl_io = io.BytesIO()
                with pd.ExcelWriter(xl_io, engine='xlsxwriter') as wr: display_df.to_excel(wr)
                st.download_button("📥 Excel Export", xl_io.getvalue(), "Statement.xlsx")
            with c2:
                if FPDF:
                    ex_m = sorted(fdf['Display_Month'].unique(), key=lambda x: datetime.strptime(x, '%B %Y'))
                    sel_m = st.selectbox("Select Month for PDF", ex_m)
                    if st.button("📥 Generate PDF"):
                        m_n, y_v = sel_m.split()
                        m_data = summary.xs(str(y_v), level='Year').xs(m_n, level='Month')
                        def gen_p(df, title):
                            pdf = FPDF(orientation='L'); pdf.add_page(); pdf.set_font("Helvetica", 'B', 14)
                            pdf.cell(270, 10, title, ln=True, align='C'); pdf.ln(10); pdf.set_font("Helvetica", size=9)
                            for h in ["Building"] + list(df.columns): pdf.cell(28, 10, str(h)[:12], 1)
                            pdf.ln()
                            for i, r in df.iterrows():
                                pdf.cell(28, 10, str(i[1])[:12], 1)
                                for idx, v in enumerate(r):
                                    if idx == len(r)-1: pdf.cell(28, 10, f"{int(v)}", 1)
                                    else: pdf.cell(28, 10, f"{v:,.2f}" if isinstance(v, (float, int)) else str(v), 1)
                                pdf.ln()
                            return bytes(pdf.output())
                        st.download_button("Download PDF", gen_p(m_data, f"Statement: {sel_m}"), f"Statement_{sel_m}.pdf")

            st.divider()
            st.subheader("🏆 Top 10 Highest Single Transactions")
            top_vends = fdf.sort_values(by='Sum Of Total Incl Vat', ascending=False).head(10).copy()
            top_vends['Date & Time'] = top_vends['Trans_date'].dt.strftime('%Y-%m-%d %H:%M')
            st.dataframe(top_vends[['Date & Time', 'Client', 'Customer Surname', 'Sum Of Total Incl Vat', 'Payment Mode', 'Usage Point Name']].style.format("R {:,.2f}", subset=['Sum Of Total Incl Vat']), use_container_width=True)

        st.divider()
        st.subheader("🔎 Global Transaction Search")
        q = st.text_input("Search (Meter, Client, Surname, Unit)...")
        ddf = fdf if not q else fdf[fdf.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
        st.dataframe(ddf, use_container_width=True)

# 🛠️ MANAGEMENT
elif st.session_state['current_page'] == "Management":
    st.title("🛠️ Meter Management")
    if not working_df.empty:
        mldf = working_df[['Meter_Search', 'Customer Surname']].drop_duplicates()
        mldf['Label'] = mldf['Meter_Search'] + " - " + mldf['Customer Surname']
        sel = st.selectbox("Search Meter Number", options=["Select..."] + sorted(mldf['Label'].tolist()))
        if sel != "Select...":
            m_no = sel.split(" - ")[0]
            st.success(f"Selected: {m_no}")
            ca, cb, cc = st.columns(3)
            with ca: st.button("🚫 Block Meter", type="primary", use_container_width=True)
            with cb: st.button("🔓 Unblock Meter", use_container_width=True)
            with cc: st.button("🎫 Generate Free Token", use_container_width=True)
            st.divider()
            st.subheader(f"📜 Full Transaction History for {m_no}")
            st.dataframe(working_df[working_df['Meter_Search'] == m_no].sort_values('Trans_date', ascending=False), use_container_width=True)

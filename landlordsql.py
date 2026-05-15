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
    page_icon="logo.png",
    layout="wide"
)

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
    try:
        return pd.read_sql("SELECT * FROM users", engine)
    except Exception:
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
        
        # Ensure 'Units' is numeric for math
        df['Units'] = pd.to_numeric(df['Units'], errors='coerce').fillna(0)
        df['Sum Of Total Incl Vat'] = pd.to_numeric(df['Sum Of Total Incl Vat'], errors='coerce').fillna(0)
        df['Total Service Fee Incl Vat'] = pd.to_numeric(df['Total Service Fee Incl Vat'], errors='coerce').fillna(0)
        
        df['Trans_date'] = pd.to_datetime(df['Trans_date'], errors='coerce')
        df = df.dropna(subset=['Trans_date', 'Owner Detail', 'Building Detail'])
        
        df['Year'] = df['Trans_date'].dt.year.astype(str)
        df['Month'] = df['Trans_date'].dt.strftime('%B')
        df['Year_Month_Key'] = df['Trans_date'].dt.strftime('%Y-%m')
        df['Display_Month'] = df['Month'] + " " + df['Year']
        df['Paytype'] = df['Paytype'].fillna('Other')

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

# --- 5. LOGIN ---
if not st.session_state['logged_in']:
    c1, c2, c3 = st.columns([1, 2, 1])
    with c2:
        if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
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
            else: st.error("Invalid Login")
    st.stop()

# --- 6. NAVIGATION ---
raw_df = load_master_data()

with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
    st.title(f"👤 {st.session_state['user_name']}")
    
    if st.session_state['user_role'] == 'admin':
        with st.expander("📂 System: Data Upload"):
            up_file = st.file_uploader("Upload transactions.csv", type="csv")
            up_mode = st.radio("Method", ["Add to existing (Append)", "Start fresh (Overwrite)"])
            mode_key = "append" if "Add" in up_mode else "replace"
            if up_file and st.button("💾 Sync to Supabase"):
                update_database(up_file, mode=mode_key)
                st.success("Database Updated!")
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
    if st.button("🚪 Logout"): st.session_state['logged_in'] = False; st.rerun()

# --- 7. PAGES ---

if st.session_state['current_page'] == "UserAdmin":
    st.title("👥 User Management")
    t1, t2, t3 = st.tabs(["Create User", "Manage Users", "Reset Password"])
    with t1:
        with st.form("c"):
            nu, np = st.text_input("Username"), st.text_input("Password", type="password")
            nr, no = st.selectbox("Role", ["landlord", "admin"]), st.selectbox("Owner", ["All"] + sorted(raw_df['Owner Detail'].unique().tolist()) if not raw_df.empty else ["All"])
            if st.form_submit_button("Save"):
                s, m = save_user(nu, np, nr, no); st.success(m) if s else st.error(m)
    with t2:
        udf = load_users()
        st.dataframe(udf[['username', 'role', 'owner_name']], use_container_width=True)
        u_del = st.selectbox("Delete Account", udf['username'].tolist())
        if st.button("🗑️ Confirm Delete"): s, m = delete_user(u_del); st.rerun()
    with t3:
        u_reset = st.selectbox("Account to Reset", load_users()['username'].tolist(), key="reset_u")
        p1, p2 = st.text_input("New Password", type="password"), st.text_input("Confirm Password", type="password")
        if st.button("🔐 Update"):
            if p1 == p2 and p1 != "":
                s, m = update_user_password(u_reset, p1); st.success(m) if s else st.error(m)
            else: st.error("Mismatch.")

elif st.session_state['current_page'] == "Analytics":
    st.title("📈 Analytics")
    if working_df.empty: st.warning("No data.")
    else:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.pie(working_df, values='Sum Of Total Incl Vat', names='Service Resource', hole=0.4, title="Revenue by Resource"), use_container_width=True)
        with c2: 
            sun_agg = working_df.groupby(['Meter Type', 'Meter Model'])['Sum Of Total Incl Vat'].sum().reset_index()
            st.plotly_chart(px.sunburst(sun_agg, path=['Meter Type', 'Meter Model'], values='Sum Of Total Incl Vat', title="Hardware Split"), use_container_width=True)

elif st.session_state['current_page'] == "Dashboard":
    if working_df.empty: st.warning("No data found.")
    else:
        st.title(f"🏢 {st.session_state['sel_owner']}")
        with st.sidebar:
            sb = st.multiselect("Buildings", sorted(working_df['Building Detail'].unique()), default=sorted(working_df['Building Detail'].unique()))
            mo = ['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August', 'September', 'October', 'November', 'December']
            sm = st.multiselect("Months", [m for m in mo if m in working_df['Month'].unique()], default=[m for m in mo if m in working_df['Month'].unique()])

        fdf = working_df[(working_df['Building Detail'].isin(sb)) & (working_df['Month'].isin(sm))]

        if not fdf.empty:
            st.subheader("📋 Monthly Statement Breakdown")
            
            # Aggregate and Rename
            bs = fdf.groupby(['Year', 'Month', 'Year_Month_Key', 'Building Detail']).agg({
                'Sum Of Total Incl Vat': 'sum', 
                'Total Service Fee Incl Vat': 'sum', 
                'Units': 'sum', 
                'Meter Number': 'nunique'
            }).rename(columns={
                'Sum Of Total Incl Vat': 'Sales', 
                'Total Service Fee Incl Vat': 'Fees',
                'Units': 'Units',
                'Meter Number': 'Meters'
            })

            pp = fdf.pivot_table(index=['Year', 'Month', 'Year_Month_Key', 'Building Detail'], columns='Paytype', values='Sum Of Total Incl Vat', aggfunc='sum', fill_value=0)
            summary = pd.concat([bs, pp], axis=1).sort_index(level='Year_Month_Key')
            
            totals = summary.sum().to_frame().T
            totals.index = pd.MultiIndex.from_tuples([('---', 'GRAND TOTAL', '---', '---')], names=['Year', 'Month', 'Year_Month_Key', 'Building Detail'])
            summary.index = summary.index.set_levels([l.astype(str) for l in summary.index.levels])
            
            # --- ROBUST TABLE DISPLAY ---
            combined_display = pd.concat([summary, totals])
            all_cols = combined_display.columns.tolist()
            currency_cols = [c for c in ['Sales', 'Fees'] + list(pp.columns) if c in all_cols]
            
            styler = combined_display.style
            if currency_cols: styler = styler.format("R {:,.2f}", subset=currency_cols)
            if 'Units' in all_cols: styler = styler.format("{:,.2f}", subset=['Units'])
            if 'Meters' in all_cols: styler = styler.format("{:,.0f}", subset=['Meters'])

            st.dataframe(styler, use_container_width=True)

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
                        st.download_button("Download PDF", gen_p(m_data, f"Statement: {sel_m}"), f"Statement_{sel_m}.pdf")

elif st.session_state['current_page'] == "Management":
    st.title("🛠️ Meter Management")
    if not working_df.empty:
        # Use 'Unit' (Flat Name) and 'Customer Surname' to make search easier
        mldf = working_df[['Meter_Search', 'Unit', 'Customer Surname']].drop_duplicates()
        mldf['Label'] = mldf['Meter_Search'] + " - Flat: " + mldf['Unit'].astype(str) + " (" + mldf['Customer Surname'] + ")"
        sel = st.selectbox("Search Meter", options=["Select..."] + sorted(mldf['Label'].tolist()))
        if sel != "Select...":
            m_no = sel.split(" - ")[0]
            st.success(f"Selected: {m_no}")
            ca, cb = st.columns(2)
            with ca: st.button("🚫 Block Meter", type="primary", use_container_width=True)
            with cb: st.button("🎫 Generate Free Token", use_container_width=True)
            st.divider()
            st.subheader(f"📜 History for {m_no}")
            st.dataframe(working_df[working_df['Meter_Search'] == m_no].sort_values('Trans_date', ascending=False), use_container_width=True)

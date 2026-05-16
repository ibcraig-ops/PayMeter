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
    st.error("🚨 System Connection Traceback Error Logged:")
    st.exception(e)
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

# --- 5. EXECUTIVE EXECUTIVE PDF REPORT TEMPLATE ---
def gen_executive_sales_report_pdf(summary_df, total_metrics, period_label, portfolio_label, logo_path="logo.png"):
    if not FPDF:
        return None
        
    pdf = FPDF(orientation='L', unit='mm', format='A4')
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    
    pdf.set_fill_color(30, 58, 138) 
    pdf.rect(0, 0, 297, 32, 'F')
    
    if os.path.exists(logo_path):
        try: pdf.image(logo_path, x=12, y=5, h=22)
        except: pass
            
    pdf.set_text_color(255, 255, 255)
    pdf.set_font("Helvetica", 'B', 18)
    pdf.set_xy(80, 8)
    pdf.cell(205, 8, "EXECUTIVE SALES & UTILITY REVENUE REPORT", ln=True, align='R')
    pdf.set_font("Helvetica", 'I', 10)
    pdf.set_x(80)
    pdf.cell(205, 5, f"Portfolio Scope: {portfolio_label}   |   Reporting Window: {period_label}", ln=True, align='R')
    
    pdf.set_text_color(51, 65, 85) 
    pdf.set_font("Helvetica", size=9)
    pdf.set_xy(12, 38)
    pdf.cell(100, 5, f"Document ID: ISR-{random.randint(100000, 999999)}", ln=True)
    pdf.set_x(12)
    pdf.cell(100, 5, f"Generated On: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}", ln=True)
    pdf.ln(4)
    
    pdf.set_fill_color(241, 245, 249) 
    pdf.set_draw_color(226, 232, 240)
    
    pdf.rect(12, 50, 62, 18, 'DF')
    pdf.set_xy(14, 52)
    pdf.set_font("Helvetica", '', 8)
    pdf.cell(58, 4, "TOTAL GROSS SALES", ln=True)
    pdf.set_xy(14, 57)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.set_text_color(13, 148, 136) 
    pdf.cell(58, 8, f"R {total_metrics['gross']:,.2f}", ln=True)
    
    pdf.set_text_color(51, 65, 85)
    pdf.rect(80, 50, 62, 18, 'DF')
    pdf.set_xy(82, 52)
    pdf.set_font("Helvetica", '', 8)
    pdf.cell(58, 4, "PRINCIPLE REVENUE SHARE", ln=True)
    pdf.set_xy(82, 57)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(58, 8, f"R {total_metrics['net']:,.2f}", ln=True)
    
    pdf.rect(148, 50, 62, 18, 'DF')
    pdf.set_xy(150, 52)
    pdf.set_font("Helvetica", '', 8)
    pdf.cell(58, 4, "TOTAL SERVICE FEES", ln=True)
    pdf.set_xy(150, 57)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(58, 8, f"R {total_metrics['fees']:,.2f}", ln=True)
    
    pdf.rect(216, 50, 69, 18, 'DF')
    pdf.set_xy(218, 52)
    pdf.set_font("Helvetica", '', 8)
    pdf.cell(65, 4, "CUMULATIVE UNITS CONSUMED", ln=True)
    pdf.set_xy(218, 57)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(65, 8, f"{total_metrics['units']:,.2f} Units", ln=True)
    
    pdf.ln(12)
    
    pdf.set_font("Helvetica", 'B', 10)
    pdf.set_text_color(30, 58, 138)
    pdf.set_x(12)
    pdf.cell(200, 6, "DETAILED REVENUE BREAKDOWN BY ASSET LOCATION", ln=True)
    pdf.ln(2)
    
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.set_draw_color(30, 58, 138)
    pdf.set_font("Helvetica", 'B', 8)
    
    col_w = [22, 63, 24, 33, 33, 33, 22, 23, 20]
    headers = ["PERIOD", "BUILDING DETAIL", "UTILITY", "GROSS SALES", "PRINCIPLE PAY", "SERVICE FEES", "VAT ACCR", "UNITS", "TX COUNT"]
    
    pdf.set_x(12)
    for w, h in zip(col_w, headers): pdf.cell(w, 8, h, 1, 0, 'C', True)
    pdf.ln()
    
    pdf.set_text_color(51, 65, 85)
    pdf.set_draw_color(226, 232, 240) 
    
    toggle_fill = False
    for _, r in summary_df.iterrows():
        pdf.set_x(12)
        pdf.set_font("Helvetica", '', 8)
        if toggle_fill: pdf.set_fill_color(248, 250, 252)
        else: pdf.set_fill_color(255, 255, 255)
            
        pdf.cell(col_w[0], 7, str(r['Period']), 1, 0, 'C', True)
        pdf.cell(col_w[1], 7, str(r['Building Location'])[:34], 1, 0, 'L', True)
        pdf.cell(col_w[2], 7, str(r['Utility Type']), 1, 0, 'C', True)
        pdf.cell(col_w[3], 7, f"R {r['Gross Sales']:,.2f}", 1, 0, 'R', True)
        pdf.cell(col_w[4], 7, f"R {r['Net To Principle']:,.2f}", 1, 0, 'R', True)
        pdf.cell(col_w[5], 7, f"R {r['Service Fees']:,.2f}", 1, 0, 'R', True)
        pdf.cell(col_w[6], 7, f"R {r['VAT']:,.2f}", 1, 0, 'R', True)
        pdf.cell(col_w[7], 7, f"{r['Units Consumed']:,.2f}", 1, 0, 'R', True)
        pdf.cell(col_w[8], 7, f"{int(r['Transactions'])}", 1, 0, 'C', True)
        pdf.ln()
        toggle_fill = not toggle_fill
        
    pdf.set_x(12)
    pdf.set_font("Helvetica", 'B', 8)
    pdf.set_fill_color(226, 232, 240)
    pdf.cell(col_w[0] + col_w[1] + col_w[2], 8, "PORTFOLIO AGGREGATE TOTALS", 1, 0, 'L', True)
    pdf.cell(col_w[3], 8, f"R {total_metrics['gross']:,.2f}", 1, 0, 'R', True)
    pdf.cell(col_w[4], 8, f"R {total_metrics['net']:,.2f}", 1, 0, 'R', True)
    pdf.cell(col_w[5], 8, f"R {total_metrics['fees']:,.2f}", 1, 0, 'R', True)
    pdf.cell(col_w[6], 8, f"R {total_metrics['vat']:,.2f}", 1, 0, 'R', True)
    pdf.cell(col_w[7], 8, f"{total_metrics['units']:,.2f}", 1, 0, 'R', True)
    pdf.cell(col_w[8], 8, f"{int(total_metrics['tx_count'])}", 1, 0, 'C', True)
    
    try: return pdf.output(dest='S').encode('latin-1')
    except: return pdf.output()

# --- 6. DATABASE FUNCTIONS ---
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
        df['Payment To Principle'] = pd.to_numeric(df['Payment To Principle'], errors='coerce').fillna(0)
        df['Total Service Fee Incl Vat'] = pd.to_numeric(df['Total Service Fee Incl Vat'], errors='coerce').fillna(0)
        df['Vat'] = pd.to_numeric(df['Vat'], errors='coerce').fillna(0)
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

# --- 7. LOGIN GATING ---
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

# --- 8. NAVIGATION & BASE SIDEBAR ---
raw_df = load_master_data()

with st.sidebar:
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
    st.title(f"👤 {st.session_state['user_name']}")
    
    if st.session_state['user_role'] == 'admin':
        with st.expander("📂 Data Sync"):
            up = st.file_uploader("Upload CSV", type="csv")
            md = "replace" if st.radio("Mode", ["Overwrite", "Append"]) == "Overwrite" else "append"
            if up and st.button("Sync Now"): update_database(up, md); st.rerun()
            
    st.divider()
    st.button("📊 Dashboard", on_click=lambda: st.session_state.update({'current_page': 'Dashboard'}), use_container_width=True)
    st.button("📈 Analytics", on_click=lambda: st.session_state.update({'current_page': 'Analytics'}), use_container_width=True)
    st.button("🗂️ Reporting Suite", on_click=lambda: st.session_state.update({'current_page': 'Reporting'}), use_container_width=True)
    st.button("🛠️ Meters Control", on_click=lambda: st.session_state.update({'current_page': 'Management'}), use_container_width=True)
    if st.session_state['user_role'] == 'admin' and st.button("👥 Users Panel", use_container_width=True):
        st.session_state['current_page'] = "UserAdmin"
    
    st.divider()
    if not raw_df.empty and st.session_state['user_role'] == 'admin':
        opts = ["All Owners"] + sorted(raw_df['Owner Detail'].unique().tolist())
        st.session_state['sel_owner'] = st.selectbox("View Portfolio Scope:", opts)

# --- 9. SIDEBAR CONTROL CONTROLLERS ---
working_df = raw_df if st.session_state['sel_owner'] == "All Owners" else raw_df[raw_df['Owner Detail'] == st.session_state['sel_owner']]

chron_timeline = []
selected_months = []

if st.session_state['current_page'] in ["Dashboard", "Analytics", "Reporting"]:
    if working_df.empty:
        st.sidebar.warning("No transactional database content found.")
        fdf = working_df
    else:
        with st.sidebar:
            st.markdown("### 🔍 Live Dataset Filters")
            sb = st.multiselect("Filter Asset Buildings", sorted(working_df['Building Detail'].unique()), default=sorted(working_df['Building Detail'].unique()))
            chron_timeline = working_df.sort_values('Year_Month_Key')['Display_Month'].unique().tolist()
            selected_months = st.multiselect("Filter Months/Years", chron_timeline, default=chron_timeline)
            st.divider()
            if st.button("Logout", use_container_width=True): st.session_state['logged_in'] = False; st.rerun()
        fdf = working_df[(working_df['Building Detail'].isin(sb)) & (working_df['Display_Month'].isin(selected_months))]
else:
    with st.sidebar:
        if st.button("Logout", use_container_width=True): st.session_state['logged_in'] = False; st.rerun()

# --- 10. PAGES ---

if st.session_state['current_page'] == "Dashboard":
    if fdf.empty: st.warning("No data matches selected timeline or building parameters.")
    else:
        st.title(f"🏢 {st.session_state['sel_owner']} Overview")
        
        st.subheader("📈 Performance Trend")
        trend_data = fdf.groupby('Year_Month_Key')['Sum Of Total Incl Vat'].sum().reset_index()
        st.plotly_chart(px.bar(
            trend_data, 
            x='Year_Month_Key', 
            y='Sum Of Total Incl Vat', 
            color='Year_Month_Key', 
            title="Gross Revenue Breakdown per Month",
            labels={'Sum Of Total Incl Vat': 'Sales Revenue (R)', 'Year_Month_Key': 'Timeline Period'}
        ), use_container_width=True)
        
        st.divider()
        st.subheader("📋 Monthly Breakdown")
        
        if st.session_state['sel_owner'] == "All Owners":
            summary = fdf.groupby(['Year_Month_Key']).agg({
                'Sum Of Total Incl Vat': 'sum', 
                'Units': 'sum', 
                'Meter Number': 'nunique',
                'Unique Id': 'count'
            }).rename(columns={
                'Sum Of Total Incl Vat': 'Sales', 
                'Units': 'Consumption', 
                'Meter Number': 'Meters',
                'Unique Id': 'Transactions'
            })
            summary_flat = summary.reset_index()
            
            total_row = pd.DataFrame([{
                'Year_Month_Key': 'Grand Total',
                'Sales': summary_flat['Sales'].sum(),
                'Consumption': summary_flat['Consumption'].sum(),
                'Meters': int(fdf['Meter Number'].nunique()),
                'Transactions': int(summary_flat['Transactions'].sum())
            }])
        else:
            summary = fdf.groupby(['Year_Month_Key', 'Building Detail']).agg({
                'Sum Of Total Incl Vat': 'sum', 
                'Units': 'sum', 
                'Meter Number': 'nunique',
                'Unique Id': 'count'
            }).rename(columns={
                'Sum Of Total Incl Vat': 'Sales', 
                'Units': 'Consumption', 
                'Meter Number': 'Meters',
                'Unique Id': 'Transactions'
            })
            summary_flat = summary.reset_index()
            
            total_row = pd.DataFrame([{
                'Year_Month_Key': 'Grand Total',
                'Building Detail': '',
                'Sales': summary_flat['Sales'].sum(),
                'Consumption': summary_flat['Consumption'].sum(),
                'Meters': int(fdf['Meter Number'].nunique()),
                'Transactions': int(summary_flat['Transactions'].sum())
            }])
        
        summary_with_total = pd.concat([summary_flat, total_row], ignore_index=True)
        
        summary_with_total['Sales'] = pd.to_numeric(summary_with_total['Sales'], errors='coerce').fillna(0)
        summary_with_total['Consumption'] = pd.to_numeric(summary_with_total['Consumption'], errors='coerce').fillna(0)
        summary_with_total['Meters'] = pd.to_numeric(summary_with_total['Meters'], errors='coerce').fillna(0).astype(int)
        summary_with_total['Transactions'] = pd.to_numeric(summary_with_total['Transactions'], errors='coerce').fillna(0).astype(int)
        
        st.dataframe(summary_with_total.style.format({
            'Sales': 'R {:,.2f}', 
            'Consumption': '{:,.2f}',
            'Meters': '{:,}',
            'Transactions': '{:,}'
        }), use_container_width=True)
        
        c1, c2 = st.columns(2)
        with c1:
            xl = io.BytesIO()
            with pd.ExcelWriter(xl) as wr: summary_with_total.to_excel(wr, index=False)
            st.download_button("📥 Excel Export", xl.getvalue(), "Statement.xlsx")
        with c2:
            if FPDF:
                ex_m = sorted(fdf['Display_Month'].unique())
                sel_m = st.selectbox("Select Month for PDF Summary", ex_m)
                if st.button("📥 Generate PDF Breakdown"):
                    m_data = fdf[fdf['Display_Month'] == sel_m].groupby('Building Detail').agg({'Sum Of Total Incl Vat': 'sum', 'Units': 'sum'})
                    st.download_button("Download PDF", gen_p(m_data, f"Report: {sel_m}"), "Report.pdf")

        st.divider()
        st.subheader("🏆 Top 10 Highest Transactions")
        st.dataframe(fdf.sort_values('Sum Of Total Incl Vat', ascending=False).head(10)[['Trans_date', 'Customer Surname', 'Sum Of Total Incl Vat', 'Meter Number']], use_container_width=True)
        st.divider()
        st.subheader("🔎 Fast Ledger Text Search")
        q = st.text_input("Filter dashboard results by keyword...")
        res = fdf if not q else fdf[fdf.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]
        st.dataframe(res, use_container_width=True)

elif st.session_state['current_page'] == "Analytics":
    st.title("📈 Strategic Portfolio Analytics")
    if fdf.empty: st.warning("Select items from the sidebar filters to build charts.")
    else:
        c1, c2 = st.columns(2)
        with c1: st.plotly_chart(px.pie(fdf, values='Sum Of Total Incl Vat', names='Service Resource', title="Revenue Mix by Utility Type"), use_container_width=True)
        with c2: st.plotly_chart(px.bar(fdf.groupby('Client')['Sum Of Total Incl Vat'].sum().reset_index(), x='Client', y='Sum Of Total Incl Vat', title="Revenue Contribution per Client Account"), use_container_width=True)
        st.divider()
        c3, c4 = st.columns(2)
        with c3: st.plotly_chart(px.line(fdf.groupby('Year_Month_Key')['Units'].sum().reset_index(), x='Year_Month_Key', y='Units', markers=True, title="Consumption Volatility Trend (Units)"), use_container_width=True)
        with c4: st.plotly_chart(px.bar(fdf.groupby('Building Detail')['Sum Of Total Incl Vat'].sum().reset_index().sort_values('Sum Of Total Incl Vat', ascending=False).head(15), y='Building Detail', x='Sum Of Total Incl Vat', orientation='h', title="Top 15 Buildings by Billings Gross"), use_container_width=True)

elif st.session_state['current_page'] == "Reporting":
    st.title("🗂️ Executive Reporting Suite")
    if fdf.empty: st.info("Please adjust filters in the left sidebar configuration panel.")
    else:
        st.markdown("### 📊 Financial Revenue & Sales Report Factory")
        rpt_grouped = fdf.groupby(['Display_Month', 'Year_Month_Key', 'Building Detail', 'Service Resource']).agg({'Sum Of Total Incl Vat': 'sum', 'Payment To Principle': 'sum', 'Total Service Fee Incl Vat': 'sum', 'Vat': 'sum', 'Units': 'sum', 'Unique Id': 'count'}).reset_index().sort_values(['Year_Month_Key', 'Building Detail'])
        rpt_display = rpt_grouped.rename(columns={'Display_Month': 'Period', 'Building Detail': 'Building Location', 'Service Resource': 'Utility Type', 'Sum Of Total Incl Vat': 'Gross Sales', 'Payment To Principle': 'Net To Principle', 'Total Service Fee Incl Vat': 'Service Fees', 'Vat': 'VAT', 'Units': 'Units Consumed', 'Unique Id': 'Transactions'})
        totals = {'gross': rpt_display['Gross Sales'].sum(), 'net': rpt_display['Net To Principle'].sum(), 'fees': rpt_display['Service Fees'].sum(), 'vat': rpt_display['VAT'].sum(), 'units': rpt_display['Units Consumed'].sum(), 'tx_count': rpt_display['Transactions'].sum()}
        
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Gross Revenue", f"R {totals['gross']:,.2f}")
        m2.metric("Principle Payout Share", f"R {totals['net']:,.2f}")
        m3.metric("Service Fees Retained", f"R {totals['fees']:,.2f}")
        m4.metric("Aggregated Activity Load", f"{totals['units']:,.2f} Units", f"{totals['tx_count']} Tx")
        
        # FIXED: Added errors='ignore' protective handler to drop instructions
        st.dataframe(rpt_display.drop(columns=['Year_Month_Key'], errors='ignore').style.format({'Gross Sales': 'R {:,.2f}', 'Net To Principle': 'R {:,.2f}', 'Service Fees': 'R {:,.2f}', 'VAT': 'R {:,.2f}', 'Units Consumed': '{:,.2f}'}), use_container_width=True)
        
        exp_col1, exp_col2 = st.columns(2)
        window_label = f"Selected Range ({len(selected_months)} Months)" if len(selected_months) < len(chron_timeline) else "Full Historical Portfolio Range"
        with exp_col1:
            xl_buffer = io.BytesIO()
            # FIXED: Added errors='ignore' protective handler to drop instructions
            with pd.ExcelWriter(xl_buffer, engine='openpyxl') as xl_writer: rpt_display.drop(columns=['Year_Month_Key'], errors='ignore').to_excel(xl_writer, index=False, sheet_name="Sales Summary Report")
            st.download_button(label="📥 Export Report as Excel Ledger", data=xl_buffer.getvalue(), file_name=f"Sales_Summary_Report_{datetime.now().strftime('%Y%m%d')}.xlsx", use_container_width=True)
        with exp_col2:
            if FPDF:
                pdf_bytes = gen_executive_sales_report_pdf(summary_df=rpt_display, total_metrics=totals, period_label=window_label, portfolio_label=str(st.session_state['sel_owner']), logo_path="logo.png")
                if pdf_bytes: st.download_button(label="📥 Export Executive PDF Statement", data=pdf_bytes, file_name=f"Executive_Sales_Report_{datetime.now().strftime('%Y%m%d')}.pdf", use_container_width=True)

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
    st.title("🛠️ Meter Reference & Command Center")
    if working_df.empty: st.warning("No tracking data available.")
    else:
        col1, col2, col3, col4 = st.columns(4)
        with col1: query_meter = st.text_input("Search Meter", placeholder="Filter by digits...").strip()
        with col2: query_building = st.selectbox("Filter Location", ["All Buildings"] + sorted(working_df['Building Detail'].unique().tolist()))
        with col3: query_client = st.text_input("Search Client", placeholder="Filter text...").strip()
        with col4: query_surname = st.text_input("Search Tenant Surname", placeholder="Filter text...").strip()
            
        filtered_meters_df = working_df.copy()
        if query_meter: filtered_meters_df = filtered_meters_df[filtered_meters_df['Meter_Search'].str.contains(query_meter, case=False, na=False)]
        if query_building != "All Buildings": filtered_meters_df = filtered_meters_df[filtered_meters_df['Building Detail'] == query_building]
        if query_client: filtered_meters_df = filtered_meters_df[filtered_meters_df['Client'].str.contains(query_client, case=False, na=False)]
        if query_surname: filtered_meters_df = filtered_meters_df[filtered_meters_df['Customer Surname'].str.contains(query_surname, case=False, na=False)]
            
        if filtered_meters_df.empty: st.warning("No meters match criteria.")
        else:
            dir_df = filtered_meters_df.groupby('Meter Number').agg({'Building Detail': 'first', 'Client': 'first', 'Customer Surname': 'first', 'Sum Of Total Incl Vat': 'sum', 'Units': 'sum', 'Trans_date': 'count'}).rename(columns={'Sum Of Total Incl Vat': 'Billings', 'Units': 'Consumption', 'Trans_date': 'Count'}).reset_index()
            st.dataframe(dir_df.style.format({'Billings': 'R {:,.2f}', 'Consumption': '{:,.2f}'}), use_container_width=True)
            
            st.divider()
            selected_meter = st.selectbox("Drill Down Target Meter Logs:", sorted(dir_df['Meter Number'].unique().tolist()))
            if selected_meter:
                ledger_df = working_df[working_df['Meter Number'] == selected_meter].sort_values('Trans_date', ascending=False)
                st.markdown(f"#### ⚡ Command Console: `{selected_meter}`")
                op1, op2 = st.columns(2)
                with op1:
                    b1, b2 = st.columns(2)
                    if b1.button("🔴 Block Connection", use_container_width=True): st.toast(f"Meter {selected_meter} BLOCKED.", icon="🔒")
                    if b2.button("🟢 Unblock Connection", use_container_width=True): st.toast(f"Meter {selected_meter} UNBLOCKED.", icon="🔓")
                with op2:
                    token_type = st.selectbox("STS Instruction Profile", ["Clear Tamper Status", "Key Change Token", "High Power Limit Test"])
                    if st.button("⚙️ Compile Engineering Instruction", use_container_width=True):
                        st.info(f"**Generated STS {token_type} Token:**")
                        st.code(generate_sts_token(), language="text")
                st.divider()
                st.dataframe(ledger_df, use_container_width=True)

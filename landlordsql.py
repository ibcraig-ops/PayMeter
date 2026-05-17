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

    with engine.begin() as init_conn:
        init_conn.execute(text("""
            CREATE TABLE IF NOT EXISTS notifications (
                id SERIAL PRIMARY KEY,
                notice_text TEXT NOT NULL,
                target_landlord VARCHAR(255) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))

except Exception as e:
    st.error("🚨 System Connection Traceback Error Logged:")
    st.exception(e)
    st.stop()

# --- 3. APP CONFIG & BRANDING ---
st.set_page_config(page_title="Landlord Executive Portal", page_icon="logo.png", layout="wide")

try:
    from fpdf import FPDF
except ImportError:
    FPDF = None

# --- 4. UTILITY HELPERS ---
def generate_sts_token():
    """Generates a standard 20-digit split STS utility token format."""
    blocks = [f"{random.randint(1000, 9999)}" for _ in range(5)]
    return "-".join(blocks)

def clean_txt(val):
    """Safeguards FPDF canvas by scrubbing unencodable unicode special characters."""
    return str(val).encode('latin-1', 'replace').decode('latin-1')

def norm_id(val):
    """Safely normalizes alphanumeric or float distorted tracking IDs uniformly."""
    s = str(val).strip()
    if s.endswith('.0'):
        return s[:-2]
    return s

def gen_p(df, title):
    """Generates standard byte outputs for dashboard pdf fragments."""
    pdf = FPDF(orientation='L'); pdf.add_page(); pdf.set_font("Helvetica", 'B', 14)
    pdf.cell(270, 10, clean_txt(title), align='C'); pdf.ln(10); pdf.set_font("Helvetica", size=8)
    pdf_df = df.reset_index()
    for h in pdf_df.columns: pdf.cell(32, 10, clean_txt(str(h)[:14]), 1)
    pdf.ln()
    for _, r in pdf_df.iterrows():
        for v in r:
            txt = f"{v:,.2f}" if isinstance(v, (float, int)) else str(v)[:14]
            pdf.cell(32, 10, clean_txt(txt), 1)
        pdf.ln()
    return bytes(pdf.output())

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
    pdf.cell(205, 8, "EXECUTIVE SALES & UTILITY REVENUE REPORT", align='R')
    pdf.set_font("Helvetica", 'I', 10)
    pdf.set_xy(80, 18)
    pdf.cell(205, 5, clean_txt(f"Portfolio Scope: {portfolio_label}   |   Reporting Window: {period_label}"), align='R')
    
    pdf.set_text_color(51, 65, 85) 
    pdf.set_font("Helvetica", size=9)
    pdf.set_xy(12, 38)
    pdf.cell(100, 5, f"Document ID: ISR-{random.randint(100000, 999999)}")
    pdf.ln(5)
    pdf.set_x(12)
    pdf.cell(100, 5, f"Generated On: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    pdf.ln(9)
    
    pdf.set_fill_color(241, 245, 249) 
    pdf.set_draw_color(226, 232, 240)
    
    # KPI Blocks
    pdf.rect(12, 50, 62, 18, 'DF')
    pdf.set_xy(14, 52)
    pdf.set_font("Helvetica", '', 8)
    pdf.cell(58, 4, "TOTAL GROSS SALES")
    pdf.set_xy(14, 57)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.set_text_color(13, 148, 136) 
    pdf.cell(58, 8, f"R {total_metrics['gross']:,.2f}")
    
    pdf.set_text_color(51, 65, 85)
    pdf.rect(80, 50, 62, 18, 'DF')
    pdf.set_xy(82, 52)
    pdf.set_font("Helvetica", '', 8)
    pdf.cell(58, 4, "PRINCIPLE REVENUE SHARE")
    pdf.set_xy(82, 57)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(58, 8, f"R {total_metrics['net']:,.2f}")
    
    pdf.rect(148, 50, 62, 18, 'DF')
    pdf.set_xy(150, 52)
    pdf.set_font("Helvetica", '', 8)
    pdf.cell(58, 4, "TOTAL SERVICE FEES")
    pdf.set_xy(150, 57)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(58, 8, f"R {total_metrics['fees']:,.2f}")
    
    pdf.rect(216, 50, 69, 18, 'DF')
    pdf.set_xy(218, 52)
    pdf.set_font("Helvetica", '', 8)
    pdf.cell(65, 4, "CUMULATIVE UNITS CONSUMED")
    pdf.set_xy(218, 57)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(65, 8, f"{total_metrics['units']:,.2f} Units")
    
    pdf.set_xy(12, 74)
    pdf.set_font("Helvetica", 'B', 10)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(200, 6, "DETAILED REVENUE BREAKDOWN BY ASSET LOCATION")
    pdf.ln(8)
    
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.set_draw_color(30, 58, 138)
    pdf.set_font("Helvetica", 'B', 8)
    
    has_period = 'Period' in summary_df.columns
    has_meter = 'Meter Number' in summary_df.columns
    
    col_w = []
    headers = []
    
    if has_period:
        col_w.append(18); headers.append("PERIOD")
    col_w.append(55); headers.append("BUILDING DETAIL")
    if has_meter:
        col_w.append(30); headers.append("METER NUMBER")
        
    col_w.extend([18, 28, 28, 28, 22, 25, 18])
    headers.extend(["UTILITY", "GROSS SALES", "PRINCIPLE PAY", "SERVICE FEES", "VAT ACCR", "UNITS", "TX COUNT"])
    
    total_w = sum(col_w)
    if total_w < 273:
        col_w[-1] += (273 - total_w)
    
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
            
        c_idx = 0
        if has_period:
            pdf.cell(col_w[c_idx], 7, clean_txt(r['Period']), 1, 0, 'C', True); c_idx += 1
            
        pdf.cell(col_w[c_idx], 7, clean_txt(r['Building Location'])[:26], 1, 0, 'L', True); c_idx += 1
        
        if has_meter:
            pdf.cell(col_w[c_idx], 7, clean_txt(r['Meter Number']), 1, 0, 'C', True); c_idx += 1
            
        pdf.cell(col_w[c_idx], 7, clean_txt(r['Utility Type']), 1, 0, 'C', True); c_idx += 1
        pdf.cell(col_w[c_idx], 7, f"R {r['Gross Sales']:,.2f}", 1, 0, 'R', True); c_idx += 1
        pdf.cell(col_w[c_idx], 7, f"R {r['Net To Principle']:,.2f}", 1, 0, 'R', True); c_idx += 1
        pdf.cell(col_w[c_idx], 7, f"R {r['Service Fees']:,.2f}", 1, 0, 'R', True); c_idx += 1
        pdf.cell(col_w[c_idx], 7, f"R {r['VAT']:,.2f}", 1, 0, 'R', True); c_idx += 1
        pdf.cell(col_w[c_idx], 7, f"{r['Units Consumed']:,.2f}", 1, 0, 'R', True); c_idx += 1
        pdf.cell(col_w[c_idx], 7, f"{int(r['Transactions'])}", 1, 0, 'C', True)
        pdf.ln()
        toggle_fill = not toggle_fill
        
    pdf.set_x(12)
    pdf.set_font("Helvetica", 'B', 8)
    pdf.set_fill_color(226, 232, 240)
    
    descriptive_w = 55
    if has_period: descriptive_w += 18
    if has_meter: descriptive_w += 30
    
    pdf.cell(descriptive_w, 8, "PORTFOLIO AGGREGATE TOTALS", 1, 0, 'L', True)
    
    start_num_idx = 1
    if has_period: start_num_idx += 1
    if has_meter: start_num_idx += 1
    
    c_idx = start_num_idx
    pdf.cell(col_w[c_idx], 8, f"R {total_metrics['gross']:,.2f}", 1, 0, 'R', True); c_idx += 1
    pdf.cell(col_w[c_idx], 8, f"R {total_metrics['net']:,.2f}", 1, 0, 'R', True); c_idx += 1
    pdf.cell(col_w[c_idx], 8, f"R {total_metrics['fees']:,.2f}", 1, 0, 'R', True); c_idx += 1
    pdf.cell(col_w[c_idx], 8, f"R {total_metrics['vat']:,.2f}", 1, 0, 'R', True); c_idx += 1
    pdf.cell(col_w[c_idx], 8, f"{total_metrics['units']:,.2f}", 1, 0, 'R', True); c_idx += 1
    pdf.cell(col_w[c_idx], 8, f"{int(total_metrics['tx_count'])}", 1, 0, 'C', True)
    
    return bytes(pdf.output())

def gen_building_summary_pdf(summary_df, total_metrics, period_label, portfolio_label, logo_path="logo.png"):
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
    pdf.cell(205, 8, "EXECUTIVE BUILDING SUMMARY STATEMENT", align='R')
    pdf.set_font("Helvetica", 'I', 10)
    pdf.set_xy(80, 18)
    pdf.cell(205, 5, clean_txt(f"Portfolio Scope: {portfolio_label}   |   Reporting Window: {period_label}"), align='R')
    
    pdf.set_text_color(51, 65, 85) 
    pdf.set_font("Helvetica", size=9)
    pdf.set_xy(12, 38)
    pdf.cell(100, 5, f"Document ID: BSR-{random.randint(100000, 999999)}")
    pdf.ln(5)
    pdf.set_x(12)
    pdf.cell(100, 5, f"Generated On: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    pdf.ln(9)
    
    pdf.set_fill_color(241, 245, 249) 
    pdf.set_draw_color(226, 232, 240)
    
    pdf.rect(12, 50, 62, 18, 'DF')
    pdf.set_xy(14, 52)
    pdf.set_font("Helvetica", '', 8)
    pdf.cell(58, 4, "AGGREGATE GROSS SALES")
    pdf.set_xy(14, 57)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.set_text_color(13, 148, 136) 
    pdf.cell(58, 8, f"R {total_metrics['gross']:,.2f}")
    
    pdf.set_text_color(51, 65, 85)
    pdf.rect(80, 50, 62, 18, 'DF')
    pdf.set_xy(82, 52)
    pdf.set_font("Helvetica", '', 8)
    pdf.cell(58, 4, "AGGREGATE PRINCIPLE PAY")
    pdf.set_xy(82, 57)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(58, 8, f"R {total_metrics['net']:,.2f}")
    
    pdf.rect(148, 50, 62, 18, 'DF')
    pdf.set_xy(150, 52)
    pdf.set_font("Helvetica", '', 8)
    pdf.cell(58, 4, "AGGREGATE SERVICE FEES")
    pdf.set_xy(150, 57)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(58, 8, f"R {total_metrics['fees']:,.2f}")
    
    pdf.rect(216, 50, 69, 18, 'DF')
    pdf.set_xy(218, 52)
    pdf.set_font("Helvetica", '', 8)
    pdf.cell(65, 4, "AGGREGATE UNITS CONSUMED")
    pdf.set_xy(218, 57)
    pdf.set_font("Helvetica", 'B', 12)
    pdf.cell(65, 8, f"{total_metrics['units']:,.2f} Units")
    
    pdf.set_xy(12, 74)
    pdf.set_font("Helvetica", 'B', 10)
    pdf.set_text_color(30, 58, 138)
    pdf.cell(200, 6, "PORTFOLIO BUILDING-WISE FINANCIAL SUMMARY")
    pdf.ln(8)
    
    pdf.set_fill_color(30, 58, 138)
    pdf.set_text_color(255, 255, 255)
    pdf.set_draw_color(30, 58, 138)
    pdf.set_font("Helvetica", 'B', 8)
    
    col_w = [85, 25, 30, 30, 30, 25, 28, 20]
    headers = ["BUILDING PROPERTY LOCATION", "RESOURCE", "GROSS SALES", "PRINCIPLE PAY", "SERVICE FEES", "VAT ACCR", "UNITS", "TX COUNT"]
    
    pdf.set_x(12)
    for w, h in zip(col_w, headers): pdf.cell(w, 8, h, 1, 0, 'C', True)
    pdf.ln()
    
    pdf.set_text_color(51, 65, 85)
    pdf.set_draw_color(226, 232, 240)
    
    for _, r in summary_df.iterrows():
        b_name = str(r['Building Location'])
        is_sub = "SUBTOTAL" in b_name or "GRAND TOTAL" in b_name
        
        pdf.set_x(12)
        if is_sub:
            pdf.set_font("Helvetica", 'B', 8)
            pdf.set_fill_color(226, 232, 240)
        else:
            pdf.set_font("Helvetica", '', 8)
            pdf.set_fill_color(255, 255, 255)
            
        pdf.cell(col_w[0], 7, clean_txt(b_name)[:48], 1, 0, 'L', True)
        pdf.cell(col_w[1], 7, clean_txt(r['Utility Type']), 1, 0, 'C', True)
        pdf.cell(col_w[2], 7, f"R {r['Gross Sales']:,.2f}" if isinstance(r['Gross Sales'], (int, float)) else str(r['Gross Sales']), 1, 0, 'R', True)
        pdf.cell(col_w[3], 7, f"R {r['Net To Principle']:,.2f}" if isinstance(r['Net To Principle'], (int, float)) else str(r['Net To Principle']), 1, 0, 'R', True)
        pdf.cell(col_w[4], 7, f"R {r['Service Fees']:,.2f}" if isinstance(r['Service Fees'], (int, float)) else str(r['Service Fees']), 1, 0, 'R', True)
        pdf.cell(col_w[5], 7, f"R {r['VAT']:,.2f}" if isinstance(r['VAT'], (int, float)) else str(r['VAT']), 1, 0, 'R', True)
        pdf.cell(col_w[6], 7, f"{r['Units Consumed']:,.2f}" if isinstance(r['Units Consumed'], (int, float)) else str(r['Units Consumed']), 1, 0, 'R', True)
        pdf.cell(col_w[7], 7, f"{int(r['Transactions'])}" if isinstance(r['Transactions'], (int, float)) else str(r['Transactions']), 1, 0, 'C', True)
        pdf.ln()
        
    return bytes(pdf.output())

# --- 6. DATABASE FUNCTIONS ---
@st.cache_data(ttl=300)
def load_users():
    try:
        df = pd.read_sql("SELECT * FROM users", engine)
        return df
    except Exception as e:
        err_str = str(e).lower()
        if "does not exist" in err_str:
            admin_pass = hashlib.sha256("Sillycat01".encode()).hexdigest()
            df_init = pd.DataFrame([{"username": "admin", "password": admin_pass, "role": "admin", "owner_name": "All"}])
            try:
                with engine.begin() as conn:
                    df_init.to_sql("users", conn, if_exists="replace", index=False)
                return df_init
            except Exception as sql_e:
                st.error("🚨 System Table Initialization Failed")
                st.code(str(sql_e))
                st.stop()
        else:
            st.error("❌ App Connection Failed")
            st.stop()

def save_user(u, p, r, o):
    try:
        hp = hashlib.sha256(p.encode()).hexdigest()
        query = text("INSERT INTO users (username, password, role, owner_name) VALUES (:u, :p, :r, :o)")
        with engine.begin() as conn:
            conn.execute(query, {"u": u, "p": hp, "r": r, "o": o})
        st.cache_data.clear()
        return True
    except Exception as database_error:
        st.error("🚨 Database Engine Rejected User Creation Entry")
        st.exception(database_error)
        return False

def update_user_password(u, p):
    try:
        hp = hashlib.sha256(p.encode()).hexdigest()
        query = text("UPDATE users SET password = :p WHERE username = :u")
        with engine.begin() as conn:
            conn.execute(query, {"p": hp, "u": u})
        st.cache_data.clear()
        return True
    except Exception as database_error:
        st.error("🚨 Database Engine Rejected Password Revision Request")
        st.exception(database_error)
        return False

def delete_user(u):
    try:
        query = text("DELETE FROM users WHERE username = :u")
        with engine.begin() as conn:
            conn.execute(query, {"u": u})
        st.cache_data.clear()
        return True
    except Exception as database_error:
        st.error("🚨 Database Engine Rejected Access Revocation Purge")
        st.exception(database_error)
        return False

def save_notification(notice_text, target):
    try:
        query = text("INSERT INTO notifications (notice_text, target_landlord) VALUES (:txt, :tgt)")
        with engine.begin() as conn:
            conn.execute(query, {"txt": notice_text, "tgt": target})
        return True
    except Exception as database_error:
        st.error("🚨 Database Engine Rejected Broadcast Insertion Request")
        st.exception(database_error)
        return False

def load_active_notifications(target_landlord):
    try:
        query = text("SELECT notice_text FROM notifications WHERE target_landlord = 'All' OR target_landlord = :tgt ORDER BY created_at DESC")
        with engine.connect() as conn:
            res = conn.execute(query, {"tgt": target_landlord}).fetchall()
        return [row[0] for row in res]
    except:
        return []

def purge_all_notifications():
    try:
        query = text("TRUNCATE TABLE notifications")
        with engine.begin() as conn:
            conn.execute(query)
        return True
    except Exception as database_error:
        st.error("🚨 Database Engine Rejected Notice Clear Sequence")
        st.exception(database_error)
        return False

def clear_transaction_history():
    try:
        query = text("TRUNCATE TABLE transactions")
        with engine.begin() as conn:
            conn.execute(query)
        st.cache_data.clear()
        return True
    except Exception:
        st.cache_data.clear()
        return True

# FIXED ENGINE CORRECTION LAYER: Automatically scrub trailing decimals from meter numbers on retrieval
@st.cache_data(ttl=60)
def load_master_data():
    try:
        df = pd.read_sql("SELECT * FROM transactions", engine)
        if df.empty: return df
        
        # Scrub trailing float decimals from meter column fields globally prior to workspace assembly
        if 'Meter Number' in df.columns:
            df['Meter Number'] = df['Meter Number'].astype(str).str.strip().str.replace(r'\.0$', '', regex=True)
            
        df['Units'] = pd.to_numeric(df['Units'], errors='coerce').fillna(0)
        df['Sum Of Total Incl Vat'] = pd.to_numeric(df['Sum Of Total Incl Vat'], errors='coerce').fillna(0)
        df['Payment To Principle'] = pd.to_numeric(df['Payment To Principle'], errors='coerce').fillna(0)
        df['Total Service Fee Incl Vat'] = pd.to_numeric(df['Total Service Fee Incl Vat'], errors='coerce').fillna(0)
        df['Vat'] = pd.to_numeric(df['Vat'], errors='coerce').fillna(0)
        
        df['Trans_date'] = pd.to_datetime(df['Trans_date'], errors='coerce')
        
        df['Owner Detail'] = df['Owner Detail'].fillna("Missing Owner").astype(str).str.strip()
        df['Building Detail'] = df['Building Detail'].fillna("Missing Building").astype(str).str.strip()
        
        df['Year_Month_Key'] = df['Trans_date'].dt.strftime('%Y-%m').fillna("Unknown Period")
        df['Month'] = df['Trans_date'].dt.strftime('%B').fillna("Unknown Month")
        df['Display_Month'] = df['Month'] + " " + df['Trans_date'].dt.year.astype(str).fillna("")
        df['Meter_Search'] = df['Meter Number']
        return df
    except: return pd.DataFrame()

def update_database(f, m):
    try:
        df = pd.read_csv(f)
        
        col_map = {
            "unique id": "Unique Id", "unique_id": "Unique Id",
            "trans_date": "Trans_date", "trans date": "Trans_date", "transaction date": "Trans_date",
            "owner detail": "Owner Detail", "owner": "Owner Detail",
            "building detail": "Building Detail", "building location": "Building Detail", "building": "Building Detail",
            "meter number": "Meter Number", "meter no": "Meter Number",
            "service resource": "Service Resource", "utility type": "Service Resource", "utility": "Service Resource",
            "sum of total incl vat": "Sum Of Total Incl Vat", "gross sales": "Sum Of Total Incl Vat", "gross": "Sum Of Total Incl Vat",
            "payment to principle": "Payment To Principle", "net to principle": "Payment To Principle",
            "total service fee incl vat": "Total Service Fee Incl Vat", "service fees": "Total Service Fee Incl Vat",
            "vat": "Vat", "units": "Units", "client": "Client", "customer surname": "Customer Surname"
        }
        
        df.columns = df.columns.str.strip().str.lower()
        df = df.rename(columns=col_map)
        
        if 'Unique Id' in df.columns:
            df = df.dropna(subset=['Unique Id'])
            df['Unique Id'] = df['Unique Id'].apply(norm_id)
            
        if df.empty:
            st.sidebar.warning("⚠️ Uploaded file template contains zero rows.")
            return

        with engine.begin() as conn:
            if m == "replace":
                df.to_sql("transactions", conn, if_exists="replace", index=False)
                st.sidebar.success(f"🚀 Overwrote data suite with {len(df)} rows.")
            else:
                df.to_sql("transactions", conn, if_exists="append", index=False)
                st.sidebar.success(f"🚀 Appended {len(df)} lines successfully!")
                
        st.cache_data.clear()
    except Exception as data_sync_exception:
        st.error("🚨 Critical Failure Encountered During Spreadsheet Synchronization")
        st.exception(data_sync_exception)

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
    st.success("✔️ Connected to Database")
    if os.path.exists("logo.png"): st.image("logo.png", use_container_width=True)
    st.title(f"👤 {st.session_state['user_name']}")
    
    if st.session_state['user_role'] == 'admin':
        with st.expander("📂 Data Sync"):
            up = st.file_uploader("Upload CSV", type="csv")
            md = "replace" if st.radio("Mode", ["Overwrite", "Append"]) == "Overwrite" else "append"
            if up and st.button("Sync Now"): update_database(up, md); st.rerun()
            
            st.divider()
            st.markdown("<span style='color:#ef4444; font-weight:700; font-size:12px;'>⚠️ DANGER ZONE</span>", unsafe_allow_html=True)
            if st.button("🗑️ Wipe All Transaction Logs", use_container_width=True):
                if clear_transaction_history():
                    st.toast("Database tables successfully wiped clean!", icon="🧼")
                    st.rerun()
            
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
    if not working_df.empty:
        with st.sidebar:
            st.markdown("### 🔍 Live Dataset Filters")
            sb = st.multiselect("Filter Asset Buildings", sorted(working_df['Building Detail'].unique()), default=sorted(working_df['Building Detail'].unique()))
            chron_timeline = working_df.sort_values('Year_Month_Key')['Display_Month'].unique().tolist()
            selected_months = st.multiselect("Filter Months/Years", chron_timeline, default=chron_timeline)
            st.divider()
            if st.button("Logout", use_container_width=True): st.session_state['logged_in'] = False; st.rerun()
else:
    with st.sidebar:
        if st.button("Logout", use_container_width=True): st.session_state['logged_in'] = False; st.rerun()

# --- 10. NOTIFICATION LAYER ---
if st.session_state['logged_in']:
    target_scope = st.session_state['assigned_owner'] if st.session_state['user_role'] == 'landlord' else 'All'
    active_alerts = load_active_notifications(target_scope)
    for alert_msg in active_alerts:
        st.markdown(f"""
        <div style="background-color: #fffbeb; border-left: 5px solid #f59e0b; padding: 12px 18px; margin-top: 5px; margin-bottom: 18px; border-radius: 4px; box-shadow: 0 2px 5px rgba(0,0,0,0.04); font-family: Arial, sans-serif;">
            <span style="font-size: 15px; margin-right: 8px;">📢</span>
            <strong style="color: #b45309; font-size: 13px; text-transform: uppercase; letter-spacing: 0.3px;">Executive Notice:</strong>
            <span style="color: #78350f; font-size: 13.5px; margin-left: 6px; font-weight: 500;">{alert_msg}</span>
        </div>
        """, unsafe_allow_html=True)

# --- 11. VIEWPORT ROUTER CONTROL LAYOUTS ---

if st.session_state['current_page'] == "Dashboard":
    if working_df.empty: st.warning("No transactional database content found.")
    else:
        fdf = working_df[(working_df['Building Detail'].isin(sb)) & (working_df['Display_Month'].isin(selected_months))]
        if fdf.empty: st.warning("No data matches selected timeline parameters.")
        else:
            st.title(f"🏢 {st.session_state['sel_owner']} Overview")
            
            elec_sub = fdf[fdf['Service Resource'].str.lower() == 'electricity'] if 'Service Resource' in fdf.columns else pd.DataFrame()
            water_sub = fdf[fdf['Service Resource'].str.lower() == 'water'] if 'Service Resource' in fdf.columns else pd.DataFrame()
            
            e_sales, e_units = elec_sub['Sum Of Total Incl Vat'].sum(), elec_sub['Units'].sum()
            w_sales, w_units = water_sub['Sum Of Total Incl Vat'].sum(), water_sub['Units'].sum()
            t_sales, t_units = e_sales + w_sales, e_units + w_units
            
            st.write("#### 📊 Period Performance Summary Matrix")
            html_matrix = f"""
            <table style="width:100%; border-collapse: collapse; font-family: 'Helvetica Neue', Helvetica, Arial, sans-serif; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 12px rgba(0,0,0,0.08); margin-bottom: 25px;">
                <thead>
                    <tr style="background-color: #1e3a8a; color: white; text-align: left;">
                        <th style="padding: 14px 18px; font-size: 14px; font-weight: 600; letter-spacing: 0.5px;">Metric Summary Matrix</th>
                        <th style="padding: 14px 18px; font-size: 14px; font-weight: 600; text-align: center; letter-spacing: 0.5px; border-left: 1px solid rgba(255,255,255,0.15);">⚡ Electricity</th>
                        <th style="padding: 14px 18px; font-size: 14px; font-weight: 600; text-align: center; letter-spacing: 0.5px; border-left: 1px solid rgba(255,255,255,0.15);">💧 Water</th>
                        <th style="padding: 14px 18px; font-size: 14px; font-weight: 600; text-align: center; letter-spacing: 0.5px; border-left: 1px solid rgba(255,255,255,0.15);">🏢 Total Scope</th>
                    </tr>
                </thead>
                <tbody>
                    <tr style="background-color: #ffffff; border-bottom: 1px solid #e2e8f0;">
                        <td style="padding: 16px 18px; font-weight: 700; color: #334155; background-color: #f8fafc; font-size: 13px; width: 20%;">💰 Sales</td>
                        <td style="padding: 16px 18px; text-align: center; font-size: 16px; font-weight: 700; color: #0d9488; background-color: #f0fdfa; width: 26%;">R {e_sales:,.2f}</td>
                        <td style="padding: 16px 18px; text-align: center; font-size: 16px; font-weight: 700; color: #0d9488; background-color: #f0fdfa; width: 26%;">R {w_sales:,.2f}</td>
                        <td style="padding: 16px 18px; text-align: center; font-size: 16px; font-weight: 700; color: #0f172a; background-color: #f1f5f9; width: 28%;">R {t_sales:,.2f}</td>
                    </tr>
                    <tr style="background-color: #ffffff;">
                        <td style="padding: 16px 18px; font-weight: 700; color: #334155; background-color: #f8fafc; font-size: 13px;">📊 Consumption</td>
                        <td style="padding: 16px 18px; text-align: center; font-size: 16px; font-weight: 700; color: #2563eb; background-color: #eff6ff;">{e_units:,.2f} Units</td>
                        <td style="padding: 16px 18px; text-align: center; font-size: 16px; font-weight: 700; color: #2563eb; background-color: #eff6ff;">{w_units:,.2f} Units</td>
                        <td style="padding: 16px 18px; text-align: center; font-size: 16px; font-weight: 700; color: #475569; background-color: #f1f5f9;">{t_units:,.2f} Units</td>
                    </tr>
                </tbody>
            </table>
            """
            st.markdown(html_matrix, unsafe_allow_html=True)
            st.divider()
            
            st.subheader("📈 Performance Trend")
            if 'Service Resource' in fdf.columns:
                trend_data = fdf.groupby(['Year_Month_Key', 'Service Resource'])['Sum Of Total Incl Vat'].sum().reset_index()
                fig = px.bar(trend_data, x='Year_Month_Key', y='Sum Of Total Incl Vat', color='Service Resource', barmode='group', title="Gross Revenue Split: Electricity vs Water", labels={'Sum Of Total Incl Vat': 'Sales Revenue (R)', 'Year_Month_Key': 'Timeline Period', 'Service Resource': 'Utility Resource'}, color_discrete_map={'Electricity': '#0d9488', 'Water': '#2563eb'})
            else:
                trend_data = fdf.groupby('Year_Month_Key')['Sum Of Total Incl Vat'].sum().reset_index()
                fig = px.bar(trend_data, x='Year_Month_Key', y='Sum Of Total Incl Vat', title="Gross Revenue Breakdown per Month")
            st.plotly_chart(fig, use_container_width=True)
            st.divider()
            
            st.subheader("📋 Monthly Breakdown")
            if st.session_state['sel_owner'] == "All Owners":
                summary = fdf.groupby(['Year_Month_Key']).agg({'Sum Of Total Incl Vat': 'sum', 'Units': 'sum', 'Meter Number': 'nunique', 'Unique Id': 'count'}).rename(columns={'Sum Of Total Incl Vat': 'Sales', 'Units': 'Consumption', 'Meter Number': 'Meters', 'Unique Id': 'Transactions'})
                summary_flat = summary.reset_index()
                total_row = pd.DataFrame([{'Year_Month_Key': 'Grand Total', 'Sales': summary_flat['Sales'].sum(), 'Consumption': summary_flat['Consumption'].sum(), 'Meters': int(fdf['Meter Number'].nunique()), 'Transactions': int(summary_flat['Transactions'].sum())}])
            else:
                summary = fdf.groupby(['Year_Month_Key', 'Building Detail']).agg({'Sum Of Total Incl Vat': 'sum', 'Units': 'sum', 'Meter Number': 'nunique', 'Unique Id': 'count'}).rename(columns={'Sum Of Total Incl Vat': 'Sales', 'Units': 'Consumption', 'Meter Number': 'Meters', 'Unique Id': 'Transactions'})
                summary_flat = summary.reset_index()
                total_row = pd.DataFrame([{'Year_Month_Key': 'Grand Total', 'Building Detail': '', 'Sales': summary_flat['Sales'].sum(), 'Consumption': summary_flat['Consumption'].sum(), 'Meters': int(fdf['Meter Number'].nunique()), 'Transactions': int(summary_flat['Transactions'].sum())}])
            
            summary_with_total = pd.concat([summary_flat, total_row], ignore_index=True)
            st.dataframe(summary_with_total.style.format({'Sales': 'R {:,.2f}', 'Consumption': '{:,.2f}', 'Meters': '{:,}', 'Transactions': '{:,}'}), use_container_width=True)
            
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
    if working_df.empty: st.warning("No tracking records available to compute visuals.")
    else:
        fdf = working_df[(working_df['Building Detail'].isin(sb)) & (working_df['Display_Month'].isin(selected_months))]
        st.title("📈 Strategic Portfolio Analytics")
        if fdf.empty: st.warning("Select filters from the sidebar to build dynamic charts.")
        else:
            c1, c2 = st.columns(2)
            with c1: st.plotly_chart(px.pie(fdf, values='Sum Of Total Incl Vat', names='Service Resource', title="Revenue Mix by Utility Type"), use_container_width=True)
            with c2: st.plotly_chart(px.bar(fdf.groupby('Client')['Sum Of Total Incl Vat'].sum().reset_index(), x='Client', y='Sum Of Total Incl Vat', title="Revenue Contribution per Client Account"), use_container_width=True)
            st.divider()
            c3, c4 = st.columns(2)
            with c3: st.plotly_chart(px.line(fdf.groupby('Year_Month_Key')['Units'].sum().reset_index(), x='Year_Month_Key', y='Units', markers=True, title="Consumption Volatility Trend (Units)"), use_container_width=True)
            with c4: st.plotly_chart(px.bar(fdf.groupby('Building Detail')['Sum Of Total Incl Vat'].sum().reset_index().sort_values('Sum Of Total Incl Vat', ascending=False).head(15), y='Building Detail', x='Sum Of Total Incl Vat', orientation='h', title="Top 15 Buildings by Billings Gross"), use_container_width=True)

elif st.session_state['current_page'] == "Reporting":
    if working_df.empty: st.info("Please sync asset profiles to access report generation frameworks.")
    else:
        sb_local = sb if 'sb' in locals() else working_df['Building Detail'].unique()
        
        t1, t2, t3 = st.tabs(["📊 Financial Sales Factory", "🏢 Building Summary Report", "⚠️ Dormant Meters Audit"])
        
        with t1:
            st.markdown("### 📊 Financial Revenue & Sales Report Factory")
            st.write("#### 🔍 Filter Reporting Window & Structure")
            rc1, rc2 = st.columns(2)
            with rc1: local_months_selected = st.multiselect("Filter Active Report Months:", chron_timeline, default=selected_months if any(m in chron_timeline for m in selected_months) else chron_timeline)
            with rc2: consolidation_mode = st.selectbox("Meter Rows Grouping Structure:", ["Consolidate Total for Selected Period", "Split by Month Rows"])
                
            rpt_fdf = working_df[(working_df['Building Detail'].isin(sb_local)) & (working_df['Display_Month'].isin(local_months_selected))]
            if rpt_fdf.empty: st.warning("No data rows locate within current selections.")
            else:
                group_cols = []
                rename_dict = {}
                if consolidation_mode == "Split by Month Rows":
                    group_cols.extend(['Display_Month', 'Year_Month_Key'])
                    rename_dict['Display_Month'] = 'Period'
                group_cols.append('Building Detail'); rename_dict['Building Detail'] = 'Building Location'
                if st.session_state['sel_owner'] != "All Owners": group_cols.append('Meter Number'); rename_dict['Meter Number'] = 'Meter Number'
                group_cols.append('Service Resource'); rename_dict['Service Resource'] = 'Utility Type'
                
                rename_dict.update({'Sum Of Total Incl Vat': 'Gross Sales', 'Payment To Principle': 'Net To Principle', 'Total Service Fee Incl Vat': 'Service Fees', 'Vat': 'VAT', 'Units': 'Units Consumed', 'Unique Id': 'Transactions'})
                rpt_grouped = rpt_fdf.groupby(group_cols).agg({'Sum Of Total Incl Vat': 'sum', 'Payment To Principle': 'sum', 'Total Service Fee Incl Vat': 'sum', 'Vat': 'sum', 'Units': 'sum', 'Unique Id': 'count'}).reset_index()
                rpt_grouped = rpt_grouped.sort_values(['Year_Month_Key', 'Building Detail']) if "Year_Month_Key" in rpt_grouped.columns else rpt_grouped.sort_values(['Building Detail'])
                rpt_display = rpt_grouped.rename(columns=rename_dict)
                totals = {'gross': rpt_display['Gross Sales'].sum(), 'net': rpt_display['Net To Principle'].sum(), 'fees': rpt_display['Service Fees'].sum(), 'vat': rpt_display['VAT'].sum(), 'units': rpt_display['Units Consumed'].sum(), 'tx_count': rpt_display['Transactions'].sum()}
                
                st.divider()
                m1, m2, m3, m4 = st.columns(4)
                m1.metric("Gross Revenue", f"R {totals['gross']:,.2f}")
                m2.metric("Principle Payout Share", f"R {totals['net']:,.2f}")
                m3.metric("Service Fees Retained", f"R {totals['fees']:,.2f}")
                m4.metric("Aggregated Activity Load", f"{totals['units']:,.2f} Units", f"{totals['tx_count']} Tx")
                
                st.write("#### 📑 Sales Report Data Grid Preview")
                st.dataframe(rpt_display.drop(columns=['Year_Month_Key'], errors='ignore').style.format({'Gross Sales': 'R {:,.2f}', 'Net To Principle': 'R {:,.2f}', 'Service Fees': 'R {:,.2f}', 'VAT': 'R {:,.2f}', 'Units Consumed': '{:,.2f}'}), use_container_width=True)
                
                st.markdown("#### 📥 Document Compilation & Export Options")
                exp_col1, exp_col2 = st.columns(2)
                window_label = f"Selected Range ({len(local_months_selected)} Months)" if len(local_months_selected) < len(chron_timeline) else "Full Historical Portfolio Range"
                with exp_col1:
                    xl_buffer = io.BytesIO()
                    with pd.ExcelWriter(xl_buffer, engine='openpyxl') as xl_writer: rpt_display.drop(columns=['Year_Month_Key'], errors='ignore').to_excel(xl_writer, index=False, sheet_name="Sales Summary Report")
                    st.download_button(label="📥 Export Report as Excel Ledger", data=xl_buffer.getvalue(), file_name=f"Sales_Summary_Report_{datetime.now().strftime('%Y%m%d')}.xlsx", use_container_width=True)
                with exp_col2:
                    if FPDF:
                        pdf_bytes = gen_executive_sales_report_pdf(summary_df=rpt_display.drop(columns=['Year_Month_Key'], errors='ignore'), total_metrics=totals, period_label=window_label, portfolio_label=str(st.session_state['sel_owner']), logo_path="logo.png")
                        if pdf_bytes: st.download_button(label="📥 Export Executive PDF Statement", data=pdf_bytes, file_name=f"Executive_Sales_Report_{datetime.now().strftime('%Y%m%d')}.pdf", use_container_width=True)
                        
        with t2:
            st.markdown("### 🏢 Executive Building Summary Statement Factory")
            local_months_b = st.multiselect("Select Reporting Months (Building Summary Scope):", chron_timeline, default=selected_months if any(m in chron_timeline for m in selected_months) else chron_timeline, key="months_b")
            b_fdf = working_df[(working_df['Building Detail'].isin(sb_local)) & (working_df['Display_Month'].isin(local_months_b))]
            
            if b_fdf.empty: st.warning("No tracking details found matching specified criteria scopes.")
            else:
                b_grouped = b_fdf.groupby(['Building Detail', 'Service Resource']).agg({'Sum Of Total Incl Vat': 'sum', 'Payment To Principle': 'sum', 'Total Service Fee Incl Vat': 'sum', 'Vat': 'sum', 'Units': 'sum', 'Unique Id': 'count'}).reset_index()
                final_rows = []
                unique_buildings = sorted(b_grouped['Building Detail'].unique())
                
                for b_item in unique_buildings:
                    b_subset = b_grouped[b_grouped['Building Detail'] == b_item]
                    for _, row in b_subset.iterrows():
                        final_rows.append({'Building Location': row['Building Detail'], 'Utility Type': row['Service Resource'], 'Gross Sales': row['Sum Of Total Incl Vat'], 'Net To Principle': row['Payment To Principle'], 'Service Fees': row['Total Service Fee Incl Vat'], 'VAT': row['Vat'], 'Units Consumed': row['Units'], 'Transactions': row['Unique Id']})
                    final_rows.append({'Building Location': f"🏢 {b_item} - SUBTOTAL", 'Utility Type': "Combined", 'Gross Sales': b_subset['Sum Of Total Incl Vat'].sum(), 'Net To Principle': b_subset['Payment To Principle'].sum(), 'Service Fees': b_subset['Total Service Fee Incl Vat'].sum(), 'VAT': b_subset['Vat'].sum(), 'Units Consumed': b_subset['Units'].sum(), 'Transactions': b_subset['Unique Id'].sum()})
                    
                totals_b = {'gross': b_grouped['Sum Of Total Incl Vat'].sum(), 'net': b_grouped['Payment To Principle'].sum(), 'fees': b_grouped['Total Service Fee Incl Vat'].sum(), 'vat': b_grouped['Vat'].sum(), 'units': b_grouped['Units'].sum(), 'tx_count': b_grouped['Unique Id'].sum()}
                final_rows.append({'Building Location': "🗃️ GRAND PORTFOLIO TOTAL", 'Utility Type': "Aggregate", 'Gross Sales': totals_b['gross'], 'Net To Principle': totals_b['net'], 'Service Fees': totals_b['fees'], 'VAT': totals_b['vat'], 'Units Consumed': totals_b['units'], 'Transactions': totals_b['tx_count']})
                b_display_df = pd.DataFrame(final_rows)
                
                st.divider()
                bm1, bm2, bm3, bm4 = st.columns(4)
                bm1.metric("Portfolio Gross Sales", f"R {totals_b['gross']:,.2f}")
                bm2.metric("Portfolio Net Share", f"R {totals_b['net']:,.2f}")
                bm3.metric("Portfolio Fees Revenue", f"R {totals_b['fees']:,.2f}")
                bm4.metric("Portfolio Combined Load", f"{totals_b['units']:,.2f} Units", f"{totals_b['tx_count']} Tx")
                
                def highlight_subtotals(row):
                    val = str(row['Building Location'])
                    if "SUBTOTAL" in val: return ['background-color: #f1f5f9; font-weight: bold; color: #1e3a8a'] * len(row)
                    elif "GRAND PORTFOLIO" in val: return ['background-color: #e2e8f0; font-weight: bold; color: #0f172a; border-top: 2px solid #94a3b8'] * len(row)
                    return [''] * len(row)
                    
                st.write("#### 📊 Building Summary Statement Preview")
                st.dataframe(b_display_df.style.apply(highlight_subtotals, axis=1).format({'Gross Sales': 'R {:,.2f}', 'Net To Principle': 'R {:,.2f}', 'Service Fees': 'R {:,.2f}', 'VAT': 'R {:,.2f}', 'Units Consumed': '{:,.2f}', 'Transactions': '{:,}'}), use_container_width=True)
                
                st.markdown("#### 📥 Document Compilation & Export Options")
                b_exp_col1, b_exp_col2 = st.columns(2)
                window_label_b = f"Selected Range ({len(local_months_b)} Months)" if len(local_months_b) < len(chron_timeline) else "Full Historical Portfolio Range"
                with b_exp_col1:
                    xl_buffer_b = io.BytesIO()
                    with pd.ExcelWriter(xl_buffer_b, engine='openpyxl') as xl_writer_b: b_display_df.to_excel(xl_buffer_b, index=False, sheet_name="Building Summary Statement")
                    st.download_button(label="📥 Export Building Statement as Excel Ledger", data=xl_buffer_b.getvalue(), file_name=f"Building_Summary_Statement_{datetime.now().strftime('%Y%m%d')}.xlsx", use_container_width=True)
                with b_exp_col2:
                    if FPDF:
                        pdf_bytes_b = gen_building_summary_pdf(summary_df=b_display_df, total_metrics=totals_b, period_label=window_label_b, portfolio_label=str(st.session_state['sel_owner']), logo_path="logo.png")
                        if pdf_bytes_b: st.download_button(label="📥 Export Executive Building PDF Summary", data=pdf_bytes_b, file_name=f"Building_Summary_Statement_{datetime.now().strftime('%Y%m%d')}.pdf", use_container_width=True)
                        
        with t3:
            st.markdown("### ⚠️ Dormant Meters Audit Suite")
            dorm_base = working_df[working_df['Building Detail'].isin(sb_local)]
            if dorm_base.empty: st.warning("No tracking records exist mapping back to this building context sequence.")
            else:
                lookback_days = st.slider("Define Dormancy Threshold (Days of Continuous Inactivity):", min_value=15, max_value=120, value=60, step=5)
                global_max_date = dorm_base['Trans_date'].max()
                st.info(f"💡 Target lookback reference calculation locked to newest available transaction timestamp: **{global_max_date.strftime('%Y-%m-%d')}**")
                
                dorm_grouped = dorm_base.groupby('Meter Number').agg({'Trans_date': 'max', 'Building Detail': 'first', 'Client': 'first', 'Customer Surname': 'first'}).reset_index()
                dorm_grouped['Days Inactive'] = (global_max_date - dorm_grouped['Trans_date']).dt.days
                dormant_filtered = dorm_grouped[dorm_grouped['Days Inactive'] >= lookback_days].sort_values('Days Inactive', ascending=False)
                
                dormant_display = dormant_filtered.rename(columns={'Meter Number': 'Meter Identifier', 'Trans_date': 'Last Successful Purchase', 'Building Detail': 'Asset Location', 'Client': 'Client Vendor Account', 'Customer Surname': 'Tenant Reference', 'Days Inactive': 'Consecutive Inactivity Days'})
                st.write(f"#### 📋 Dormancy Directory Summary ({len(dormant_display)} Meters Flagged)")
                if dormant_display.empty: st.success(f"🎉 Complete structural activity verified! Zero meters exceed the {lookback_days}-day lookup constraints.")
                else:
                    st.dataframe(dormant_display.style.format({'Last Successful Purchase': lambda x: x.strftime('%Y-%m-%d %H:%M') if not pd.isna(x) else ''}), use_container_width=True)
                    xl_buf_dorm = io.BytesIO()
                    with pd.ExcelWriter(xl_buf_dorm, engine='openpyxl') as xl_wr_dorm: dormant_display.to_excel(xl_wr_dorm, index=False, sheet_name="Dormant Inactive Meters")
                    st.download_button(label="📥 Export Dormant Meters Audit Sheet", data=xl_buf_dorm.getvalue(), file_name=f"Dormant_Meters_Audit_{datetime.now().strftime('%Y%m%d')}.xlsx", use_container_width=True)

elif st.session_state['current_page'] == "UserAdmin":
    st.title("👥 User Administration")
    u_df = load_users()
    
    st.markdown("### 📋 Active System Access Accounts")
    display_users = u_df[['username', 'role', 'owner_name']].rename(columns={'username': 'System Username Identifier', 'role': 'Assigned Access Role', 'owner_name': 'Assigned Data Scope Allocation'})
    st.dataframe(display_users.style.set_properties(**{'font-weight': '600', 'color': '#1e293b'}), use_container_width=True)
    st.divider()
    
    t1, t2, t3, t4 = st.tabs(["Add Landlord", "Reset Password", "Delete User", "📢 Broadcast Notice"])
    with t1:
        with st.form("create_landlord", clear_on_submit=True):
            nu = st.text_input("New Landlord Username")
            np = st.text_input("Password", type="password")
            no = st.selectbox("Assign to Owner", ["All"] + sorted(raw_df['Owner Detail'].unique().tolist()) if not raw_df.empty else ["All"])
            if st.form_submit_button("Create Account"):
                if nu.strip() and np.strip():
                    if save_user(nu.strip(), np.strip(), "landlord", no): st.toast(f"Account for '{nu}' created successfully!", icon="✔️"); st.rerun()
                else: st.error("Form Input Validation Rejection: Username and password details cannot be empty.")
    with t2:
        ur = st.selectbox("Select Account", u_df['username'].tolist())
        npw = st.text_input("New Password", type="password")
        if st.button("Update Access"): 
            if update_user_password(ur, npw): st.success("Access Updated."); st.rerun()
    with t3:
        delete_opts = [un for un in u_df['username'].tolist() if un != "admin"]
        if not delete_opts: st.info("No landlord tracking sub-accounts currently available to purge.")
        else:
            ud = st.selectbox("Select Account to Delete", delete_opts)
            st.warning(f"⚠️ Action Required: Deleting account '{ud}' will permanently revoke their privileges.")
            if st.button("❌ Permanently Purge Account Access", use_container_width=True):
                if delete_user(ud): st.success(f"Security Profile for account '{ud}' has been purged successfully."); st.rerun()
    with t4:
        st.markdown("### 📢 Broadcast Notices Dispatch Center")
        with st.form("broadcast_panel"):
            notice_input_body = st.text_area("Alert Banner Message Text Content:", placeholder="Type maintenance details, pricing revisions, or portfolio compliance instructions here...")
            available_landlords = ["All"] + sorted([x for x in u_df['owner_name'].unique().tolist() if x != "All"])
            selected_audience_scope = st.selectbox("Notice Recipient Scope:", available_landlords)
            if st.form_submit_button("🚀 Deploy Notice Banner"):
                if notice_input_body.strip():
                    if save_notification(notice_input_body.strip(), selected_audience_scope): st.success("Notice banner deployed to matching system target channels."); st.rerun()
                else: st.error("Message body text parameter cannot evaluate blank inputs.")
        st.divider()
        if st.button("🧹 Clear All Dynamic Alert Banners Everywhere", use_container_width=True):
            if purge_all_notifications(): st.success("All historical system alert banners flushed from production storage."); st.rerun()

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
                    if st.button("⚙️ Compile Engineering Instruction", use_container_width=True): st.info(f"**Generated STS {token_type} Token:**"); st.code(generate_sts_token(), language="text")
                st.divider()
                st.dataframe(ledger_df, use_container_width=True)

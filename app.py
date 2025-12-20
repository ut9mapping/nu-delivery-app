import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime

# --- ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="NU Professional Tracker", page_icon="🛵", layout="wide")

# --- 1. การเชื่อมต่อ Google Sheets ---
def get_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])

def load_mapping_df():
    try:
        sh = get_sheets()
        sheet = sh.worksheet("Mapping")
        df = pd.DataFrame(sheet.get_all_records())
        df.columns = [str(c).strip() for c in df.columns]
        df = df.map(lambda x: str(x).strip() if isinstance(x, str) else x)
        return df
    except:
        return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])

# --- 2. ฟังก์ชันช่วยเลือก (Smart Filter) ---
def get_options(df, filters):
    temp_df = df.copy()
    for col, val in filters.items():
        if val and val != "-- เลือก --":
            temp_df = temp_df[temp_df[col] == val]
    return sorted([x for x in temp_df.iloc[:, len(filters)].unique() if x and x != "-" and x != ""])

# --- 3. UI หน้าหลัก ---
st.title("🛵 ระบบบันทึกพิกัด มน. (Dynamic Version)")
mapping_df = load_mapping_df()

tab1, tab2 = st.tabs(["📌 บันทึกงาน", "⚙️ โหมด Admin (จัดการโครงสร้าง)"])

with tab1:
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')

    if lat and lon:
        # STEP 1: ประตู
        gate = st.selectbox("1. เลือกประตู:", ["-- เลือก --"] + sorted(mapping_df['ประตู'].unique().tolist()))
        
        if gate != "-- เลือก --":
            col1, col2 = st.columns(2)
            
            # STEP 2: ฝั่งถนน/โซน
            with col1:
                zones = get_options(mapping_df, {"ประตู": gate})
                zone = st.selectbox("2. ฝั่งถนน/โซนหลัก:", ["-- เลือก --"] + zones) if zones else "-"
            
            # STEP 3: ซอยหลัก
            with col2:
                if zone != "-- เลือก --":
                    main_sois = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone})
                    main_soi = st.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + main_sois) if main_sois else "-"
                else: main_soi = "-- เลือก --"

            col3, col4 = st.columns(2)
            # STEP 4: ซอยย่อย (ถ้ามี)
            with col3:
                if main_soi != "-- เลือก --":
                    sub_sois = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi})
                    sub_soi = st.selectbox("4. ซอยย่อย/ทางเชื่อม (ถ้ามี):", ["-- เลือก --"] + sub_sois) if sub_sois else "-"
                else: sub_soi = "-- เลือก --"

            # STEP 5: ฝั่งในซอย/จุดละเอียด
            with col4:
                if sub_soi != "-- เลือก --":
                    details = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi, "ซอยย่อย/ทางเชื่อม": sub_soi})
                    detail = st.selectbox("5. ฝั่ง/จุดละเอียด:", ["-- เลือก --"] + details) if details else "-"
                else: detail = "-- เลือก --"

            extra = st.text_input("✍️ เลขห้อง/ชื่อหอ/หมายเหตุ:")

            if st.button("🚀 บันทึกพิกัด"):
                full_info = f"{gate} | {zone} | {main_soi} | {sub_soi} | {detail} | {extra}"
                sh = get_sheets()
                sh.get_worksheet(0).append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), full_info, lat, lon])
                st.success(f"บันทึกสำเร็จ: {full_info}")
    else:
        st.warning("📍 กรุณากด GPS")

with tab2:
    if st.text_input("รหัส Admin:", type="password") == "9999":
        st.header("➕ เพิ่มโครงสร้างพื้นที่ใหม่")
        st.info("ระบุข้อมูลจากใหญ่ไปเล็ก หากช่องไหนไม่มี (เช่น ไม่มีซอยย่อย) ให้ใส่เครื่องหมายลบ '-'")
        
        with st.form("add_form"):
            c1, c2, c3, c4, c5 = st.columns(5)
            a_gate = c1.text_input("ประตู")
            a_zone = c2.text_input("ฝั่งถนน/โซน")
            a_soi = c3.text_input("ซอยหลัก")
            a_sub = c4.text_input("ซอยย่อย (ถ้าไม่มีใส่ -)")
            a_det = c5.text_input("ฝั่ง/จุดละเอียด")
            
            if st.form_submit_button("➕ เพิ่มข้อมูล (ปุ่มบวก)"):
                sh = get_sheets()
                sh.worksheet("Mapping").append_row([a_gate, a_zone, a_soi, a_sub, a_det])
                st.cache_data.clear()
                st.success("เพิ่มข้อมูลโครงสร้างเรียบร้อย!")
                st.rerun()

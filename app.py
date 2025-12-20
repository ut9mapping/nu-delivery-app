import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import google.generativeai as genai
import re

# --- ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="NU Delivery Visualizer Pro", page_icon="🛵", layout="wide")

# --- 1. การเชื่อมต่อ Google Services ---
def get_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])

# เชื่อมต่อ AI Gemini
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    model = genai.GenerativeModel('models/gemini-2.0-flash') # ใช้เวอร์ชันเสถียร
except: 
    st.error("AI Config Error: กรุณาเช็ก API_KEY ใน Secrets")

# --- 2. ฟังก์ชันโหลดและล้างข้อมูล (ป้องกัน KeyError) ---
def load_mapping_df():
    try:
        sh = get_sheets()
        sheet = sh.worksheet("Mapping")
        data = sheet.get_all_records()
        if not data:
            return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])
        
        df = pd.DataFrame(data)
        # ลบเว้นวรรคที่หัวคอลัมน์และข้อมูลทุกช่องป้องกัน Error
        df.columns = [str(c).strip() for c in df.columns]
        df = df.map(lambda x: str(x).strip() if isinstance(x, str) else x)
        return df
    except Exception as e:
        st.error(f"Error Loading Mapping: {e}")
        return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])

def get_options(df, filters):
    temp_df = df.copy()
    for col, val in filters.items():
        if val and val != "-- เลือก --":
            temp_df = temp_df[temp_df[col] == val]
    # ดึงคอลัมน์ถัดไปจากจำนวน filter ที่ใส่มา
    target_col_idx = len(filters)
    if target_col_idx < len(df.columns):
        return sorted([x for x in temp_df.iloc[:, target_col_idx].unique() if x and x != "-" and x != ""])
    return []

# --- 3. UI หลัก ---
st.title("📍 ระบบพิกัดขนส่ง มน. (Visual Search)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงานส่งของ", "🔍 ค้นหา & ดูภาพแผนที่", "⚙️ Admin (จัดการซอย)"])

# --- TAB 1: บันทึกงาน (5 ระดับ) ---
with tab1:
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')

    if lat and lon:
        st.success(f"📍 พิกัดพร้อมบันทึก: {lat:.6f}, {lon:.6f}")
        
        # ค้นหาประตู
        gate = st.selectbox("1. เลือกประตู:", ["-- เลือก --"] + sorted(mapping_df['ประตู'].unique().tolist()))
        
        if gate != "-- เลือก --":
            col1, col2 = st.columns(2)
            with col1:
                zones = get_options(mapping_df, {"ประตู": gate})
                zone = st.selectbox("2. ฝั่งถนน/โซน:", ["-- เลือก --"] + zones) if zones else "-"
            with col2:
                if zone != "-- เลือก --":
                    main_sois = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone})
                    main_soi = st.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + main_sois) if main_sois else "-"
                else: main_soi = "-- เลือก --"

            col3, col4 = st.columns(2)
            with col3:
                if main_soi != "-- เลือก --":
                    sub_sois = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi})
                    sub_soi = st.selectbox("4. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + sub_sois) if sub_sois else "-"
                else: sub_soi = "-- เลือก --"
            with col4:
                if sub_soi != "-- เลือก --":
                    details = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi, "ซอยย่อย/ทางเชื่อม": sub_soi})
                    detail = st.selectbox("5. ฝั่ง/จุดละเอียด:", ["-- เลือก --"] + details) if details else "-"
                else: detail = "-- เลือก --"

            extra = st.text_input("✍️ หมายเหตุเพิ่มเติม (เลขห้อง/ชื่อร้าน):")

            if st.button("🚀 ยืนยันบันทึกพิกัด"):
                with st.spinner("กำลังส่งข้อมูล..."):
                    sh = get_sheets()
                    log_sheet = sh.worksheet("Sheet1")
                    full_info = f"{gate} | {zone} | {main_soi} | {sub_soi} | {detail} | {extra}"
                    maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                    log_sheet.append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), full_info, lat, lon, maps_url])
                    st.balloons()
                    st.success("บันทึกสำเร็จ!")
    else:
        st.warning("📍 กรุณากดปุ่ม GPS เพื่อดึงพิกัดปัจจุบัน")

# --- TAB 2: ค้นหา + ภาพจำลองแผนที่ ---
with tab2:
    st.header("🔍 ค้นหาสถานที่ & ดูภาพจำลอง")
    query = st.text_input("ถาม AI เช่น 'ร้านเครปประตู 4 อยู่ตรงไหน', 'หอนริศาเคยไปส่งไหม'")
    
    if st.button("ค้นหาข้อมูล"):
        with st.spinner("AI กำลังตรวจสอบประวัติ..."):
            try:
                sh = get_sheets()
                history_df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
                
                # ลบช่องว่างหัวตารางกันพลาด
                history_df.columns = [str(c).strip() for c in history_df.columns]

                prompt = f"""
                นี่คือประวัติการส่งของ: {history_df.to_string()}
                คำถาม: {query}
                ช่วยตอบคำถามจากข้อมูล และถ้าเจอพิกัด ให้ใส่บรรทัดใหม่ว่า "COORD_FOUND: ละติจูด,ลองจิจูด"
                """
                
                response = model.generate_content(prompt).text
                
                # ดึงพิกัด
                coord_match = re.search(r"COORD_FOUND:\s*([0-9.]+),\s*([0-9.]+)", response)
                st.markdown(f"**🤖 AI:** {response.split('COORD_FOUND')[0]}")

                if coord_match:
                    m_lat, m_lon = float(coord_match.group(1)), float(coord_match.group(2))
                    st.write("---")
                    st.subheader("📸 ภาพจำลองแผนที่จุดส่ง")
                    map_df = pd.DataFrame({'lat': [m_lat], 'lon': [m_lon]})
                    st.map(map_df, zoom=17)
                    st.write(f"🔗 [เปิดใน Google Maps](https://www.google.com/maps?q={m_lat},{m_lon})")
            except Exception as e:
                st.error(f"ค้นหาไม่สำเร็จ: {e}")

# --- TAB 3: Admin (ปุ่มบวกเพิ่มซอย) ---
with tab3:
    st.header("⚙️ ระบบจัดการโครงสร้าง (Admin)")
    if st.text_input("ใส่รหัส PIN:", type="password") == "9999":
        st.subheader("➕ เพิ่มข้อมูลโครงสร้างใหม่")
        with st.form("add_structure"):
            c1, c2, c3 = st.columns(3)
            with c1: 
                a_gate = st.text_input("1. ประตู")
                a_zone = st.text_input("2. ฝั่งถนน/โซน")
            with c2:
                a_soi = st.text_input("3. ซอยหลัก")
                a_sub = st.text_input("4. ซอยย่อย (ถ้าไม่มีใส่ -)")
            with c3:
                a_det = st.text_input("5. ฝั่ง/จุดรายละเอียด")
            
            if st.form_submit_button("➕ เพิ่มข้อมูลลงระบบ"):
                if a_gate and a_soi:
                    sh = get_sheets()
                    sh.worksheet("Mapping").append_row([a_gate, a_zone, a_soi, a_sub, a_det])
                    st.cache_data.clear()
                    st.success("เพิ่มข้อมูลแล้ว! กรุณากด Refresh หน้าเว็บ")
                    st.rerun()
                else:
                    st.error("กรุณากรอก ประตู และ ซอยหลัก เป็นอย่างน้อย")

import streamlit as st
import google.generativeai as genai
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime

# --- ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="NU Dynamic Database", page_icon="📍", layout="wide")

# --- 1. ฟังก์ชันเชื่อมต่อ Google Sheets ---
def get_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    spreadsheet = client.open_by_key(st.secrets["SHEET_ID"])
    return spreadsheet

# --- 2. ดึงข้อมูล Mapping (ซอย/ประตู) จาก Sheet ---
@st.cache_data(ttl=60) # รีเฟรชข้อมูลทุก 1 นาที
def load_mapping():
    sh = get_sheets()
    # สมมติว่าแผ่นงานที่เก็บชื่อซอยชื่อ 'Mapping'
    mapping_sheet = sh.worksheet("Mapping") 
    df = pd.DataFrame(mapping_sheet.get_all_records())
    return df

# --- 3. UI หลัก ---
st.title("🛵 ระบบบันทึกพิกัด (ฐานข้อมูลแก้ไขได้ผ่าน Sheet)")

try:
    mapping_df = load_mapping()
    
    tab1, tab2 = st.tabs(["📌 บันทึกงาน", "⚙️ จัดการฐานข้อมูลซอย"])

    with tab1:
        location = streamlit_geolocation()
        lat, lon = location.get('latitude'), location.get('longitude')

        if lat and lon:
            # STEP 1: เลือกประตู
            gate_list = mapping_df['ประตู'].unique().tolist()
            gate = st.selectbox("1️⃣ เลือกประตู:", ["-- เลือก --"] + gate_list)

            if gate != "-- เลือก --":
                # STEP 2: เลือกซอยหลัก (กรองตามประตู)
                filtered_alleys = mapping_df[mapping_df['ประตู'] == gate]['ซอยหลัก'].unique().tolist()
                main_soi = st.selectbox("2️⃣ เลือกซอยหลัก:", ["-- เลือก --"] + filtered_alleys)

                if main_soi != "-- เลือก --":
                    # STEP 3: เลือกจุดส่ง (กรองตามซอยหลัก)
                    spots = mapping_df[(mapping_df['ประตู'] == gate) & (mapping_df['ซอยหลัก'] == main_soi)]['รายละเอียดจุดส่ง'].tolist()
                    spot = st.selectbox("3️⃣ เลือกจุดส่ง/ฝั่ง:", spots)

                    extra = st.text_input("✍️ เพิ่มเติม (เลขห้อง/ชื่อหอ):")
                    full_record = f"{gate} | {main_soi} | {spot} | {extra}"
                    
                    if st.button("🚀 บันทึกข้อมูลลงฐานข้อมูล"):
                        sh = get_sheets()
                        data_sheet = sh.get_worksheet(0) # แผ่นงานแรกที่เก็บประวัติการส่ง
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                        
                        # หยอดข้อมูลลงแถวใหม่
                        data_sheet.append_row([now, full_record, lat, lon, maps_url])
                        st.balloons()
                        st.success("บันทึกสำเร็จ!")
        else:
            st.warning("📍 กรุณาเปิด GPS")

    with tab2:
        st.header("🛠 วิธีแก้ไขฐานข้อมูล (ซอย/ประตู)")
        st.write("คุณสามารถแก้ไข เพิ่ม หรือลบชื่อซอยได้โดยตรงที่ Google Sheets แผ่นงานชื่อ **'Mapping'**")
        st.info("💡 เมื่อแก้ใน Google Sheets เสร็จแล้ว ให้กลับมาหน้าเว็บนี้แล้วกดปุ่มด้านล่าง")
        if st.button("🔄 อัปเดตรายชื่อซอยล่าสุด"):
            st.cache_data.clear()
            st.rerun()
        
        # แสดงตารางปัจจุบันให้ดู
        st.subheader("ผังข้อมูลปัจจุบัน:")
        st.dataframe(mapping_df, use_container_width=True)

except Exception as e:
    st.error(f"เกิดข้อผิดพลาดในการโหลดข้อมูล: {e}")
    st.info("ตรวจสอบว่าคุณสร้าง Sheet ชื่อ 'Mapping' และมีหัวข้อ: ประตู, ซอยหลัก, รายละเอียดจุดส่ง เรียบร้อยแล้ว")

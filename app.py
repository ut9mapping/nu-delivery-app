import streamlit as st
import google.generativeai as genai
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
from PIL import Image

# --- ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="Gemini Delivery Pro", page_icon="📦", layout="wide")
st.title("📦 ระบบบันทึกพิกัดและวิเคราะห์การส่งของ")

# --- 1. เชื่อมต่อ Gemini 2.5 Flash ---
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    model = genai.GenerativeModel('models/gemini-2.5-flash')
except Exception as e:
    st.error(f"❌ Gemini Connection Error: {e}")

# --- 2. ฟังก์ชันจัดการ Google Sheets ---
def get_sheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(st.secrets["SHEET_ID"]).get_worksheet(0)
        return sheet
    except Exception as e:
        st.error(f"❌ Sheets Connection Error: {e}")
        return None

# --- 3. ส่วน UI หลัก ---
col_input, col_display = st.columns([1, 1])

with col_input:
    st.subheader("📍 ข้อมูลการส่งของ")
    
    # 3.1 ดึงพิกัด GPS
    location = streamlit_geolocation()
    lat = location.get('latitude')
    lon = location.get('longitude')
    
    if lat and lon:
        st.success(f"พิกัดปัจจุบัน: {lat}, {lon}")
        
        # 3.2 ถ่ายภาพหรือแนบรูป (Optional)
        img_file = st.camera_input("📷 ถ่ายรูปยืนยันการส่ง (ถ้ามี)")
        
        # 3.3 บันทึกเพิ่มเติม
        note = st.text_area("✍️ รายละเอียดเพิ่มเติม:", placeholder="เช่น บ้านปิดสนิท วางของไว้ที่รั้ว...")

        if st.button("🚀 ประมวลผลและบันทึก"):
            sheet = get_sheet()
            if sheet:
                with st.spinner('Gemini กำลังวิเคราะห์ข้อมูล...'):
                    try:
                        # เตรียมข้อมูลให้ Gemini (ใส่ทั้งข้อความและรูปภาพ)
                        prompt = f"พิกัด {lat}, {lon} รายละเอียด: {note}. ช่วยสรุปสถานะการส่งนี้สั้นๆ 1 ประโยค"
                        
                        if img_file:
                            img = Image.open(img_file)
                            response = model.generate_content([prompt, img])
                        else:
                            response = model.generate_content(prompt)
                        
                        ai_comment = response.text.strip()
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        
                        # บันทึกลง Sheet (เวลา, Lat, Lon, Note, AI)
                        sheet.append_row([now, lat, lon, note, ai_comment])
                        
                        st.balloons()
                        st.success("บันทึกข้อมูลสำเร็จ!")
                        st.info(f"🤖 AI วิเคราะห์ว่า: {ai_comment}")
                    except Exception as e:
                        st.error(f"Error: {e}")
    else:
        st.warning("👈 คลิกไอคอนหมุดด้านบนเพื่อดึงพิกัด GPS ก่อนครับ")

with col_display:
    st.subheader("🗺️ แผนที่พิกัดปัจจุบัน")
    if lat and lon:
        # แสดงแผนที่จุดที่อยู่ปัจจุบัน
        map_data = pd.DataFrame({'lat': [lat], 'lon': [lon]})
        st.map(map_data)
    else:
        st.info("รอพิกัด GPS เพื่อแสดงแผนที่...")

    st.write("---")
    st.subheader("🕒 ประวัติการบันทึกล่าสุด")
    if st.button("🔄 ดึงประวัติจาก Sheets"):
        sheet = get_sheet()
        if sheet:
            data = sheet.get_all_records()
            if data:
                df = pd.DataFrame(data)
                st.table(df.tail(5)) # โชว์ 5 แถวล่าสุด
            else:
                st.write("ยังไม่มีข้อมูลในตาราง")

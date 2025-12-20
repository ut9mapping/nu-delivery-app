import streamlit as st
import google.generativeai as genai
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
from PIL import Image

# --- ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="Gemini Smart Navigator", page_icon="📍", layout="wide")
st.title("📍 บันทึกพิกัดและระบบนำทางอัจฉริยะ")

# --- 1. เชื่อมต่อ Gemini 2.5 Flash ---
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    model = genai.GenerativeModel('models/gemini-2.5-flash')
except Exception as e:
    st.error(f"❌ Gemini Error: {e}")

# --- 2. ฟังก์ชันจัดการ Google Sheets ---
def get_sheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        gc = gspread.authorize(creds)
        sheet = gc.open_by_key(st.secrets["SHEET_ID"]).get_worksheet(0)
        
        # ตรวจสอบและสร้างหัวตารางถ้ายังไม่มี (เพิ่มคอลัมน์ ลิงก์นำทาง)
        headers = ["วัน-เวลา", "ละติจูด", "ลองจิจูด", "บันทึก", "AI สรุป", "ลิงก์นำทาง"]
        if not sheet.row_values(1):
            sheet.insert_row(headers, 1)
        return sheet
    except Exception as e:
        st.error(f"❌ Sheets Error: {e}")
        return None

# --- 3. ส่วน UI แบ่ง Tab ---
tab1, tab2 = st.tabs(["📌 บันทึกและรับพิกัด", "🔍 ค้นหาและนำทาง"])

# --- Tab 1: บันทึกข้อมูลพร้อมสร้างลิงก์ Map ---
with tab1:
    st.header("บันทึกพิกัดส่งของ")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        location = streamlit_geolocation()
        lat, lon = location.get('latitude'), location.get('longitude')
        
        if lat and lon:
            # สร้าง Google Maps URL
            google_maps_url = f"https://www.google.com/maps?q={lat},{lon}"
            
            st.success(f"📍 พิกัด: {lat}, {lon}")
            st.markdown(f"[🔗 เปิดดูใน Google Maps]({google_maps_url})") # แสดงลิงก์ให้กดดูทันที
            
            img_file = st.camera_input("📷 ถ่ายรูป (ถ้ามี)")
            note = st.text_area("✍️ บันทึกรายละเอียด:")
            
            if st.button("🚀 บันทึกข้อมูลลงฐานข้อมูล"):
                sheet = get_sheet()
                if sheet:
                    with st.spinner('AI กำลังบันทึกข้อมูล...'):
                        try:
                            # ให้ AI ช่วยสรุป
                            prompt = f"พิกัด {lat}, {lon} รายละเอียด: {note}. สรุปสั้นๆ 1 ประโยค"
                            if img_file:
                                response = model.generate_content([prompt, Image.open(img_file)])
                            else:
                                response = model.generate_content(prompt)
                            
                            ai_comment = response.text.strip()
                            now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                            
                            # บันทึก 6 คอลัมน์ (รวมลิงก์นำทาง)
                            sheet.append_row([now, lat, lon, note, ai_comment, google_maps_url])
                            
                            st.balloons()
                            st.success("บันทึกสำเร็จ!")
                        except Exception as e:
                            st.error(f"เกิดข้อผิดพลาด: {e}")
        else:
            st.info("👈 กรุณากดไอคอนวงกลมเพื่อดึงพิกัด GPS")

    with col2:
        if lat and lon:
            st.subheader("🗺️ แผนที่พิกัดปัจจุบัน")
            st.map(pd.DataFrame({'lat': [lat], 'lon': [lon]}))

# --- Tab 2: ระบบค้นหาด้วย AI + ลิงก์นำทาง ---
with tab2:
    st.header("🤖 ค้นหาสถานที่ด้วย AI")
    st.write("ตัวอย่าง: 'เมื่อวานฉันไปที่ไหนมาบ้าง?' หรือ 'หาพิกัดที่ฉันบันทึกว่าบ้านคุณเอ'")
    
    query = st.text_input("💬 ถาม AI เกี่ยวกับข้อมูลที่เคยบันทึก:")
    
    if st.button("🔍 ค้นหาพิกัด"):
        sheet = get_sheet()
        if sheet:
            with st.spinner('Gemini กำลังค้นหาข้อมูลและเตรียมลิงก์นำทาง...'):
                try:
                    data = sheet.get_all_records()
                    df = pd.DataFrame(data)
                    context = df.to_string()
                    
                    # สั่งให้ AI สร้างลิงก์นำทางในคำตอบด้วย
                    search_prompt = f"""
                    ข้อมูลใน Google Sheets:
                    {context}
                    
                    คำถาม: {query}
                    
                    คำแนะนำ: 
                    - ตอบคำถามให้ชัดเจนตามข้อมูลที่มี
                    - **สำคัญมาก**: หากระบุถึงสถานที่ใด ให้แสดง "ลิงก์นำทาง" (จากคอลัมน์ ลิงก์นำทาง) มาให้ผู้ใช้กดคลิกได้เลยในรูปแบบ [นำทางไปที่นี่](URL)
                    """
                    
                    ans = model.generate_content(search_prompt)
                    st.write("---")
                    st.subheader("💡 ผลการค้นหา:")
                    st.markdown(ans.text) # ใช้ markdown เพื่อให้คลิกลิงก์ได้
                    
                except Exception as e:
                    st.error(f"ค้นหาไม่สำเร็จ: {e}")

    with st.expander("📊 ดูตารางข้อมูลทั้งหมด"):
        sheet = get_sheet()
        if sheet:
            st.dataframe(pd.DataFrame(sheet.get_all_records()))

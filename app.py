import streamlit as st
import google.generativeai as genai
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
from PIL import Image

# --- ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="Gemini Delivery Smart App", page_icon="🤖", layout="wide")

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

# --- 3. ส่วน UI แบ่งเป็น Tab เพื่อให้ใช้งานง่าย ---
tab1, tab2 = st.tabs(["📍 บันทึกพิกัดใหม่", "🔍 ค้นหาด้วย AI"])

# --- Tab 1: การบันทึกข้อมูล ---
with tab1:
    st.header("บันทึกข้อมูลการส่งของ")
    col1, col2 = st.columns([1, 1])
    
    with col1:
        location = streamlit_geolocation()
        lat, lon = location.get('latitude'), location.get('longitude')
        
        if lat and lon:
            st.success(f"พิกัดปัจจุบัน: {lat}, {lon}")
            img_file = st.camera_input("📷 ถ่ายรูปยืนยัน")
            note = st.text_area("✍️ บันทึกเพิ่มเติม:")
            
            if st.button("🚀 บันทึกข้อมูล"):
                sheet = get_sheet()
                if sheet:
                    with st.spinner('กำลังประมวลผล...'):
                        prompt = f"พิกัด {lat}, {lon} รายละเอียด: {note}. สรุปสถานะการส่งสั้นๆ"
                        if img_file:
                            img = Image.open(img_file)
                            response = model.generate_content([prompt, img])
                        else:
                            response = model.generate_content(prompt)
                        
                        ai_comment = response.text.strip()
                        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        sheet.append_row([now, lat, lon, note, ai_comment])
                        st.balloons()
                        st.success("บันทึกสำเร็จ!")
        else:
            st.warning("👈 โปรดกดปุ่มวงกลมเพื่อแชร์พิกัด GPS")

    with col2:
        if lat and lon:
            st.subheader("🗺️ แผนที่จุดส่ง")
            st.map(pd.DataFrame({'lat': [lat], 'lon': [lon]}))

# --- Tab 2: ระบบค้นหาด้วย AI (AI Search & Assistant) ---
with tab2:
    st.header("🤖 ผู้ช่วยอัจฉริยะ (AI Search)")
    st.write("คุณสามารถถามข้อมูลที่เคยบันทึกไว้ได้ เช่น 'สัปดาห์นี้ส่งไปกี่ที่?' หรือ 'พิกัดล่าสุดอยู่ที่ไหน?'")
    
    user_query = st.text_input("💬 พิมพ์คำถามของคุณที่นี่:")
    
    if st.button("🔍 ให้ Gemini ค้นหาคำตอบ"):
        sheet = get_sheet()
        if sheet:
            with st.spinner('Gemini กำลังอ่านข้อมูลใน Sheet...'):
                try:
                    # ดึงข้อมูลทั้งหมดจาก Sheet มาเป็น Text เพื่อให้ AI อ่าน
                    all_records = sheet.get_all_records()
                    df = pd.DataFrame(all_records)
                    context_text = df.to_string() # แปลงตารางเป็นข้อความให้ AI
                    
                    # ส่งให้ Gemini วิเคราะห์
                    search_prompt = f"""
                    นี่คือข้อมูลการส่งของทั้งหมดใน Google Sheets:
                    {context_text}
                    
                    คำถามจากผู้ใช้: {user_query}
                    ช่วยตอบคำถามนี้โดยอิงจากข้อมูลด้านบน (ถ้าหาไม่เจอให้บอกตรงๆ ว่าไม่มีข้อมูล)
                    """
                    
                    search_response = model.generate_content(search_prompt)
                    
                    st.write("---")
                    st.subheader("💡 คำตอบจาก AI:")
                    st.write(search_response.text)
                    
                except Exception as e:
                    st.error(f"การค้นหาผิดพลาด: {e}")

    # แสดงตารางข้อมูลดิบด้านล่าง (เผื่ออยากดูเอง)
    with st.expander("📊 ดูข้อมูลดิบทั้งหมด"):
        sheet = get_sheet()
        if sheet:
            data = sheet.get_all_records()
            st.dataframe(pd.DataFrame(data))

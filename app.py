import streamlit as st
import google.generativeai as genai
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
from PIL import Image

# --- ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="Smart GPS Pro", page_icon="📍", layout="wide")

# --- 1. ระบบ Session State ---
if 'step' not in st.session_state: st.session_state.step = "input"
if 'temp_data' not in st.session_state: st.session_state.temp_data = {}

# --- 2. การเชื่อมต่อ ---
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    model = genai.GenerativeModel('models/gemini-2.5-flash')
except: st.error("Gemini Error")

def get_sheet():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["SHEET_ID"]).get_worksheet(0)

# --- 3. ฟังก์ชันอัจฉริยะ: หยอดข้อมูลให้ตรงคอลัมน์ ---
def save_to_correct_columns(sheet, data_dict):
    headers = sheet.row_values(1) # อ่านหัวคอลัมน์จาก Sheet จริง
    new_row = [""] * len(headers) # เตรียมแถวว่างตามจำนวนคอลัมน์ที่มี
    
    for i, header in enumerate(headers):
        h = header.lower()
        if "เวลา" in h: new_row[i] = data_dict['time']
        elif "ละติจูด" in h or "lat" in h: new_row[i] = data_dict['lat']
        elif "ลองจิจูด" in h or "lon" in h: new_row[i] = data_dict['lon']
        elif "บันทึก" in h or "รายละเอียด" in h: new_row[i] = data_dict['note']
        elif "สรุป" in h or "ai" in h: new_row[i] = data_dict['ai_summary']
        elif "นำทาง" in h or "map" in h: new_row[i] = data_dict['map_url']
    
    sheet.append_row(new_row)

# --- 4. ส่วน UI หลัก ---
tab1, tab2, tab3 = st.tabs(["📌 บันทึกพิกัด", "🔍 ค้นหาด้วย AI", "✏️ แก้ไขข้อมูล (9999)"])

# --- TAB 1: บันทึกพิกัด (มี AI คอยซักถาม) ---
with tab1:
    st.header("บันทึกข้อมูลการส่งของ")
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')

    if lat and lon:
        st.info(f"📍 ตรวจพบพิกัด: {lat}, {lon}")
        
        if st.session_state.step == "input":
            user_note = st.text_area("✍️ ระบุรายละเอียดการส่ง:", key="user_note_input")
            if st.button("ตรวจสอบความครบถ้วน"):
                # AI ตรวจสอบ ซอย/ซอยย่อย/ฝั่งถนน
                prompt = f"ตรวจสอบบันทึก: '{user_note}' หากขาดข้อมูล 'ซอย' หรือ 'ฝั่งถนน (ซ้าย/ขวา)' ให้ถามผู้ใช้ แต่ถ้าครบแล้วตอบ 'OK'"
                response = model.generate_content(prompt).text
                if "OK" in response.upper():
                    st.session_state.temp_data = {'lat': lat, 'lon': lon, 'note': user_note}
                    st.session_state.step = "save"
                    st.rerun()
                else:
                    st.session_state.temp_data = {'lat': lat, 'lon': lon, 'note': user_note, 'ask': response}
                    st.session_state.step = "clarify"
                    st.rerun()

        elif st.session_state.step == "clarify":
            st.warning(f"🤖 AI ต้องการข้อมูลเพิ่ม: {st.session_state.temp_data['ask']}")
            extra = st.text_input("ระบุข้อมูลที่ AI ถาม:")
            if st.button("ตกลง"):
                st.session_state.temp_data['note'] += f" | เพิ่มเติม: {extra}"
                st.session_state.step = "save"
                st.rerun()

        if st.session_state.step == "save":
            st.success("✅ ข้อมูลพร้อมบันทึกแล้ว!")
            if st.button("🚀 บันทึกลงคอลัมน์ใน Sheet"):
                sheet = get_sheet()
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                ai_sum = model.generate_content(f"สรุปบันทึกนี้สั้นๆ: {st.session_state.temp_data['note']}").text
                
                # เรียกใช้ฟังก์ชันหยอดคอลัมน์
                data_to_save = {
                    'time': now, 'lat': lat, 'lon': lon, 
                    'note': st.session_state.temp_data['note'], 
                    'ai_summary': ai_sum, 'map_url': maps_url
                }
                save_to_correct_columns(sheet, data_to_save)
                
                st.balloons()
                st.session_state.step = "input"
                st.success("บันทึกข้อมูลตรงตามคอลัมน์เรียบร้อย!")

# --- TAB 2: AI Search ---
with tab2:
    st.header("🔍 ถาม-ตอบ ข้อมูลใน Sheet")
    query = st.text_input("พิมพ์คำถาม (เช่น วันนี้ไปที่ไหนมาบ้าง?):")
    if st.button("ค้นหา"):
        sheet = get_sheet()
        df = pd.DataFrame(sheet.get_all_records())
        ans = model.generate_content(f"ข้อมูล:\n{df.to_string()}\n\nคำถาม: {query}").text
        st.markdown(ans)

# --- TAB 3: แก้ไข (รหัส 9999) ---
with tab3:
    st.header("✏️ แก้ไขข้อมูล (ต้องระบุ PIN)")
    sheet = get_sheet()
    df = pd.DataFrame(sheet.get_all_records())
    st.dataframe(df)
    
    idx = st.number_input("ลำดับแถวที่ต้องการแก้ (เริ่มที่ 0):", min_value=0, step=1)
    edit_col = st.selectbox("เลือกคอลัมน์ที่จะแก้:", df.columns)
    edit_val = st.text_input("ข้อมูลใหม่:")
    pin = st.text_input("รหัสยืนยัน (PIN):", type="password")
    
    if st.button("💾 ยืนยันแก้ไข"):
        if pin == "9999":
            # ค้นหาเลขที่คอลัมน์
            headers = sheet.row_values(1)
            col_idx = headers.index(edit_col) + 1
            sheet.update_cell(idx + 2, col_idx, edit_val)
            st.success("แก้ไขข้อมูลเรียบร้อย!")
        else:
            st.error("รหัสไม่ถูกต้อง!")

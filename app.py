import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from streamlit_js_eval import streamlit_js_eval
from datetime import datetime

# --- การตั้งค่าเบื้องต้น ---
st.set_page_config(page_title="Delivery Tracker", layout="centered")
st.title("📍 บันทึกพิกัดส่งของด้วย Gemini")

# --- 1. เชื่อมต่อ Google AI (Gemini) ---
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    # ใช้รุ่น 1.5-flash เพื่อความรวดเร็วและเลี่ยงปัญหา NotFound
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"❌ การเชื่อมต่อ Gemini ล้มเหลว: {e}")

# --- 2. ฟังก์ชันเชื่อมต่อ Google Sheets ---
def connect_to_sheet():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds_dict = st.secrets["gcp_service_account"]
        creds = Credentials.from_service_account_info(creds_dict, scopes=scope)
        client = gspread.authorize(creds)
        sheet = client.open_by_key(st.secrets["SHEET_ID"]).get_worksheet(0)
        return sheet
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่สำเร็จ: {e}")
        return None

# --- 3. ส่วนการดึงพิกัด GPS ---
st.subheader("ดึงข้อมูลตำแหน่งปัจจุบัน")

# ใช้ Container ครอบเพื่อให้ UI แสดงผลได้ชัดเจนขึ้น
with st.container():
    # ฟังก์ชันดึงค่าพิกัดจาก Browser
    location = streamlit_js_eval(data_key='geo', label='🎯 คลิกที่นี่เพื่อแชร์ตำแหน่ง GPS', request_permissions=True)

# ตรวจสอบว่าได้พิกัดมาหรือยัง
if location:
    lat = location['coords']['latitude']
    lon = location['coords']['longitude']
    
    st.success(f"✅ ตรวจพบพิกัด: {lat}, {lon}")
    
    # ช่องสำหรับกรอกรายละเอียดเพิ่มเติม
    note = st.text_area("✍️ บันทึกเพิ่มเติม (เช่น ชื่อลูกค้า หรือลักษณะบ้าน):", placeholder="ใส่รายละเอียดที่นี่...")

    if st.button("🚀 บันทึกข้อมูลและให้ Gemini วิเคราะห์"):
        sheet = connect_to_sheet()
        if sheet:
            with st.spinner('กำลังประมวลผล...'):
                try:
                    # ให้ Gemini สรุปข้อมูล
                    prompt = f"สรุปพิกัด {lat}, {lon} และข้อมูล '{note}' เป็นบันทึกการส่งของสั้นๆ ไม่เกิน 1 ประโยค"
                    response = model.generate_content(prompt)
                    ai_comment = response.text.strip()

                    # เตรียมข้อมูลบันทึก (เวลา, Lat, Lon, Note, AI)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([now, lat, lon, note, ai_comment])
                    
                    st.balloons()
                    st.success("บันทึกข้อมูลลง Google Sheets เรียบร้อยแล้ว!")
                    st.info(f"🤖 AI สรุปให้ว่า: {ai_comment}")
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาดขณะบันทึก: {e}")
else:
    # แสดงคำแนะนำหากปุ่มไม่ขึ้นหรือยังไม่ได้กด
    st.warning("⚠️ หากปุ่ม '🎯 คลิกที่นี่เพื่อแชร์ตำแหน่ง GPS' ไม่แสดง หรือกดแล้วไม่มีอะไรเกิดขึ้น:")
    st.write("1. ตรวจสอบว่าเบราว์เซอร์ของคุณอนุญาตการเข้าถึง **Location** หรือไม่ (ดูที่รูปแม่กุญแจตรงแถบพิมพ์ URL)")
    st.write("2. หากใช้งานบนมือถือ ตรวจสอบว่าเปิด GPS แล้ว")
    st.write("3. ลอง Refresh หน้าเว็บอีกครั้ง")

import streamlit as st
import google.generativeai as genai
import gspread
from google.oauth2.service_account import Credentials
from streamlit_js_eval import streamlit_js_eval
from datetime import datetime

# --- ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="GPS Delivery Tracker", layout="centered")

# CSS ตกแต่งปุ่มให้เห็นชัดๆ
st.markdown("""
    <style>
    div.stButton > button:first-child {
        background-color: #008CBA;
        color: white;
        height: 3em;
        width: 100%;
        border-radius:10px;
        font-size:20px;
        font-weight: bold;
    }
    </style>
    """, unsafe_allow_html=True)

st.title("📍 บันทึกพิกัดด้วย Gemini")

# --- 1. เชื่อมต่อ Google AI (Gemini) ---
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    model = genai.GenerativeModel('gemini-1.5-flash')
except Exception as e:
    st.error(f"❌ Gemini เชื่อมต่อไม่ได้: {e}")

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
        st.error(f"❌ Google Sheets เชื่อมต่อไม่ได้: {e}")
        return None

# --- 3. ส่วน GPS (จุดที่มีปัญหา) ---
st.subheader("ดึงข้อมูลตำแหน่ง")

# บังคับให้โหลด Javascript และสร้างปุ่ม
# ลองใส่ปุ่มลงในคอลัมน์เพื่อให้มัน re-render ได้ง่ายขึ้น
col1, col2 = st.columns([1, 1])
with col1:
    location = streamlit_js_eval(data_key='geo', label='🎯 กดเพื่อแชร์ตำแหน่ง GPS', request_permissions=True)

if location:
    lat = location['coords']['latitude']
    lon = location['coords']['longitude']
    
    st.success(f"✅ ตรวจพบพิกัด: {lat}, {lon}")
    
    # ส่วนกรอกข้อมูล
    note = st.text_area("✍️ บันทึกเพิ่มเติม:", placeholder="เช่น ชื่อลูกค้า หรือบ้านเลขที่...")

    if st.button("🚀 บันทึกข้อมูล"):
        sheet = connect_to_sheet()
        if sheet:
            with st.spinner('กำลังบันทึก...'):
                try:
                    # ให้ Gemini สรุป
                    prompt = f"สรุปพิกัด {lat}, {lon} และข้อมูล '{note}' เป็นบันทึกสั้นๆ 1 ประโยค"
                    response = model.generate_content(prompt)
                    ai_comment = response.text.strip()

                    # บันทึก (เวลา, Lat, Lon, Note, AI)
                    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    sheet.append_row([now, lat, lon, note, ai_comment])
                    
                    st.balloons()
                    st.success("บันทึกสำเร็จ!")
                    st.info(f"🤖 AI สรุป: {ai_comment}")
                except Exception as e:
                    st.error(f"เกิดข้อผิดพลาด: {e}")
else:
    # ถ้าปุ่มไม่ยอมขึ้น ให้แสดงกล่องข้อความเตือน
    st.warning("🔄 หากปุ่ม '🎯 กดเพื่อแชร์ตำแหน่ง GPS' ไม่ปรากฏ:")
    st.info("กรุณากด **Refresh (F5)** หน้าเว็บ 1 ครั้ง หรือตรวจสอบว่าคุณไม่ได้กด **'Block Location'** ในเบราว์เซอร์ครับ")

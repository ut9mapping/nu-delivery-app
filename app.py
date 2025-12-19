import streamlit as st
import google.generativeai as genai
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from streamlit_js_eval import streamlit_js_eval

# --- 1. เชื่อมต่อระบบ (AI & Google Sheets) ---
try:
    genai.configure(api_key=st.secrets["API_KEY"])
    
    # เชื่อมต่อ Google Sheets โดยใช้กุญแจจาก Secrets
    scope = ["https://www.googleapis.com/auth/spreadsheets"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    sheet = client.open_by_key(st.secrets["SHEET_ID"]).get_worksheet(0)
except Exception as e:
    st.error(f"❌ การเชื่อมต่อล้มเหลว: {e}")
    st.stop()

st.set_page_config(page_title="NU Mapping", page_icon="📍")
st.title("🛵 NU Delivery Mapping")

# --- 2. ฟังก์ชันดึงข้อมูล ---
@st.cache_data(ttl=10) # อัปเดตข้อมูลทุก 10 วินาที
def load_data():
    return pd.DataFrame(sheet.get_all_records())

df = load_data()

tab1, tab2 = st.tabs(["🔍 ค้นหา & นำทาง", "📌 บันทึกพิกัดใหม่"])

# --- Tab 1: ค้นหาและนำทาง ---
with tab1:
    query = st.text_input("พิมพ์ชื่อตึกหรือสถานที่เพื่อนำทาง:")
    if query:
        with st.spinner("AI กำลังค้นหาข้อมูล..."):
            context = df.to_string(index=False)
            model = genai.GenerativeModel('gemini-1.5-flash')
            prompt = f"ข้อมูล: {context}\nคำถาม: {query}\nตอบสั้นๆ ว่าสถานที่นี้คืออะไร และบอกจุดสังเกตถ้ามี"
            response = model.generate_content(prompt)
            st.info(response.text)
            
            # ค้นหาพิกัดในฐานข้อมูล
            match = df[df.apply(lambda row: query.lower() in row.astype(str).str.lower().values, axis=1)]
            if not match.empty:
                lat = match.iloc[0].get('Latitude')
                lon = match.iloc[0].get('Longitude')
                if lat and lon:
                    # สร้างลิงก์นำทาง Google Maps
                    nav_url = f"https://www.google.com/maps/dir/?api=1&destination={lat},{lon}"
                    st.link_button("🚗 เปิด Google Maps นำทางทันที", nav_url)
                else:
                    st.warning("⚠️ สถานที่นี้ยังไม่มีพิกัดบันทึกไว้")

# --- Tab 2: บันทึกพิกัดใหม่ ---
with tab2:
    st.subheader("เพิ่มจุดส่งของใหม่")
    name = st.text_input("ชื่อสถานที่ (เช่น ตึกวิศวะ Sc1):")
    note = st.text_area("หมายเหตุ/จุดจอดรถ:")
    
    # ดึงพิกัดจากเบราว์เซอร์มือถือ
    st.write("ขั้นตอนที่ 1: กดปุ่มด้านล่างเพื่อดึงตำแหน่งที่คุณยืนอยู่")
    loc = streamlit_js_eval(data_of='get_location', key='get_loc')
    
    if loc:
        lat = loc['coords']['latitude']
        lon = loc['coords']['longitude']
        st.success(f"📍 พบพิกัดแล้ว: {lat}, {lon}")
        
        if st.button("💾 บันทึกลงฐานข้อมูล"):
            if name:
                try:
                    # บันทึกลง Google Sheets (ชื่อ, หมายเหตุ, ละติจูด, ลองจิจูด)
                    sheet.append_row([name, note, lat, lon])
                    st.balloons()
                    st.success(f"บันทึก '{name}' เรียบร้อย! ข้อมูลจะปรากฏในการค้นหาทันที")
                    st.cache_data.clear()
                except Exception as e:
                    st.error(f"บันทึกไม่สำเร็จ: {e}")
            else:
                st.error("กรุณาใส่ชื่อสถานที่ด้วยครับ")
    else:
        st.info("รอพิกัดจาก GPS... (หากไม่ขึ้น ให้ตรวจสอบว่าเปิด Location ในมือถือหรือยัง)")

import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery Viewer", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่ได้: {e}")
        return None

# ปรับปรุงการโหลดข้อมูลให้เสถียรขึ้น
@st.cache_data(ttl=2) # ลดเวลาแคชเหลือ 2 วินาที
def load_data_robust():
    sh = get_sheets()
    if not sh: return pd.DataFrame()
    try:
        ws = sh.worksheet("Sheet1")
        # ดึงข้อมูลทั้งหมดออกมาเป็น List of Lists
        all_values = ws.get_all_values()
        
        if len(all_values) > 1:
            # สร้าง DataFrame โดยใช้แถวแรกเป็นหัวตาราง
            df = pd.DataFrame(all_values[1:], columns=all_values[0])
            # ล้างชื่อคอลัมน์: ตัดช่องว่างออก และทำให้เป็นตัวพิมพ์เล็กทั้งหมด
            df.columns = [str(c).strip().lower() for c in df.columns]
            return df
        else:
            return pd.DataFrame() # มีแค่หัวตาราง ไม่มีข้อมูล
    except Exception as e:
        st.error(f"Error loading: {e}")
        return pd.DataFrame()

# --- 2. หน้าจอหลัก ---
st.title("🛵 ระบบจัดการพิกัด (เช็กข้อมูลล่าสุด)")

tab1, tab2 = st.tabs(["📌 บันทึกข้อมูล", "🗺️ แผนที่และตารางข้อมูล"])

with tab1:
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    
    place_name = st.text_input("🏠 ชื่อสถานที่ / บ้านเลขที่")
    note = st.text_area("🗒️ หมายเหตุ")

    if st.button("💾 บันทึกข้อมูล", type="primary", use_container_width=True):
        if not lat or not place_name:
            st.warning("⚠️ กรุณารอพิกัด GPS และกรอกชื่อสถานที่")
        else:
            try:
                sh = get_sheets()
                ws = sh.worksheet("Sheet1")
                # เตรียม Row (A-J)
                new_data = [datetime.now().strftime("%Y-%m-%d %H:%M"), "-", lat, lon, place_name, "", "", "", note, "Complete"]
                ws.insert_row(new_data, index=2) # แทรกแถวบนสุด
                st.success("✅ บันทึกลง Google Sheets แล้ว!")
                st.cache_data.clear() # ล้างแคชทันทีเพื่อให้ Tab 2 อัปเดต
            except Exception as e:
                st.error(f"บันทึกไม่สำเร็จ: {e}")

with tab2:
    st.subheader("📊 ข้อมูลทั้งหมดในระบบ")
    
    # ปุ่มกดเพื่อบังคับรีโหลด
    if st.button("🔄 ดึงข้อมูลใหม่จาก Google Sheets เดี๋ยวนี้"):
        st.cache_data.clear()
        st.rerun()

    df = load_data_robust()

    if not df.empty:
        # ตรวจสอบชื่อคอลัมน์ที่โหลดมาได้จริง (สำหรับ Debug)
        with st.expander("🛠️ ตรวจสอบหัวตารางที่แอปมองเห็น"):
            st.write("คอลัมน์ที่พบ:", df.columns.tolist())
            st.write("จำนวนข้อมูล:", len(df), "แถว")

        # พยายามแปลง lat/lon เป็นตัวเลข
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        
        # กรองเฉพาะแถวที่มีพิกัดเพื่อโชว์บนแผนที่
        df_map = df.dropna(subset=['lat', 'lon'])

        # แสดงตารางข้อมูลก่อน (เพื่อให้มั่นใจว่าดึงมาได้)
        st.write("📋 ข้อมูลล่าสุดในชีต:")
        st.dataframe(df, use_container_width=True)

        if not df_map.empty:
            st.write("📍 พิกัดบนแผนที่:")
            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(
                    latitude=df_map['lat'].iloc[0], 
                    longitude=df_map['lon'].iloc[0], 
                    zoom=13
                ),
                layers=[
                    pdk.Layer(
                        "ScatterplotLayer",
                        df_map,
                        get_position='[lon, lat]',
                        get_color='[255, 0, 0, 160]',
                        get_radius=50,
                        pickable=True
                    ),
                ],
                tooltip={"text": "{place_name}"}
            ))
        else:
            st.info("💡 มีข้อมูลในตารางแต่ยังไม่มีพิกัด (lat/lon) ที่ถูกต้องสำหรับแสดงบนแผนที่")
    else:
        st.warning("⚠️ ไม่เจอข้อมูลใน Sheet1 (ลองตรวจสอบว่าพิมพ์ชื่อ Sheet1 ถูกต้องหรือไม่)")

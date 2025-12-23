import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. ตั้งค่าการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery Final Fix", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client.open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อมต่อไม่ได้: {e}")
        return None

# โหลดข้อมูล (ไม่ใช้ Cache ในส่วนตาราง เพื่อให้เห็นความจริงล่าสุด)
def load_sheet_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame()
    try:
        # ดึงจาก Sheet1
        df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        return df
    except: return pd.DataFrame()

# --- 2. หน้าจอหลัก ---
st.title("🚀 ระบบบันทึกพิกัด (เวอร์ชันแก้ไขด่วน)")

# ตรวจสอบเบื้องต้น (Debug Zone)
with st.expander("🛠️ คลิกเพื่อตรวจสอบการเชื่อมต่อ (Debug)", expanded=False):
    sh = get_sheets()
    if sh:
        st.success(f"✅ ตอนนี้แอปเชื่อมต่อกับไฟล์ชื่อ: **{sh.title}**")
        st.write("แผ่นงานที่มีในไฟล์นี้:", [w.title for w in sh.worksheets()])
    else:
        st.error("❌ เชื่อมต่อไฟล์ไม่ได้ ตรวจสอบ SHEET_ID ใน Secrets")

tab1, tab2 = st.tabs(["📌 บันทึกข้อมูล", "🗺️ ดูข้อมูลในชีตปัจจุบัน"])

with tab1:
    # ดึงพิกัด
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    
    if lat:
        st.success(f"📍 พิกัด GPS ล็อกแล้ว: {lat}, {lon}")
    else:
        st.warning("📡 กำลังรอพิกัด GPS... (หากรอนานแล้วไม่มา ให้ลองเปลี่ยนเบราว์เซอร์หรือเปิด GPS ในมือถือ)")

    p_name = st.text_input("🏠 ชื่อสถานที่ / บ้านเลขที่", placeholder="เช่น หอพักคุณป้า")
    note = st.text_area("🗒️ หมายเหตุ")

    if st.button("💾 บันทึกที่แถวบนสุด", type="primary", use_container_width=True):
        if not lat:
            st.error("❌ บันทึกไม่ได้: ไม่พบพิกัด GPS")
        elif not p_name:
            st.warning("⚠️ โปรดกรอกชื่อสถานที่")
        else:
            try:
                sh = get_sheets()
                ws = sh.worksheet("Sheet1")
                
                # เตรียมข้อมูล 10 คอลัมน์ (A-J)
                new_row = [
                    datetime.now().strftime("%Y-%m-%d %H:%M"), # A
                    "-",           # B: location_path (ย่อไว้ก่อน)
                    lat, lon,      # C, D
                    p_name,        # E
                    "", "", "",    # F, G, H
                    note,          # I
                    "Complete"     # J
                ]
                
                # เปลี่ยนจาก append_row เป็น insert_row(..., index=2) 
                # เพื่อให้ข้อมูลโผล่ที่ "แถวที่ 2" (ใต้หัวข้อ) เสมอ!
                ws.insert_row(new_row, index=2)
                
                st.balloons()
                st.success(f"✅ บันทึกสำเร็จ! ข้อมูลจะอยู่ที่ 'แถวที่ 2' ของไฟล์คุณทันที")
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")

with tab2:
    st.subheader("📊 ข้อมูลจริงที่ดึงได้จาก Google Sheets")
    if st.button("🔄 ดึงข้อมูลล่าสุด"):
        st.cache_data.clear()
    
    df_live = load_sheet_data()
    if not df_live.empty:
        st.dataframe(df_live, use_container_width=True)
        
        # แสดงแผนที่เฉพาะตัวที่มีพิกัด
        df_live['lat'] = pd.to_numeric(df_live['lat'], errors='coerce')
        df_live['lon'] = pd.to_numeric(df_live['lon'], errors='coerce')
        df_map = df_live.dropna(subset=['lat', 'lon'])
        
        if not df_map.empty:
            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(latitude=df_map['lat'].iloc[0], longitude=df_map['lon'].iloc[0], zoom=14),
                layers=[pdk.Layer("ScatterplotLayer", df_map, get_position='[lon, lat]', get_color='[255, 0, 0, 160]', get_radius=30)],
            ))
    else:
        st.info("ไม่พบข้อมูลใน Sheet1 หรือหัวตารางไม่ถูกต้อง")

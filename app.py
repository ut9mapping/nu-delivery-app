import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าระบบและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery Master V3", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        client = gspread.authorize(creds)
        return client.open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่สำเร็จ: {e}")
        return None

# ฟังก์ชันโหลดข้อมูลแบบป้องกันชื่อคอลัมน์ซ้ำ
@st.cache_data(ttl=2)
def load_sheet_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame()
    try:
        ws = sh.worksheet("Sheet1")
        all_vals = ws.get_all_values()
        if len(all_vals) > 0:
            raw_headers = all_vals[0]
            # จัดการชื่อคอลัมน์ซ้ำ (Deduplicate)
            clean_headers = []
            for i, h in enumerate(raw_headers):
                name = str(h).strip().lower() if h else f"col_{i}"
                if name in clean_headers or name == "":
                    name = f"{name}_{i}"
                clean_headers.append(name)
            
            df = pd.DataFrame(all_vals[1:], columns=clean_headers)
            return df
        return pd.DataFrame()
    except:
        return pd.DataFrame()

# --- 2. ส่วน UI หน้าหลัก ---
st.title("📍 ระบบบันทึกพิกัด NU Delivery")

tab1, tab2 = st.tabs(["📌 บันทึกพิกัดใหม่", "🗺️ แผนที่ & ตารางข้อมูล"])

with tab1:
    st.subheader("เพิ่มข้อมูลใหม่")
    
    # ดึงพิกัด GPS
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    
    if lat:
        st.success(f"✅ จับพิกัดได้: {lat}, {lon}")
    else:
        st.warning("📡 กำลังรอสัญญาณ GPS... (โปรดกดยอมรับสิทธิ์ระบุตำแหน่ง)")

    # ฟอร์มกรอกข้อมูล
    place_name = st.text_input("🏠 ชื่อสถานที่ / บ้านเลขที่ (จำเป็น)")
    location_path = st.text_input("📍 เส้นทาง/ซอย (เช่น ประตู 4 > ซอย 2)")
    note = st.text_area("🗒️ หมายเหตุเพิ่มเติม")

    if st.button("💾 บันทึกข้อมูลลงแถวใหม่", type="primary", use_container_width=True):
        if not lat or not lon:
            st.error("❌ บันทึกไม่ได้: ไม่พบพิกัด GPS")
        elif not place_name:
            st.warning("⚠️ โปรดกรอกชื่อสถานที่")
        else:
            with st.spinner("กำลังส่งข้อมูล..."):
                try:
                    sh = get_sheets()
                    ws = sh.worksheet("Sheet1")
                    
                    # เตรียมข้อมูลให้ตรง 10 คอลัมน์ (A-J)
                    new_row = [
                        datetime.now().strftime("%Y-%m-%d %H:%M"), # A: timestamp
                        location_path,                             # B: location_path
                        lat,                                       # C: lat
                        lon,                                       # D: lon
                        place_name,                                # E: place_name
                        "", "", "",                                # F, G, H: images (ว่าง)
                        note,                                      # I: note
                        "Complete"                                 # J: status
                    ]
                    
                    # บันทึกแบบแทรกแถวที่ 2 (เพื่อให้ข้อมูลใหม่ขึ้นข้างบนเสมอ)
                    ws.insert_row(new_row, index=2)
                    
                    st.balloons()
                    st.success(f"✅ บันทึก '{place_name}' สำเร็จแล้ว! ข้อมูลจะปรากฏที่แถวที่ 2")
                    st.cache_data.clear() # ล้างแคชเพื่อให้ Tab 2 เห็นข้อมูลทันที
                except Exception as e:
                    st.error(f"❌ เกิดข้อผิดพลาดขณะบันทึก: {e}")

with tab2:
    st.subheader("ตรวจสอบข้อมูลในระบบ")
    
    if st.button("🔄 อัปเดตข้อมูลล่าสุด"):
        st.cache_data.clear()
        st.rerun()

    df = load_sheet_data()
    
    if not df.empty:
        # ส่วนค้นหา
        search_query = st.text_input("🔍 ค้นหาชื่อสถานที่ในตาราง:")
        
        # กรองข้อมูล
        display_df = df.copy()
        if search_query:
            display_df = display_df[display_df.astype(str).apply(lambda x: x.str.contains(search_query, case=False)).any(axis=1)]

        # แสดงตาราง
        st.write(f"พบข้อมูลทั้งหมด {len(display_df)} รายการ")
        st.dataframe(display_df, use_container_width=True)

        # เตรียมแผนที่
        if 'lat' in display_df.columns and 'lon' in display_df.columns:
            display_df['lat'] = pd.to_numeric(display_df['lat'], errors='coerce')
            display_df['lon'] = pd.to_numeric(display_df['lon'], errors='coerce')
            df_map = display_df.dropna(subset=['lat', 'lon'])
            
            if not df_map.empty:
                st.write("📍 ตำแหน่งบนแผนที่:")
                st.pydeck_chart(pdk.Deck(
                    initial_view_state=pdk.ViewState(
                        latitude=df_map['lat'].iloc[0], 
                        longitude=df_map['lon'].iloc[0], 
                        zoom=14
                    ),
                    layers=[
                        pdk.Layer(
                            "ScatterplotLayer",
                            df_map,
                            get_position='[lon, lat]',
                            get_color='[255, 0, 0, 160]',
                            get_radius=40,
                            pickable=True
                        ),
                    ],
                    tooltip={"text": "{place_name}\n{location_path}"}
                ))
    else:
        st.info("ยังไม่มีข้อมูลในระบบ หรือกำลังโหลด...")

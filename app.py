import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. ตั้งค่าการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery Master", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่ได้: {e}")
        return None

# ฟังก์ชันโหลดข้อมูล (ล้างแคชบ่อยขึ้นเพื่อให้เห็นข้อมูลใหม่ทันที)
@st.cache_data(ttl=5)
def load_all_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame(), pd.DataFrame()
    
    # โหลด Mapping
    try:
        m_df = pd.DataFrame(sh.worksheet("Mapping").get_all_records()).astype(str)
    except: m_df = pd.DataFrame()

    # โหลด Sheet1
    try:
        l_df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        # แปลงหัวตารางเป็นตัวเล็กและตัดช่องว่างทิ้งป้องกัน Error
        l_df.columns = [str(c).strip().lower() for c in l_df.columns]
    except: l_df = pd.DataFrame()
    
    return m_df, l_df

# ฟังก์ชันดึงตัวเลือกDropdown
def get_opts(df, col_name, filters={}):
    if df.empty or col_name not in df.columns: return ["-- เลือก --"]
    tmp = df.copy()
    for k, v in filters.items():
        if k in tmp.columns and v and v != "-- เลือก --":
            tmp = tmp[tmp[k] == v]
    res = sorted([str(x).strip() for x in tmp[col_name].unique() if x and str(x).lower() not in ["nan", "none", ""]])
    return ["-- เลือก --"] + res

mapping_df, log_df = load_all_data()

# --- 2. หน้าจอหลัก (แบ่งเป็น 2 Tab หลัก) ---
st.title("🛵 ระบบจัดการพิกัด (เวอร์ชันเสถียรที่สุด)")

tab1, tab2 = st.tabs(["📌 บันทึกพิกัดใหม่", "🗺️ แผนที่ & ตรวจสอบข้อมูล"])

# --- TAB 1: บันทึกข้อมูล ---
with tab1:
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    
    if lat:
        st.success(f"📍 พิกัด GPS พร้อมบันทึก: {lat}, {lon}")
    else:
        st.warning("📡 กำลังรอพิกัด GPS... (โปรดกดยอมรับสิทธิ์ระบุตำแหน่ง)")

    place_name = st.text_input("🏠 ชื่อสถานที่ / บ้านเลขที่ (จำเป็น)")
    
    with st.expander("📍 ระบุรายละเอียดตำแหน่ง (ข้ามได้)", expanded=False):
        c1, c2 = st.columns(2)
        g = c1.selectbox("ประตู", get_opts(mapping_df, "ประตู"))
        z = c2.selectbox("ฝั่งถนน/โซน", get_opts(mapping_df, "ฝั่งถนน/โซน", {"ประตู": g}))
        m = c1.selectbox("ซอยหลัก", get_opts(mapping_df, "ซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z}))
        ms = c2.selectbox("ฝั่งซอยหลัก", get_opts(mapping_df, "ฝั่งซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m}))

    note = st.text_area("🗒️ หมายเหตุ")

    if st.button("🚀 ยืนยันบันทึกข้อมูล", use_container_width=True, type="primary"):
        if not lat or not lon:
            st.error("❌ บันทึกไม่ได้: ไม่พบพิกัด GPS")
        elif not place_name:
            st.warning("⚠️ โปรดระบุชื่อสถานที่")
        else:
            try:
                sh = get_sheets()
                ws = sh.worksheet("Sheet1")
                
                path_str = f"{g} > {z} > {m} > {ms}".replace("-- เลือก --", "-")
                
                # เตรียมข้อมูล 10 คอลัมน์ (A-J) ตามหัวข้อภาษาอังกฤษในชีตของคุณ
                new_row = [
                    datetime.now().strftime("%Y-%m-%d %H:%M"), # timestamp
                    path_str,                                  # location_path
                    lat,                                       # lat
                    lon,                                       # lon
                    place_name,                                # place_name
                    "", "", "",                                # img1, img2, img3
                    note,                                      # note
                    "Complete"                                 # status
                ]
                
                ws.append_row(new_row)
                st.balloons()
                st.success(f"✅ บันทึก '{place_name}' สำเร็จแล้ว!")
                st.cache_data.clear() # ล้างแคชทันทีเพื่อให้หน้าแผนที่เห็นข้อมูล
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")

# --- TAB 2: แผนที่ & ตารางข้อมูล ---
with tab2:
    st.subheader("🗺️ อาณาเขตพิกัดทั้งหมด")
    
    # โหลดข้อมูลสดๆ
    _, current_df = load_all_data()
    
    if not current_df.empty:
        # ตรวจสอบว่ามีคอลัมน์ lat/lon ไหม
        if 'lat' in current_df.columns and 'lon' in current_df.columns:
            current_df['lat'] = pd.to_numeric(current_df['lat'], errors='coerce')
            current_df['lon'] = pd.to_numeric(current_df['lon'], errors='coerce')
            df_map = current_df.dropna(subset=['lat', 'lon'])

            # ส่วนการค้นหา
            search = st.text_input("🔍 ค้นหาชื่อสถานที่/ซอย:")
            if search:
                df_map = df_map[df_map.astype(str).apply(lambda x: x.str.contains(search, case=False)).any(axis=1)]

            if not df_map.empty:
                # แสดงแผนที่
                st.pydeck_chart(pdk.Deck(
                    initial_view_state=pdk.ViewState(latitude=df_map['lat'].mean(), longitude=df_map['lon'].mean(), zoom=14),
                    layers=[pdk.Layer("ScatterplotLayer", df_map, get_position='[lon, lat]', get_color='[0, 200, 0, 160]', get_radius=30, pickable=True)],
                    tooltip={"text": "{place_name}\n{location_path}"}
                ))
            
            st.write("📊 **ข้อมูลล่าสุดในระบบ (10 รายการล่าสุด):**")
            st.dataframe(current_df.tail(10), use_container_width=True)
        else:
            st.error("❌ หัวตารางใน Sheet1 ไม่ตรง! ต้องมีคำว่า lat และ lon")
    else:
        st.info("ยังไม่มีข้อมูลในระบบ")

    if st.button("🔄 อัปเดตข้อมูล (Refresh)"):
        st.cache_data.clear()
        st.rerun()

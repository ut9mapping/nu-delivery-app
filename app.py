import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าหน้ากระดาษและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery Master", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่สำเร็จ: {e}")
        return None

@st.cache_data(ttl=2)
def load_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame(), pd.DataFrame()
    
    # โหลด Mapping (สำหรับตัวเลือก dropdown)
    try:
        m_df = pd.DataFrame(sh.worksheet("Mapping").get_all_records())
        m_df.columns = [str(c).strip() for c in m_df.columns]
    except: m_df = pd.DataFrame()

    # โหลด Sheet1 (ข้อมูลพิกัดที่บันทึกไว้)
    try:
        l_df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        l_df.columns = [str(c).strip() for c in l_df.columns]
    except: l_df = pd.DataFrame()
    
    return m_df, l_df

# โหลดข้อมูลเตรียมไว้
mapping_df, log_df = load_data()

# ฟังก์ชันดึงตัวเลือกDropdown
def get_opts(col_name, filters={}):
    if mapping_df.empty or col_name not in mapping_df.columns:
        return ["-- เลือก --"]
    tmp = mapping_df.copy()
    for k, v in filters.items():
        if k in tmp.columns and v and v != "-- เลือก --":
            tmp = tmp[tmp[k].astype(str) == str(v)]
    res = sorted([str(x).strip() for x in tmp[col_name].unique() if x and str(x).lower() not in ["nan", "none", ""]])
    return ["-- เลือก --"] + res

# --- 2. ส่วนหน้าตาโปรแกรม (UI) ---
st.title("🛵 ระบบจัดการพิกัด NU Delivery")

tab1, tab2 = st.tabs(["📌 บันทึกงานด่วน", "🗺️ อาณาเขตพิกัดทั้งหมด"])

# --- TAB 1: บันทึกงาน (กรอกแค่ชื่อก็บันทึกได้) ---
with tab1:
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    
    if lat:
        st.success(f"📍 พิกัด GPS พร้อม: {lat}, {lon}")
    else:
        st.warning("📡 กำลังรอพิกัด GPS... (โปรดกดยอมรับสิทธิ์ในเบราว์เซอร์)")

    st.subheader("🏠 ข้อมูลสถานที่")
    place_name = st.text_input("ชื่อสถานที่ / บ้านเลขที่ (จำเป็น)")

    with st.expander("📍 ระบุรายละเอียดตำแหน่ง (เลือกหรือไม่ก็ได้)", expanded=False):
        c1, c2 = st.columns(2)
        g = c1.selectbox("1. ประตู", get_opts("ประตู"))
        z = c2.selectbox("2. ฝั่งถนน/โซน", get_opts("ฝั่งถนน/โซน", {"ประตู": g}))
        m = c1.selectbox("3. ซอยหลัก", get_opts("ซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z}))
        ms = c2.selectbox("4. ฝั่งซอยหลัก", get_opts("ฝั่งซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m}))

    note = st.text_area("🗒️ หมายเหตุ")

    if st.button("🚀 บันทึกข้อมูลลงระบบ", use_container_width=True, type="primary"):
        if not lat:
            st.error("❌ บันทึกไม่ได้: ไม่พบพิกัด GPS")
        elif not place_name:
            st.warning("⚠️ โปรดระบุชื่อสถานที่")
        else:
            try:
                sh = get_sheets()
                ws = sh.worksheet("Sheet1")
                
                # รวมเส้นทางตำแหน่ง
                path_str = f"{g} > {z} > {m} > {ms}".replace("-- เลือก --", "-")
                
                # เตรียมข้อมูล 10 คอลัมน์ (A-J) ตามหัวข้อภาษาอังกฤษในรูปของคุณ
                new_row = [
                    datetime.now().strftime("%Y-%m-%d %H:%M"), # A: timestamp
                    path_str,       # B: location_path
                    lat,            # C: lat
                    lon,            # D: lon
                    place_name,     # E: place_name
                    "", "", "",     # F, G, H: img1, img2, img3 (ว่าง)
                    note,           # I: note
                    "Complete"      # J: status
                ]
                
                ws.append_row(new_row)
                st.balloons()
                st.success(f"✅ บันทึกสำเร็จ! ข้อมูล '{place_name}' ลงระบบแล้ว")
                st.cache_data.clear()
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาด: {e}")

# --- TAB 2: แผนที่อาณาเขต (No-Refresh) ---
@st.fragment
def show_map():
    st.subheader("🗺️ ตรวจสอบพิกัดในระบบ")
    q = st.text_input("🔍 ค้นหาด่วน (ชื่อสถานที่/ซอย):")
    
    _, current_df = load_data()
    if not current_df.empty:
        current_df['lat'] = pd.to_numeric(current_df['lat'], errors='coerce')
        current_df['lon'] = pd.to_numeric(current_df['lon'], errors='coerce')
        df = current_df.dropna(subset=['lat', 'lon'])

        if q:
            df = df[df.astype(str).apply(lambda x: x.str.contains(q, case=False)).any(axis=1)]

        if not df.empty:
            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(latitude=df['lat'].mean(), longitude=df['lon'].mean(), zoom=14),
                layers=[pdk.Layer("ScatterplotLayer", df, get_position='[lon, lat]', get_color='[0, 200, 0, 160]', get_radius=30, pickable=True)],
                tooltip={"text": "สถานที่: {place_name}\nตำแหน่ง: {location_path}"}
            ))
            st.dataframe(df[["timestamp", "place_name", "location_path", "note"]], use_container_width=True)
        else:
            st.info("ไม่พบข้อมูลพิกัด")
    else:
        st.info("ยังไม่มีข้อมูลถูกบันทึก")

with tab2:
    show_map()

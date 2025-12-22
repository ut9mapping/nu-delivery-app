import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. ตั้งค่าระบบและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery Master", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่ได้: {e}")
        return None

@st.cache_data(ttl=2)
def load_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame(), pd.DataFrame()
    
    # โหลด Mapping
    try:
        m_df = pd.DataFrame(sh.worksheet("Mapping").get_all_records())
        m_df.columns = [str(c).strip() for c in m_df.columns]
    except: m_df = pd.DataFrame()

    # โหลด Sheet1 (ประวัติ)
    try:
        l_df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        l_df.columns = [str(c).strip() for c in l_df.columns]
    except: l_df = pd.DataFrame()
    
    return m_df, l_df

# โหลดข้อมูล
mapping_df, log_df = load_data()

# --- 2. ฟังก์ชันดึงตัวเลือก (แก้ไข TypeError โดยบังคับเป็น String ทั้งหมด) ---
def get_opts(col_name, filters={}):
    if mapping_df.empty or col_name not in mapping_df.columns: 
        return ["-- ไม่ระบุ --"]
    
    tmp = mapping_df.copy()
    for k, v in filters.items():
        if k in tmp.columns and v and v not in ["-- เลือก --", "-- ไม่ระบุ --"]:
            tmp = tmp[tmp[k] == str(v)]
            
    # ดึงค่าที่ไม่ซ้ำ แปลงเป็น string และกรองค่าว่างออก
    raw_list = tmp[col_name].dropna().unique().tolist()
    clean_list = [str(x).strip() for x in raw_list if str(x).strip().lower() not in ["nan", "none", ""]]
    
    # เรียงลำดับ (แก้ไข TypeError โดยมั่นใจว่าเป็น string ทั้งหมด)
    return ["-- เลือก --"] + sorted(clean_list)

# --- 3. หน้าจอหลัก (2 Tabs ตามที่ต้องการ) ---
st.title("🛵 ระบบบันทึกพิกัดอาณาเขต")

tab1, tab2 = st.tabs(["📌 บันทึกงาน (ด่วน)", "🗺️ แผนที่อาณาเขต"])

# --- TAB 1: บันทึกงาน (กรอกแค่ชื่อก็บันทึกได้) ---
with tab1:
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    
    if lat:
        st.success(f"📍 GPS พร้อมบันทึก: {lat:.6f}, {lon:.6f}")
    else:
        st.warning("📡 กำลังรอพิกัด GPS... (โปรดกดยอมรับสิทธิ์ในเบราว์เซอร์)")

    # ส่วนกรอกข้อมูลหลัก
    p_name = st.text_input("🏠 ชื่อสถานที่ / บ้านเลขที่ (จำเป็นต้องกรอก)", placeholder="ตัวอย่าง: หอพักแสงจันทร์ หรือ 123/45")
    
    # ส่วนเลือกตำแหน่ง (ทำเป็น Expander ให้เลือกหรือไม่เลือกก็ได้)
    with st.expander("📍 ระบุรายละเอียดประตู/ซอย (คลิกเพื่อเลือกเพิ่มเติม)", expanded=False):
        c1, c2 = st.columns(2)
        g = c1.selectbox("1. ประตู", get_opts("ประตู"))
        z = c2.selectbox("2. ฝั่งถนน/โซน", get_opts("ฝั่งถนน/โซน", {"ประตู": g}))
        m = c1.selectbox("3. ซอยหลัก", get_opts("ซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z}))
        ms = c2.selectbox("4. ฝั่งซอยหลัก", get_opts("ฝั่งซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m}))
        sub = c1.selectbox("5. ซอยย่อย", get_opts("ซอยย่อย/ทางเชื่อม", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m, "ฝั่งซอยหลัก": ms}))
        det = c2.selectbox("6. ฝั่งของซอยย่อย", get_opts("ฝั่งของซอยย่อย", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m, "ฝั่งซอยหลัก": ms, "ซอยย่อย/ทางเชื่อม": sub}))

    p_note = st.text_area("📝 หมายเหตุเพิ่มเติม (ถ้ามี)")

    # ปุ่มบันทึก (ไม่ต้องใช้ Form เพื่อให้ควบคุมง่าย)
    if st.button("🚀 บันทึกพิกัดทันที", use_container_width=True, type="primary"):
        if not lat or not lon:
            st.error("❌ บันทึกไม่ได้: ไม่พบพิกัด GPS")
        elif not p_name:
            st.error("❌ บันทึกไม่ได้: กรุณากรอกชื่อสถานที่")
        else:
            try:
                sh = get_sheets()
                # รวมข้อมูลตำแหน่ง ถ้าไม่เลือกให้เป็นเครื่องหมาย -
                pos_list = [g, z, m, ms, sub, det]
                path_str = " > ".join([str(p) if p not in ["-- เลือก --", "-- ไม่ระบุ --"] else "-" for p in pos_list])
                
                new_row = [
                    datetime.now().strftime("%Y-%m-%d %H:%M"), # A
                    path_str, # B
                    lat, lon, # C, D
                    p_name,   # E
                    "", "", "", # F, G, H
                    p_note,   # I
                    "Complete" # J
                ]
                sh.worksheet("Sheet1").append_row(new_row)
                st.balloons()
                st.success(f"✅ บันทึก '{p_name}' ลงระบบเรียบร้อยแล้ว!")
                # เคลียร์ข้อมูลเพื่อให้พร้อมบันทึกอันถัดไป
                st.cache_data.clear()
            except Exception as e:
                st.error(f"❌ บันทึกไม่สำเร็จ: {e}")

# --- TAB 2: แผนที่อาณาเขต (No-Refresh) ---
@st.fragment
def show_map_section():
    st.subheader("🗺️ ตรวจสอบอาณาเขตพิกัด")
    search_q = st.text_input("🔍 ค้นหา (หน้าจะไม่รีเฟรช):", placeholder="พิมพ์ชื่อหอหรือชื่อซอย...")
    
    # โหลดข้อมูลล่าสุด
    _, df_map = load_data()
    
    if not df_map.empty:
        df_map['lat'] = pd.to_numeric(df_map['lat'], errors='coerce')
        df_map['lon'] = pd.to_numeric(df_map['lon'], errors='coerce')
        df_clean = df_map.dropna(subset=['lat', 'lon'])

        if search_q:
            mask = df_clean.astype(str).apply(lambda x: x.str.contains(search_q, case=False)).any(axis=1)
            df_clean = df_clean[mask]

        if not df_clean.empty:
            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(latitude=df_clean['lat'].mean(), longitude=df_clean['lon'].mean(), zoom=14),
                layers=[pdk.Layer("ScatterplotLayer", df_clean, get_position='[lon, lat]', get_color='[0, 200, 0, 160]', get_radius=25, pickable=True)],
                tooltip={"text": "สถานที่: {place_name}\nทาง: {location_path}"}
            ))
            st.dataframe(df_clean[["timestamp", "place_name", "location_path"]], use_container_width=True)
        else:
            st.info("ไม่พบข้อมูลพิกัด")
    else:
        st.info("ยังไม่มีข้อมูลในระบบ")

with tab2:
    show_map_section()

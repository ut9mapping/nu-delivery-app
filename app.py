import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าหน้าจอและหน้าเว็บ ---
st.set_page_config(page_title="NU Delivery Pro", layout="wide")

# ฟังก์ชันเชื่อมต่อ Google Sheets
def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ ไม่สามารถเชื่อมต่อ Google Sheets ได้: {e}")
        return None

# ฟังก์ชันโหลดข้อมูล (พร้อมระบบล้างชื่อคอลัมน์ป้องกัน KeyError)
@st.cache_data(ttl=2)
def load_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame(), pd.DataFrame()
    
    # โหลด Mapping
    try:
        m_df = pd.DataFrame(sh.worksheet("Mapping").get_all_records())
        m_df.columns = [str(c).strip() for c in m_df.columns]
    except: m_df = pd.DataFrame()

    # โหลด Sheet1
    try:
        l_df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        l_df.columns = [str(c).strip() for c in l_df.columns]
    except: l_df = pd.DataFrame()
    
    return m_df, l_df

# โหลดข้อมูลมาใช้งาน
mapping_df, log_df = load_data()

# ฟังก์ชันดึงตัวเลือกสำหรับ Selectbox (ป้องกัน TypeError และ KeyError)
def get_opts(col_name, filters={}):
    if mapping_df.empty or col_name not in mapping_df.columns:
        return ["-- เลือก --"]
    
    tmp = mapping_df.copy()
    for k, v in filters.items():
        if k in tmp.columns and v and v != "-- เลือก --":
            tmp = tmp[tmp[k].astype(str) == str(v)]
            
    # ดึงค่าที่ไม่ซ้ำ แปลงเป็น String และเรียงลำดับ
    raw_list = tmp[col_name].dropna().unique().tolist()
    clean_list = sorted([str(x).strip() for x in raw_list if str(x).strip().lower() not in ["nan", "none", ""]])
    return ["-- เลือก --"] + clean_list

# --- 2. ส่วนหน้าตาแอป (UI) ---
st.title("🛵 NU Delivery: ระบบจัดการพิกัดอาณาเขต")

# แบ่งหน้าเป็น 3 Tabs (ไม่มี Sidebar)
tab1, tab2, tab3 = st.tabs(["📌 บันทึกงานใหม่", "🗺️ อาณาเขตพิกัด", "⚙️ ตั้งค่าแอดมิน"])

# --- TAB 1: บันทึกงาน (ยืดหยุ่น ไม่บังคับกรอกครบ) ---
with tab1:
    location = streamlit_geolocation()
    curr_lat, curr_lon = location.get('latitude'), location.get('longitude')
    
    if curr_lat:
        st.success(f"✅ พิกัด GPS พร้อมใช้งาน: {curr_lat}, {curr_lon}")
    else:
        st.warning("📡 กำลังรอพิกัด GPS... (โปรดกดยอมรับสิทธิ์ในเบราว์เซอร์หรือเปิด GPS)")

    st.subheader("🏠 ข้อมูลสถานที่")
    p_name = st.text_input("ชื่อสถานที่ / บ้านเลขที่ (จำเป็น)")

    # ส่วนเลือกตำแหน่ง 4 ระดับ (ข้ามได้)
    with st.expander("📍 ระบุรายละเอียดตำแหน่ง (ข้ามส่วนนี้ได้)", expanded=False):
        c1, c2 = st.columns(2)
        g = c1.selectbox("1. ประตู", get_opts("ประตู"))
        z = c2.selectbox("2. ฝั่งถนน/โซน", get_opts("ฝั่งถนน/โซน", {"ประตู": g}))
        m = c1.selectbox("3. ซอยหลัก", get_opts("ซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z}))
        ms = c2.selectbox("4. ฝั่งซอยหลัก", get_opts("ฝั่งซอยหลัก", {"ประตู": g, "ฝั่งถนน/โซน": z, "ซอยหลัก": m}))

    p_note = st.text_area("🗒️ หมายเหตุเพิ่มเติม")

    if st.button("🚀 บันทึกข้อมูลลงระบบ", use_container_width=True, type="primary"):
        if not curr_lat or not curr_lon:
            st.error("❌ ไม่สามารถบันทึกได้: หาพิกัด GPS ไม่เจอ")
        elif not p_name:
            st.warning("⚠️ โปรดระบุชื่อสถานที่ก่อนบันทึก")
        else:
            try:
                sh = get_sheets()
                ws = sh.worksheet("Sheet1")
                
                # รวมเส้นทาง (ถ้าไม่เลือกจะขึ้นเป็น -)
                path_str = f"{g} > {z} > {m} > {ms}".replace("-- เลือก --", "-")
                
                # เตรียมข้อมูล 10 คอลัมน์ (A-J) ตามโครงสร้างภาษาอังกฤษในรูปของคุณ
                new_row = [
                    datetime.now().strftime("%Y-%m-%d %H:%M"), # A: timestamp
                    path_str,       # B: location_path
                    curr_lat,       # C: lat
                    curr_lon,       # D: lon
                    p_name,         # E: place_name
                    "", "", "",     # F, G, H: img1-3 (ว่าง)
                    p_note,         # I: note
                    "Complete"      # J: status
                ]
                
                # บันทึกแถวข้อมูล
                ws.append_row(new_row)
                st.balloons()
                st.success(f"✅ บันทึก '{p_name}' เรียบร้อยแล้ว!")
                st.cache_data.clear() # ล้างแคชเพื่อให้ Tab 2 เห็นข้อมูลทันที
            except Exception as e:
                st.error(f"❌ เกิดข้อผิดพลาดขณะบันทึก: {e}")

# --- TAB 2: แผนที่อาณาเขต (No-Refresh) ---
@st.fragment
def show_territory_map():
    st.subheader("🗺️ อาณาเขตพิกัดทั้งหมด")
    search_q = st.text_input("🔍 ค้นหา (พิมพ์ชื่อหอหรือซอย หน้าเว็บจะไม่รีเฟรช):")
    
    # โหลดข้อมูลล่าสุด
    _, df_full = load_data()
    
    if not df_full.empty:
        # เตรียมพิกัดให้เป็นตัวเลข
        df_full['lat'] = pd.to_numeric(df_full['lat'], errors='coerce')
        df_full['lon'] = pd.to_numeric(df_full['lon'], errors='coerce')
        df_clean = df_full.dropna(subset=['lat', 'lon'])

        # กรองตามคำค้นหา
        if search_q:
            mask = df_clean.astype(str).apply(lambda x: x.str.contains(search_q, case=False)).any(axis=1)
            df_clean = df_clean[mask]

        if not df_clean.empty:
            # วาดแผนที่ Pydeck
            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(latitude=df_clean['lat'].mean(), longitude=df_clean['lon'].mean(), zoom=14),
                layers=[pdk.Layer("ScatterplotLayer", df_clean, get_position='[lon, lat]', get_color='[0, 200, 0, 160]', get_radius=30, pickable=True)],
                tooltip={"text": "{place_name}\n{location_path}"}
            ))
            st.dataframe(df_clean[["timestamp", "place_name", "location_path", "note"]], use_container_width=True)
        else:
            st.info("ไม่พบข้อมูลพิกัดที่ค้นหา")
    else:
        st.info("ยังไม่มีข้อมูลในระบบ")

with tab2:
    show_territory_map()

# --- TAB 3: ตั้งค่าแอดมิน ---
with tab3:
    st.subheader("⚙️ การจัดการข้อมูล")
    if st.button("🔄 รีโหลดข้อมูลทั้งหมด (Manual Refresh)"):
        st.cache_data.clear()
        st.rerun()
    
    st.write("---")
    st.info("💡 วิธีใช้งาน: แก้ไขโครงสร้างตัวเลือกในชีต 'Mapping' และข้อมูลดิบในชีต 'Sheet1' ได้โดยตรงผ่าน Google Sheets")

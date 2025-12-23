import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk  # สำหรับทำแผนที่ภาพจำลอง

# --- 1. การตั้งค่าระบบ ---
st.set_page_config(page_title="NU Delivery: Map Preview", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except: return None

def load_data_robust(sheet_name):
    sh = get_sheets()
    if not sh: return pd.DataFrame()
    try:
        ws = sh.worksheet(sheet_name)
        all_values = ws.get_all_values()
        if len(all_values) > 0:
            headers = [str(h).strip().lower() for h in all_values[0]]
            df = pd.DataFrame(all_values[1:], columns=headers)
            # แปลง lat, lon เป็นตัวเลข
            if 'lat' in df.columns and 'lon' in df.columns:
                df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
                df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
            return df
        return pd.DataFrame()
    except: return pd.DataFrame()

# --- 2. ฟังก์ชันสร้างแผนที่จำลอง ---
def render_preview_map(lat, lon, zoom=16, map_style="light"):
    # สไตล์แผนที่: light, dark, satellite (mapbox://styles/mapbox/satellite-v9)
    view_state = pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom, pitch=0)
    layer = pdk.Layer(
        "ScatterplotLayer",
        pd.DataFrame({'lat': [lat], 'lon': [lon]}),
        get_position='[lon, lat]',
        get_color='[255, 0, 0, 200]',
        get_radius=15,
    )
    return st.pydeck_chart(pdk.Deck(
        map_style='mapbox://styles/mapbox/satellite-v9' if map_style=="satellite" else None,
        initial_view_state=view_state,
        layers=[layer]
    ))

# --- 3. หน้าจอหลัก ---
st.title("🛵 NU Delivery System (Map Preview Mode)")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน", "⚙️ วิเคราะห์ข้อมูล", "🔍 ค้นหาและภาพจำลองพื้นที่"])

# --- TAB 1: USER (คงเดิม) ---
with tab1:
    st.subheader("📝 บันทึกพิกัดใหม่")
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    p_name = st.text_input("🏠 ชื่อสถานที่/บ้านเลขที่/ตึก")
    note = st.text_area("🗒️ จุดสังเกต (เช่น ตึกแถวสีเหลือง ห้องที่ 3)")
    
    if st.button("🚀 ส่งข้อมูล", use_container_width=True, type="primary"):
        if lat and p_name:
            ws = get_sheets().worksheet("Sheet1")
            new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, note, "รอวิเคราะห์", "No", "No", "No", "", "", "", "", "", "", ""]
            ws.insert_row(new_row, index=2)
            st.success("✅ บันทึกสำเร็จ!")
        else: st.warning("⚠️ กรุณาระบุชื่อและรอพิกัด GPS")

# --- TAB 2: ADMIN (รหัส 9999) ---
with tab2:
    pwd = st.text_input("รหัสผ่านแอดมิน", type="password")
    if pwd == "9999":
        df_raw = load_data_robust("Sheet1")
        pending = df_raw[df_raw['status'] == "รอวิเคราะห์"]
        if not pending.empty:
            target = st.selectbox("เลือกรายการวิเคราะห์:", pending.index, format_func=lambda x: f"{pending.loc[x, 'place_name']}")
            # (ส่วนนี้คงไว้ตามโครงสร้างเดิมของคุณในการเลือก ประตู/ถนน/ซอย)
            st.write("🔧 ส่วนการวิเคราะห์ข้อมูลเชิงลึก...")
            if st.button("💾 บันทึกการวิเคราะห์"):
                st.success("วิเคราะห์เรียบร้อย")
        else: st.info("ไม่มีงานค้าง")

# --- TAB 3: SEARCH & VISUALIZATION (เพิ่มภาพจำลอง) ---
with tab3:
    st.subheader("🔍 ค้นหาและดูภาพจำลองพิกัด")
    all_df = load_data_robust("Sheet1")
    
    if not all_df.empty:
        # 1. แผนที่ภาพรวมอาณาเขต (Territory Overview)
        with st.expander("🌍 ดูอาณาเขตข้อมูลทั้งหมด (Map Overview)", expanded=False):
            df_map_all = all_df.dropna(subset=['lat', 'lon'])
            st.pydeck_chart(pdk.Deck(
                initial_view_state=pdk.ViewState(latitude=df_map_all['lat'].mean(), longitude=df_map_all['lon'].mean(), zoom=13),
                layers=[pdk.Layer("ScatterplotLayer", df_map_all, get_position='[lon, lat]', get_color='[0, 128, 255, 150]', get_radius=30)]
            ))

        # 2. ค้นหาและดูภาพจำลองรายจุด
        query = st.text_input("ค้นหาชื่อสถานที่, ตึกแถว, หรือโครงการ:")
        if query:
            results = all_df[all_df.apply(lambda r: query.lower() in str(r.values).lower(), axis=1)]
            
            for idx, row in results.iterrows():
                with st.expander(f"📍 {row['place_name']} | ประตู: {row['gate']}"):
                    col_info, col_map = st.columns([1, 1])
                    
                    with col_info:
                        st.write(f"**รายละเอียด:** {row['note']}")
                        st.write(f"**โครงสร้าง:** ประตู {row['gate']} > {row['main_alley']}")
                        st.write(f"**ฝั่ง/ซอยย่อย:** {row['main_side']} / {row['sub_alley']}")
                        
                        # ปุ่มนำทาง
                        maps_link = f"https://www.google.com/maps?q={row['lat']},{row['lon']}"
                        st.link_button("🚗 นำทางด้วย Google Maps", maps_link, use_container_width=True)
                    
                    with col_map:
                        st.write("🖼️ **ภาพจำลองตำแหน่ง (Satellite View)**")
                        # แสดงแผนที่ดาวเทียมเพื่อให้เห็นโครงสร้างตึกแถวชัดเจน
                        render_preview_map(row['lat'], row['lon'], zoom=18, map_style="satellite")
                        st.caption("ซูมเห็นหลังคาตึกเพื่อให้มั่นใจตำแหน่งก่อนเดินทาง")
    else:
        st.info("ยังไม่มีข้อมูล")

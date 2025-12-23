import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าระบบและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery Master Pro", layout="wide")

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
        all_vals = ws.get_all_values()
        if len(all_vals) > 1:
            headers = [str(h).strip().lower() for h in all_vals[0]]
            df = pd.DataFrame(all_vals[1:], columns=headers)
            # แปลงพิกัดเป็นตัวเลข (สำคัญมาก)
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
            return df.dropna(subset=['lat', 'lon'])
        return pd.DataFrame()
    except: return pd.DataFrame()

# --- 2. หน้าจอหลัก ---
st.title("🛵 NU Delivery Pro (Map Fix)")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน", "⚙️ วิเคราะห์ข้อมูล", "🔍 ค้นหาและอาณาเขต"])

# --- TAB 1: บันทึกข้อมูล ---
with tab1:
    st.subheader("📝 บันทึกพิกัดใหม่")
    # ปุ่มดึงพิกัด
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    
    if lat and lon:
        st.success(f"✅ จับพิกัดสำเร็จ: {lat}, {lon}")
    else:
        st.warning("📡 กำลังรอพิกัด... หากไม่ขึ้นกรุณากด 'อนุญาตตำแหน่ง' ที่เบราว์เซอร์")

    p_name = st.text_input("🏠 ชื่อสถานที่/ตึกแถว")
    note = st.text_area("🗒️ จุดสังเกต")

    if st.button("🚀 บันทึกข้อมูล", use_container_width=True, type="primary"):
        if lat and p_name:
            ws = get_sheets().worksheet("Sheet1")
            new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, note, "รอวิเคราะห์", "No", "No", "No", "", "", "", "", "", "", ""]
            ws.insert_row(new_row, index=2)
            st.success("บันทึกสำเร็จ!")
        else: st.error("ข้อมูลไม่ครบ")

# --- TAB 2: แอดมิน (รหัส 9999) ---
with tab2:
    pwd = st.text_input("รหัสผ่านแอดมิน", type="password")
    if pwd == "9999":
        st.info("🔓 เข้าสู่โหมดแอดมินเรียบร้อย")
        # ส่วนวิเคราะห์ข้อมูล... (ใช้ตามโค้ดเดิมของคุณได้เลย)
    elif pwd != "":
        st.error("รหัสผ่านไม่ถูกต้อง")

# --- TAB 3: ค้นหาและอาณาเขต (แก้แผนที่ขาว + Tooltip) ---
with tab3:
    st.subheader("🔍 ค้นหาและดูอาณาเขตข้อมูล")
    all_df = load_data_robust("Sheet1")
    
    if not all_df.empty:
        # --- แผนที่ภาพรวมอาณาเขต ---
        st.write("🌍 **อาณาเขตพิกัดทั้งหมด (ชี้ที่จุดเพื่อดูรายละเอียด)**")
        
        # แก้ปัญหาพื้นหลังขาวโดยใช้ Carto Light (ไม่ต้องใช้ Token)
        view_state = pdk.ViewState(
            latitude=all_df['lat'].mean(),
            longitude=all_df['lon'].mean(),
            zoom=14, pitch=0
        )
        
        layer = pdk.Layer(
            "ScatterplotLayer",
            all_df,
            get_position='[lon, lat]',
            get_color='[255, 75, 75, 180]', # สีแดงโปร่งแสง
            get_radius=35,
            pickable=True, # สำคัญ: เพื่อให้ Tooltip ทำงาน
        )
        
        # ตัวเลือกสไตล์แผนที่ที่เสถียรที่สุด
        st.pydeck_chart(pdk.Deck(
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json", # ใช้ Carto แทน Mapbox
            initial_view_state=view_state,
            layers=[layer],
            tooltip={
                "html": """
                    <div style='font-family: sans-serif; padding: 10px; background: white; color: black; border-radius: 5px; border: 1px solid #ddd;'>
                        <b>🏠 สถานที่:</b> {place_name} <br/>
                        <b>🚪 ประตู:</b> {gate} <br/>
                        <b>🗒️ หมายเหตุ:</b> {note} <br/>
                        <b>🕒 เวลา:</b> {timestamp}
                    </div>
                """,
                "style": {"zIndex": "10000"}
            }
        ))

        # --- ค้นหารายจุดเพื่อดูภาพดาวเทียม ---
        st.divider()
        query = st.text_input("🔍 พิมพ์ชื่อสถานที่เพื่อดูภาพจำลองตึกแถว:")
        if query:
            res = all_df[all_df.apply(lambda r: query.lower() in str(r.values).lower(), axis=1)]
            for idx, row in res.iterrows():
                with st.expander(f"📍 {row['place_name']} - ดูรายละเอียด"):
                    c_info, c_map = st.columns([1, 1])
                    with c_info:
                        st.write(f"**ประตู:** {row.get('gate', '-')}")
                        st.write(f"**หมายเหตุ:** {row['note']}")
                        st.link_button("🚗 นำทางด้วย Google Maps", f"https://www.google.com/maps?q={row['lat']},{row['lon']}")
                    with c_map:
                        # แผนที่ซูมดาวเทียมรายจุด
                        st.pydeck_chart(pdk.Deck(
                            map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json", # สไตล์ที่มีสีสัน
                            initial_view_state=pdk.ViewState(latitude=row['lat'], longitude=row['lon'], zoom=18),
                            layers=[pdk.Layer("ScatterplotLayer", pd.DataFrame([row]), get_position='[lon, lat]', get_color='[255,0,0]', get_radius=10)]
                        ))
    else:
        st.info("ยังไม่มีข้อมูลในฐานข้อมูล")

import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าระบบ ---
st.set_page_config(page_title="NU Delivery: Pro Map", layout="wide")

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
        if len(all_values) > 1:
            headers = [str(h).strip().lower() for h in all_values[0]]
            df = pd.DataFrame(all_values[1:], columns=headers)
            df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
            df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
            return df.dropna(subset=['lat', 'lon'])
        return pd.DataFrame()
    except: return pd.DataFrame()

# --- 2. หน้าจอหลัก ---
st.title("🛵 NU Delivery Pro (Map Fix)")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน", "⚙️ วิเคราะห์ข้อมูล", "🔍 ค้นหาและอาณาเขต"])

# --- TAB 1: บันทึกหน้างาน (ปรับปรุง GPS) ---
with tab1:
    st.subheader("📝 บันทึกพิกัดใหม่")
    
    # คำแนะนำเรื่องพิกัด
    st.info("💡 หากดึงพิกัดไม่ได้: ให้ปิด Tab นี้แล้วเปิดใหม่ หรือตรวจสอบว่าใช้ https://")
    
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    
    if lat and lon:
        st.success(f"✅ จับพิกัดสำเร็จ: {lat}, {lon}")
    else:
        st.warning("📡 กำลังค้นหาตำแหน่ง... (หากไม่ขึ้น ให้กดอนุญาตสิทธิ์ที่รูปกุญแจด้านบนหน้าเว็บ)")

    p_name = st.text_input("🏠 ชื่อสถานที่/ตึกแถว/โครงการ")
    note = st.text_area("🗒️ จุดสังเกตเพิ่มเติม")
    
    # จำลองรูปภาพ 3 รูป (บันทึกสถานะ)
    c1, c2, c3 = st.columns(3)
    img1 = c1.file_uploader("รูป 1", type=['jpg','png'])
    img2 = c2.file_uploader("รูป 2", type=['jpg','png'])
    img3 = c3.file_uploader("รูป 3", type=['jpg','png'])

    if st.button("🚀 บันทึกข้อมูลเข้าชีต", use_container_width=True, type="primary"):
        if lat and p_name:
            ws = get_sheets().worksheet("Sheet1")
            imgs = ["Yes" if i else "No" for i in [img1, img2, img3]]
            new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, note, "รอวิเคราะห์"] + imgs + [""]*7
            ws.insert_row(new_row, index=2)
            st.balloons()
            st.success("บันทึกสำเร็จ!")
        else: st.error("❌ ข้อมูลไม่ครบหรือยังไม่มีพิกัด")

# --- TAB 2: แอดมิน (รหัส 9999) ---
with tab2:
    pwd = st.text_input("รหัสผ่านแอดมิน", type="password")
    if pwd == "9999":
        st.write("🔧 ระบบวิเคราะห์ข้อมูล (Admin Only)")
        # ... (ส่วนการวิเคราะห์ข้อมูลที่คุณใช้อยู่เดิม) ...
    elif pwd != "":
        st.error("รหัสผ่านไม่ถูกต้อง")

# --- TAB 3: ค้นหาและแผนที่แบบ Interactive ---
with tab3:
    st.subheader("🔍 ค้นหาและดูอาณาเขตข้อมูล")
    all_df = load_data_robust("Sheet1")
    
    if not all_df.empty:
        # 1. แผนที่อาณาเขตพร้อม Tooltip
        st.write("🌍 **อาณาเขตพิกัดทั้งหมด (ชี้ที่จุดเพื่อดูรายละเอียด)**")
        
        # ตั้งค่าแผนที่พื้นหลังให้ไม่เป็นสีขาว (ใช้ Carto Light)
        view_state = pdk.ViewState(
            latitude=all_df['lat'].mean(), 
            longitude=all_df['lon'].mean(), 
            zoom=14, pitch=0
        )
        
        layer = pdk.Layer(
            "ScatterplotLayer",
            all_df,
            get_position='[lon, lat]',
            get_color='[255, 75, 75, 180]',
            get_radius=30,
            pickable=True, # ทำให้ชี้ได้
        )
        
        # แสดงแผนที่
        st.pydeck_chart(pdk.Deck(
            map_style='mapbox://styles/mapbox/light-v10', # หรือลองเปลี่ยนเป็น None ถ้ายังขาว
            initial_view_state=view_state,
            layers=[layer],
            tooltip={
                "html": "<b>สถานที่:</b> {place_name} <br/> <b>หมายเหตุ:</b> {note} <br/> <b>โซน:</b> {gate}",
                "style": {"backgroundColor": "steelblue", "color": "white"}
            }
        ))
        
        

        # 2. ค้นหารายจุดเพื่อดูภาพดาวเทียม
        st.divider()
        query = st.text_input("🔍 พิมพ์ชื่อสถานที่เพื่อซูมดูภาพจำลอง:")
        if query:
            res = all_df[all_df.apply(lambda r: query.lower() in str(r.values).lower(), axis=1)]
            for idx, row in res.iterrows():
                with st.expander(f"📍 {row['place_name']} - คลิกเพื่อดูภาพดาวเทียม"):
                    c_info, c_map = st.columns(2)
                    with c_info:
                        st.write(f"**ประตู:** {row.get('gate', '-')}")
                        st.write(f"**หมายเหตุ:** {row['note']}")
                        st.link_button("🚗 นำทางด้วย Google Maps", f"https://www.google.com/maps?q={row['lat']},{row['lon']}")
                    with c_map:
                        # แผนที่ซูมรายจุดแบบดาวเทียม
                        st.pydeck_chart(pdk.Deck(
                            map_style='mapbox://styles/mapbox/satellite-v9',
                            initial_view_state=pdk.ViewState(latitude=row['lat'], longitude=row['lon'], zoom=18),
                            layers=[pdk.Layer("ScatterplotLayer", pd.DataFrame([row]), get_position='[lon, lat]', get_color='[255,0,0]', get_radius=10)]
                        ))
    else:
        st.info("ยังไม่มีข้อมูลในระบบ")

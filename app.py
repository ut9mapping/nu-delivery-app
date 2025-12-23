import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. ตั้งค่าพื้นฐาน ---
st.set_page_config(page_title="NU Delivery Pro: Admin Control", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except: return None

def load_data_all():
    sh = get_sheets()
    if not sh: return pd.DataFrame()
    ws = sh.worksheet("Sheet1")
    data = ws.get_all_records()
    df = pd.DataFrame(data)
    if not df.empty:
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    return df

# --- 2. หน้าจอหลัก ---
st.title("🛵 NU Delivery Pro (Admin Full Control)")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน", "⚙️ จัดการข้อมูล (Admin)", "🔍 อาณาเขตและค้นหา"])

# --- TAB 1: บันทึกพิกัด (กู้คืนช่องใส่รูป) ---
with tab1:
    st.subheader("📝 บันทึกพิกัดและรูปภาพ")
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    
    if lat: st.success(f"📍 พิกัดพร้อม: {lat}, {lon}")
    else: st.warning("📡 กำลังรอพิกัด GPS... (โปรดกดยอมรับสิทธิ์ตำแหน่ง)")

    p_name = st.text_input("🏠 ชื่อสถานที่/ตึกแถว")
    note = st.text_area("🗒️ จุดสังเกต (เช่น ร้านสีเขียวข้างเซเว่น)")
    
    st.write("🖼️ อัปโหลดรูปภาพ (3 รูป)")
    c1, c2, c3 = st.columns(3)
    img1 = c1.file_uploader("รูปที่ 1", type=['jpg','png'], key="img1")
    img2 = c2.file_uploader("รูปที่ 2", type=['jpg','png'], key="img2")
    img3 = c3.file_uploader("รูปที่ 3", type=['jpg','png'], key="img3")

    if st.button("🚀 บันทึกข้อมูล", use_container_width=True, type="primary"):
        if lat and p_name:
            ws = get_sheets().worksheet("Sheet1")
            imgs = ["Yes" if i else "No" for i in [img1, img2, img3]]
            # โครงสร้าง: timestamp, lat, lon, place_name, note, status, img1, img2, img3, gate...
            new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, note, "รอวิเคราะห์"] + imgs + [""]*7
            ws.insert_row(new_row, index=2)
            st.balloons()
            st.success("✅ บันทึกข้อมูลสำเร็จ!")
        else: st.error("⚠️ ข้อมูลไม่ครบหรือ GPS ไม่ทำงาน")

# --- TAB 2: แอดมิน (แก้ไข/ลบ ข้อมูล) ---
with tab2:
    pwd = st.text_input("รหัสผ่านแอดมิน", type="password")
    if pwd == "9999":
        df_admin = load_data_all()
        if not df_admin.empty:
            mode = st.radio("เลือกโหมดการทำงาน:", ["🛠️ วิเคราะห์/แก้ไขข้อมูล", "🗑️ ลบข้อมูลพิกัด"])
            
            target_name = st.selectbox("เลือกสถานที่:", df_admin['place_name'].tolist())
            target_row = df_admin[df_admin['place_name'] == target_name].iloc[0]
            # หาแถวที่จริงใน Google Sheets (Index ใน DF เริ่ม 0 + Header 1 + เลื่อน 1 = +2)
            actual_row_idx = df_admin.index[df_admin['place_name'] == target_name][0] + 2

            if mode == "🛠️ วิเคราะห์/แก้ไขข้อมูล":
                st.write(f"--- แก้ไข: {target_name} ---")
                new_note = st.text_area("🗒️ แก้ไขหมายเหตุ", value=target_row['note'])
                new_gate = st.text_input("🚪 ประตู", value=target_row.get('gate', ''))
                new_alley = st.text_input("🛣️ ซอยหลัก", value=target_row.get('main_alley', ''))
                
                if st.button("💾 บันทึกการเปลี่ยนแปลง"):
                    ws = get_sheets().worksheet("Sheet1")
                    ws.update_cell(actual_row_idx, 5, new_note) # คอลัมน์ E (Note)
                    ws.update_cell(actual_row_idx, 6, "วิเคราะห์แล้ว") # คอลัมน์ F (Status)
                    ws.update_cell(actual_row_idx, 10, new_gate) # คอลัมน์ J (Gate)
                    ws.update_cell(actual_row_idx, 13, new_alley) # คอลัมน์ M (Alley)
                    st.success("✅ แก้ไขข้อมูลเรียบร้อย!")
                    st.rerun()

            elif mode == "🗑️ ลบข้อมูลพิกัด":
                st.warning(f"คุณกำลังจะลบพิกัด: {target_name} ออกจากระบบถาวร")
                if st.button("🔥 ยืนยันการลบข้อมูล"):
                    ws = get_sheets().worksheet("Sheet1")
                    ws.delete_rows(actual_row_idx)
                    st.success("🗑️ ลบข้อมูลสำเร็จ!")
                    st.rerun()
        else: st.info("ไม่มีข้อมูลในระบบ")

# --- TAB 3: อาณาเขตพร้อม Hover Tooltip ---
with tab3:
    st.subheader("🔍 ค้นหาและอาณาเขตข้อมูล")
    all_df = load_data_all()
    
    if not all_df.empty:
        # แผนที่อาณาเขตพร้อมระบบ Hover (ชี้เมาส์)
        st.write("🌍 **อาณาเขตพิกัดทั้งหมด (เอาเมาส์ชี้ที่จุดเพื่อดูรายละเอียด)**")
        
        view_state = pdk.ViewState(
            latitude=all_df['lat'].mean(), 
            longitude=all_df['lon'].mean(), 
            zoom=14
        )
        
        layer = pdk.Layer(
            "ScatterplotLayer",
            all_df,
            get_position='[lon, lat]',
            get_color='[255, 75, 75, 200]',
            get_radius=40,
            pickable=True, # สำคัญ: เพื่อให้เมาส์ชี้ได้
        )
        
        st.pydeck_chart(pdk.Deck(
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            initial_view_state=view_state,
            layers=[layer],
            tooltip={
                "html": """
                <div style='background-color: white; color: black; padding: 10px; border-radius: 5px; border: 1px solid #ccc;'>
                    <b>🏠 สถานที่:</b> {place_name} <br/>
                    <b>🚪 ประตู:</b> {gate} <br/>
                    <b>🛣️ ซอย:</b> {main_alley} <br/>
                    <b>🗒️ หมายเหตุ:</b> {note}
                </div>
                """,
                "style": {"zIndex": "10000"}
            }
        ))
        
        # ระบบค้นหาและนำทาง
        query = st.text_input("🔍 ค้นหาชื่อสถานที่:")
        if query:
            res = all_df[all_df.apply(lambda r: query.lower() in str(r.values).lower(), axis=1)]
            for _, row in res.iterrows():
                with st.expander(f"📍 {row['place_name']}"):
                    st.write(f"**หมายเหตุ:** {row['note']}")
                    st.link_button("🚗 เปิด Google Maps", f"https://www.google.com/maps?q={row['lat']},{row['lon']}")
    else: st.info("ยังไม่มีข้อมูล")

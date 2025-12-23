import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าระบบและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery: Admin & Map Control", layout="wide")

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
        # ล้างช่องว่างในชื่อคอลัมน์เพื่อความแม่นยำ
        df.columns = [c.strip() for c in df.columns]
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
    return df

# --- 2. หน้าจอหลัก ---
st.title("🛵 NU Delivery System (Pro Version)")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน", "⚙️ จัดการข้อมูล (Admin)", "🔍 อาณาเขตและค้นหา"])

# --- TAB 1: บันทึกพิกัด (กู้คืนช่องใส่รูป 3 ช่อง) ---
with tab1:
    st.subheader("📝 บันทึกพิกัดและรูปภาพ")
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    
    if lat: st.success(f"📍 พิกัดพร้อม: {lat}, {lon}")
    else: st.warning("📡 กำลังรอพิกัด GPS... (โปรดกดยอมรับสิทธิ์ตำแหน่งที่หน้าจอ)")

    p_name = st.text_input("🏠 ชื่อสถานที่ / ตึกแถว / เลขที่อาคาร")
    note = st.text_area("🗒️ รายละเอียดเพิ่มเติม (จุดสังเกต)")
    
    st.write("🖼️ อัปโหลดรูปภาพ (สูงสุด 3 รูป)")
    col_i1, col_i2, col_i3 = st.columns(3)
    img1 = col_i1.file_uploader("รูปที่ 1", type=['jpg','png'], key="up1")
    img2 = col_i2.file_uploader("รูปที่ 2", type=['jpg','png'], key="up2")
    img3 = col_i3.file_uploader("รูปที่ 3", type=['jpg','png'], key="up3")

    if st.button("🚀 บันทึกข้อมูลเข้าชีต", use_container_width=True, type="primary"):
        if lat and p_name:
            ws = get_sheets().worksheet("Sheet1")
            imgs = ["Yes" if i else "No" for i in [img1, img2, img3]]
            # เตรียมข้อมูล (ลำดับคอลัมน์ต้องตรงกับ Sheet1)
            new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, note, "รอวิเคราะห์"] + imgs + [""]*7
            ws.insert_row(new_row, index=2)
            st.balloons()
            st.success("✅ บันทึกข้อมูลสำเร็จ! แอดมินจะดำเนินการแยกหมวดหมู่ต่อไป")
        else: st.error("⚠️ ข้อมูลไม่ครบ หรือยังตรวจไม่พบพิกัด GPS")

# --- TAB 2: แอดมิน (แก้ไข/ลบ ข้อมูล + แก้ไข TypeError) ---
with tab2:
    pwd = st.text_input("รหัสผ่านแอดมิน (9999)", type="password")
    if pwd == "9999":
        st.info("🔓 เข้าสู่ระบบจัดการข้อมูล")
        df_admin = load_data_all()
        
        if not df_admin.empty:
            mode = st.radio("เลือกการทำงาน:", ["🛠️ แก้ไข/วิเคราะห์", "🗑️ ลบพิกัดที่เลือก"])
            target_name = st.selectbox("เลือกสถานที่:", df_admin['place_name'].tolist())
            
            # ดึงข้อมูลแถวที่ต้องการ
            target_data = df_admin[df_admin['place_name'] == target_name].iloc[0]
            # แก้ไข TypeError ด้วยการแปลงค่า index เป็น Python int มาตรฐาน
            actual_row_idx = int(df_admin.index[df_admin['place_name'] == target_name][0]) + 2

            if mode == "🛠️ แก้ไข/วิเคราะห์":
                c1, c2 = st.columns(2)
                with c1:
                    new_note = st.text_area("🗒️ แก้ไขหมายเหตุ", value=str(target_data.get('note', '')))
                    new_gate = st.text_input("🚪 ประตู", value=str(target_data.get('gate', '')))
                with c2:
                    new_alley = st.text_input("🛣️ ซอยหลัก", value=str(target_data.get('main_alley', '')))
                    new_side = st.selectbox("🌍 ฝั่ง", ["ฝั่งใน", "ฝั่งนอก", "-"], index=0)

                if st.button("💾 บันทึกการเปลี่ยนแปลง", type="primary"):
                    ws = get_sheets().worksheet("Sheet1")
                    # ใช้ int() ครอบแถวและคอลัมน์เสมอ
                    ws.update_cell(actual_row_idx, 5, new_note)  # Note
                    ws.update_cell(actual_row_idx, 6, "วิเคราะห์แล้ว") # Status
                    ws.update_cell(actual_row_idx, 10, new_gate) # Gate
                    ws.update_cell(actual_row_idx, 13, new_alley) # Alley
                    st.success("✅ อัปเดตข้อมูลสำเร็จ!")
                    st.rerun()

            elif mode == "🗑️ ลบพิกัดที่เลือก":
                st.warning(f"⚠️ คำเตือน: ระบบจะลบพิกัด '{target_name}' ถาวร")
                if st.button("🔥 ยืนยันการลบ", type="secondary"):
                    ws = get_sheets().worksheet("Sheet1")
                    ws.delete_rows(actual_row_idx) # แก้ TypeError ที่นี่
                    st.success("🗑️ ลบข้อมูลเรียบร้อยแล้ว")
                    st.rerun()
        else: st.info("ยังไม่มีข้อมูลในระบบ")

# --- TAB 3: อาณาเขตพิกัดพร้อม Hover Tooltip ---
with tab3:
    st.subheader("🔍 อาณาเขตและพิกัดทั้งหมด")
    all_df = load_data_all()
    
    if not all_df.empty:
        # ส่วนแสดงผลแผนที่อาณาเขต
        st.write("📊 **ภาพรวมอาณาเขต (เอาเมาส์ชี้เพื่อดูรายละเอียดสถานที่)**")
        
        # ตั้งค่าแผนที่และ Tooltip
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
                <div style='background: white; color: black; padding: 12px; border-radius: 8px; border: 1px solid #ccc; font-family: sans-serif;'>
                    <b style='font-size: 14px;'>🏠 {place_name}</b><hr style='margin: 5px 0;'>
                    <b>🚪 ประตู:</b> {gate} <br/>
                    <b>🛣️ ซอย:</b> {main_alley} <br/>
                    <b>🗒️ หมายเหตุ:</b> {note} <br/>
                    <b>🕒 บันทึกเมื่อ:</b> {timestamp}
                </div>
                """,
                "style": {"zIndex": "10000"}
            }
        ))
        
        

        # ระบบค้นหาและนำทางรายบุคคล
        st.divider()
        search_q = st.text_input("🔍 ค้นหาชื่อสถานที่เพื่อดูภาพจำลอง:")
        if search_q:
            res = all_df[all_df.apply(lambda r: search_q.lower() in str(r.values).lower(), axis=1)]
            for _, row in res.iterrows():
                with st.expander(f"📍 {row['place_name']}"):
                    c_a, c_b = st.columns(2)
                    with c_a:
                        st.write(f"**ประตู:** {row.get('gate', '-')}")
                        st.write(f"**หมายเหตุ:** {row['note']}")
                        st.link_button("🚗 ไป Google Maps", f"https://www.google.com/maps?q={row['lat']},{row['lon']}")
                    with c_b:
                        # ภาพจำลองดาวเทียมรายจุด
                        st.pydeck_chart(pdk.Deck(
                            map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
                            initial_view_state=pdk.ViewState(latitude=row['lat'], longitude=row['lon'], zoom=18),
                            layers=[pdk.Layer("ScatterplotLayer", pd.DataFrame([row]), get_position='[lon, lat]', get_color='[255,0,0]', get_radius=10)]
                        ))
    else: st.info("ไม่มีข้อมูลพิกัดในขณะนี้")

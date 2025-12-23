import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime

# --- 1. การตั้งค่าระบบและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery: 3-Image Support", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อมต่อไม่ได้: {e}")
        return None

def load_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame()
    ws = sh.worksheet("Sheet1")
    # ดึงข้อมูลทั้งหมดมาเป็น DataFrame
    return pd.DataFrame(ws.get_all_records())

# --- 2. หน้าจอหลัก ---
st.title("🛵 NU Delivery: ระบบบันทึกพิกัดและรูปภาพ")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน", "⚙️ แอดมินวิเคราะห์", "🔍 ค้นหาและนำทาง"])

# --- TAB 1: บันทึกข้อมูล (รับ 3 รูป) ---
with tab1:
    st.subheader("📸 ลงทะเบียนพิกัดและถ่ายรูป (3 รูป)")
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    
    if lat: st.success(f"📍 GPS พร้อมบันทึก: {lat}, {lon}")
    else: st.info("📡 กำลังรอพิกัด GPS...")

    p_name = st.text_input("🏠 ชื่อสถานที่ / จุดสังเกต")
    note = st.text_area("🗒️ รายละเอียดเพิ่มเติม")
    
    st.write("---")
    st.write("🖼️ อัปโหลดรูปภาพสถานที่ (สูงสุด 3 รูป)")
    col_img1, col_img2, col_img3 = st.columns(3)
    with col_img1:
        img1 = st.file_uploader("รูปที่ 1", type=['jpg', 'jpeg', 'png'], key="img1")
    with col_img2:
        img2 = st.file_uploader("รูปที่ 2", type=['jpg', 'jpeg', 'png'], key="img2")
    with col_img3:
        img3 = st.file_uploader("รูปที่ 3", type=['jpg', 'jpeg', 'png'], key="img3")

    if st.button("🚀 บันทึกข้อมูลทั้งหมด", use_container_width=True, type="primary"):
        if lat and p_name:
            # ตรวจสอบสถานะรูปภาพ
            s1 = "Yes" if img1 else "No"
            s2 = "Yes" if img2 else "No"
            s3 = "Yes" if img3 else "No"
            
            # เตรียมแถวข้อมูล (12 คอลัมน์)
            # timestamp(A) | lat(B) | lon(C) | place_name(D) | note(E) | status(F) | gate(G) | alley(H) | zone(I) | img1(J) | img2(K) | img3(L)
            new_row = [
                datetime.now().strftime("%Y-%m-%d %H:%M"), 
                lat, lon, p_name, note, 
                "รอวิเคราะห์", "", "", "", 
                s1, s2, s3
            ]
            
            try:
                get_sheets().worksheet("Sheet1").insert_row(new_row, index=2)
                st.balloons()
                st.success("✅ บันทึกสำเร็จ! ส่งข้อมูลให้แอดมินแล้ว")
            except Exception as e:
                st.error(f"เกิดข้อผิดพลาด: {e}")
        else:
            st.warning("⚠️ กรุณากรอกชื่อสถานที่และเปิด GPS")

# --- TAB 2: แอดมินวิเคราะห์ ---
with tab2:
    st.subheader("แอดมิน: แยกหมวดหมู่ ประตู/ซอย/โซน")
    df = load_data()
    if not df.empty:
        pending = df[df['status'] == "รอวิเคราะห์"]
        if not pending.empty:
            target = st.selectbox("เลือกรายการ:", pending.index, format_func=lambda x: f"{pending.loc[x, 'place_name']}")
            
            c1, c2 = st.columns(2)
            with c1:
                st.info(f"📍 {pending.loc[target, 'place_name']}")
                st.write(f"🖼️ รูปภาพที่มี: {pending.loc[target, 'img1']}, {pending.loc[target, 'img2']}, {pending.loc[target, 'img3']}")
            with c2:
                adm_gate = st.text_input("🚪 ประตู")
                adm_alley = st.text_input("🛣️ ซอย")
                adm_zone = st.selectbox("🌍 โซน", ["ฝั่งใน", "ฝั่งนอก", "หอพัก"])
                
            if st.button("💾 บันทึกการวิเคราะห์"):
                ws = get_sheets().worksheet("Sheet1")
                row_idx = int(target) + 2
                ws.update_cell(row_idx, 6, "วิเคราะห์แล้ว")
                ws.update_cell(row_idx, 7, adm_gate)
                ws.update_cell(row_idx, 8, adm_alley)
                ws.update_cell(row_idx, 9, adm_zone)
                st.success("อัปเดตเรียบร้อย!")
                st.rerun()
        else: st.info("ไม่มีงานค้าง")

# --- TAB 3: ค้นหาและนำทาง ---
with tab3:
    st.subheader("🔍 ค้นหาและนำทาง")
    all_data = load_data()
    search = st.text_input("พิมพ์ชื่อสถานที่ หรือ ซอย:")
    
    if not all_data.empty:
        mask = all_data.apply(lambda r: search.lower() in str(r.values).lower(), axis=1)
        res = all_data[mask]
        
        for idx, row in res.iterrows():
            with st.expander(f"📍 {row['place_name']} ({row['gate']} {row['alley']})"):
                col_a, col_b = st.columns([3, 1])
                with col_a:
                    st.write(f"**โซน:** {row['zone']} | **หมายเหตุ:** {row['note']}")
                    st.write(f"🖼️ รูปภาพในระบบ: 1:[{row['img1']}] 2:[{row['img2']}] 3:[{row['img3']}]")
                with col_b:
                    maps_url = f"https://www.google.com/maps/search/?api=1&query={row['lat']},{row['lon']}"
                    st.link_button("🚗 นำทาง", maps_url, type="primary")

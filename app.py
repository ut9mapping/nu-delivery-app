import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime

# --- 1. การตั้งค่าระบบและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery Master V4", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่ได้: {e}")
        return None

def load_data_robust(sheet_name):
    sh = get_sheets()
    if not sh: return pd.DataFrame()
    try:
        ws = sh.worksheet(sheet_name)
        all_values = ws.get_all_values()
        if len(all_values) > 0:
            headers = [str(h).strip().lower() for h in all_values[0]]
            # จัดการชื่อคอลัมน์ซ้ำ
            clean_headers = []
            for i, h in enumerate(headers):
                if h == "" or h in clean_headers:
                    clean_headers.append(f"{h if h != '' else 'col'}_{i}")
                else:
                    clean_headers.append(h)
            return pd.DataFrame(all_values[1:], columns=clean_headers)
        return pd.DataFrame()
    except: return pd.DataFrame()

def get_options(df, target_col, filters={}):
    if df.empty or target_col not in df.columns: return ["-- ไม่มีข้อมูล --"]
    temp_df = df.copy()
    for col, val in filters.items():
        if val and col in temp_df.columns:
            temp_df = temp_df[temp_df[col] == val]
    options = sorted(temp_df[target_col].unique().tolist())
    return [str(opt).strip() for opt in options if str(opt).strip() != ""]

# --- 2. หน้าจอหลัก ---
st.title("🛵 NU Delivery System")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน (User)", "⚙️ วิเคราะห์ข้อมูล (Admin)", "🔍 ค้นหา/นำทาง"])

# --- TAB 1: USER (แก้ปัญหา GPS) ---
with tab1:
    st.subheader("📝 บันทึกพิกัดใหม่")
    
    # คำแนะนำเรื่อง GPS
    with st.expander("🌐 วิธีแก้ปัญหาหากดึงพิกัดไม่ได้"):
        st.write("1. ตรวจสอบว่าใช้ลิงก์ **https://** (ต้องมี S)")
        st.write("2. กด 'อนุญาต' (Allow) เมื่อเบราว์เซอร์ถามหาตำแหน่ง")
        st.write("3. หากยังไม่ได้ ให้ลองปิดแอปแล้วเปิดใหม่ใน Chrome หรือ Safari")

    # เรียกใช้ GPS
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    
    if lat and lon:
        st.success(f"✅ จับพิกัดสำเร็จ: {lat}, {lon}")
    else:
        st.warning("📡 กำลังรอพิกัด GPS... (หากค้างนานให้ลองรีเฟรชหน้าเว็บ)")
        # ตัวเลือกสำรอง: กรอกเองถ้าจำเป็น (Optional)
        if st.checkbox("กรอกพิกัดเอง (กรณี GPS เสีย)"):
            lat = st.number_input("Latitude", format="%.6f")
            lon = st.number_input("Longitude", format="%.6f")

    p_name = st.text_input("🏠 ชื่อสถานที่/บ้านเลขที่")
    note = st.text_area("🗒️ หมายเหตุ/จุดสังเกต")
    
    st.write("🖼️ รูปภาพ (3 รูป)")
    c1, c2, c3 = st.columns(3)
    img1 = c1.file_uploader("รูปที่ 1", type=['jpg','png'], key="u1")
    img2 = c2.file_uploader("รูปที่ 2", type=['jpg','png'], key="u2")
    img3 = c3.file_uploader("รูปที่ 3", type=['jpg','png'], key="u3")

    if st.button("🚀 ส่งข้อมูล", use_container_width=True, type="primary"):
        if lat and p_name:
            try:
                sh = get_sheets()
                ws = sh.worksheet("Sheet1")
                imgs = ["Yes" if i else "No" for i in [img1, img2, img3]]
                new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, note, "รอวิเคราะห์"] + imgs + [""]*7
                ws.insert_row(new_row, index=2)
                st.balloons()
                st.success("✅ ส่งข้อมูลสำเร็จ!")
            except Exception as e:
                st.error(f"ผิดพลาด: {e}")
        else: st.warning("⚠️ กรุณาระบุชื่อและรอพิกัด")

# --- TAB 2: ADMIN (ใส่รหัสผ่าน 9999) ---
with tab2:
    st.subheader("⚙️ เฉพาะเจ้าหน้าที่แอดมิน")
    
    # ระบบล็อกรหัสผ่าน
    admin_password = st.text_input("กรุณากรอกรหัสผ่านเพื่อเข้าใช้งาน", type="password")
    
    if admin_password == "9999":
        st.success("🔓 ปลดล็อกระบบแอดมินแล้ว")
        st.divider()
        
        df_raw = load_data_robust("Sheet1")
        df_map = load_data_robust("Mapping")
        
        if 'status' in df_raw.columns:
            pending = df_raw[df_raw['status'] == "รอวิเคราะห์"]
            if not pending.empty:
                target_idx = st.selectbox("เลือกรายการวิเคราะห์:", pending.index, 
                                         format_func=lambda x: f"{pending.loc[x, 'place_name']}")
                
                st.write(f"🔍 วิเคราะห์: **{pending.loc[target_idx, 'place_name']}**")
                
                col1, col2 = st.columns(2)
                with col1:
                    g = st.selectbox("1. ประตู", get_options(df_map, 'gate'))
                    ma = st.selectbox("2. ซอยหลัก", get_options(df_map, 'main_alley', {'gate': g}))
                with col2:
                    ms = st.selectbox("3. ฝั่งซอยหลัก", get_options(df_map, 'main_side', {'gate': g, 'main_alley': ma}))
                    sa = st.selectbox("4. ซอยย่อย", get_options(df_map, 'sub_alley', {'gate': g, 'main_alley': ma}))

                if st.button("💾 บันทึกการวิเคราะห์"):
                    sh = get_sheets()
                    ws = sh.worksheet("Sheet1")
                    row_num = int(target_idx) + 2
                    ws.update_cell(row_num, 6, "วิเคราะห์แล้ว") # Status
                    ws.update_cell(row_num, 10, g)   # Gate
                    ws.update_cell(row_num, 13, ma)  # Main_Alley
                    ws.update_cell(row_num, 14, ms)  # Main_Side
                    ws.update_cell(row_num, 15, sa)  # Sub_Alley
                    st.success("บันทึกเรียบร้อย!")
                    st.rerun()
            else: st.info("🎉 ไม่มีงานค้าง")
    elif admin_password != "":
        st.error("❌ รหัสผ่านไม่ถูกต้อง")

# --- TAB 3: SEARCH ---
with tab3:
    st.subheader("🔍 ค้นหาและนำทาง")
    search_df = load_data_robust("Sheet1")
    if not search_df.empty:
        query = st.text_input("ค้นหาชื่อหรือพิกัด:")
        if query:
            res = search_df[search_df.apply(lambda r: query.lower() in str(r.values).lower(), axis=1)]
            for idx, row in res.iterrows():
                with st.expander(f"📍 {row['place_name']} ({row['gate']})"):
                    st.write(f"ซอย: {row['main_alley']} | ฝั่ง: {row['main_side']}")
                    nav_url = f"https://www.google.com/maps?q={row['lat']},{row['lon']}"
                    st.link_button("🚗 นำทาง", nav_url)

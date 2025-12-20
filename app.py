import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime

# --- ตั้งค่าหน้าจอ ---
st.set_page_config(page_title="NU Smart Database Admin", page_icon="⚙️", layout="wide")

# --- 1. การเชื่อมต่อ Google Sheets ---
def get_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    client = gspread.authorize(creds)
    return client.open_by_key(st.secrets["SHEET_ID"])

def load_mapping_df():
    sh = get_sheets()
    df = pd.DataFrame(sh.worksheet("Mapping").get_all_records())
    return df

# --- 2. ระบบ AI ตรวจสอบความขัดแย้ง (Conflict Checker) ---
def validate_structure(df, new_gate, new_soi, new_detail):
    # กรณี 1: ตรวจสอบว่าซอยนี้เคยถูกลงทะเบียนไว้ที่ประตูอื่นแล้วหรือยัง
    existing_gate = df[df['ซอยหลัก'] == new_soi]['ประตู'].unique()
    if len(existing_gate) > 0 and existing_gate[0] != new_gate:
        return f"❌ ขัดแย้ง: ซอย '{new_soi}' ถูกบันทึกไว้ที่ '{existing_gate[0]}' แล้ว คุณกำลังพยายามเพิ่มมันที่ '{new_gate}' กรุณาตรวจสอบว่าซอยซ้ำกันหรือเลือกประตูผิด"
    
    # กรณี 2: ตรวจสอบข้อมูลซ้ำซ้อนเป๊ะๆ
    duplicate = df[(df['ประตู'] == new_gate) & (df['ซอยหลัก'] == new_soi) & (df['รายละเอียดจุดส่ง'] == new_detail)]
    if not duplicate.empty:
        return "⚠️ ข้อมูลนี้มีอยู่แล้วในระบบ ไม่จำเป็นต้องเพิ่มซ้ำ"
    
    return None

# --- 3. UI หน้าหลัก ---
st.title("🛵 ระบบจัดการพิกัดส่งของ มน.")

tab1, tab2 = st.tabs(["📌 บันทึกงานส่งของ", "⚙️ โหมดแก้ไข/เพิ่มซอย (Admin)"])

# --- TAB 1: สำหรับการใช้งานปกติ ---
with tab1:
    try:
        mapping_df = load_mapping_df()
        location = streamlit_geolocation()
        lat, lon = location.get('latitude'), location.get('longitude')

        if lat and lon:
            g_col, s_col, d_col = st.columns(3)
            with g_col:
                gate = st.selectbox("เลือกประตู:", ["-- เลือก --"] + mapping_df['ประตู'].unique().tolist())
            with s_col:
                if gate != "-- เลือก --":
                    sois = mapping_df[mapping_df['ประตู'] == gate]['ซอยหลัก'].unique().tolist()
                    main_soi = st.selectbox("เลือกซอยหลัก:", ["-- เลือก --"] + sois)
                else: main_soi = "-- เลือก --"
            with d_col:
                if main_soi != "-- เลือก --":
                    spots = mapping_df[(mapping_df['ประตู'] == gate) & (mapping_df['ซอยหลัก'] == main_soi)]['รายละเอียดจุดส่ง'].tolist()
                    spot = st.selectbox("จุดส่ง/ฝั่ง:", spots)
                else: spot = "-- เลือก --"
            
            note = st.text_input("ระบุเลขห้อง/ชื่อหอพัก:")
            
            if st.button("🚀 บันทึกพิกัด"):
                sh = get_sheets()
                sh.get_worksheet(0).append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"{gate} | {main_soi} | {spot} | {note}", lat, lon])
                st.success("บันทึกเรียบร้อย!")
        else:
            st.warning("📍 กรุณากด GPS")
    except: st.error("ยังไม่มีฐานข้อมูล Mapping โปรดไปที่โหมดแอดมินเพื่อเริ่มเพิ่มซอย")

# --- TAB 2: โหมดแอดมิน (รหัส 9999) ---
with tab2:
    pin = st.text_input("กรอกรหัสผ่านเพื่อแก้ไข:", type="password")
    if pin == "9999":
        st.header("🛠 จัดการโครงสร้างซอย")
        
        # ส่วนแสดงตารางปัจจุบัน
        mapping_df = load_mapping_df()
        st.subheader("ผังซอยปัจจุบัน")
        st.dataframe(mapping_df, use_container_width=True)

        st.divider()
        
        # ส่วนของการเพิ่มข้อมูลใหม่ (ปุ่มบวก)
        st.subheader("➕ เพิ่มซอยหรือรายละเอียดใหม่")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            add_gate = st.selectbox("1. เลือกประตูที่ต้องการเพิ่ม:", ["ประตู 1", "ประตู 3", "ประตู 4", "ประตู 5 ถึง 6"])
        with col2:
            # ให้เลือกว่าจะเพิ่มซอยใหม่ หรือเลือกซอยเดิมเพื่อเพิ่มรายละเอียด
            existing_sois = mapping_df[mapping_df['ประตู'] == add_gate]['ซอยหลัก'].unique().tolist()
            add_soi = st.selectbox("2. เลือกซอยเดิม (เพื่อเพิ่มจุดย่อย) หรือพิมพ์ชื่อซอยใหม่:", ["-- พิมพ์ซอยใหม่ --"] + existing_sois)
            if add_soi == "-- พิมพ์ซอยใหม่ --":
                add_soi = st.text_input("พิมพ์ชื่อซอยใหม่ที่นี่:")
        with col3:
            add_detail = st.text_input("3. เพิ่มรายละเอียด/จุดส่ง/ฝั่งถนน:")

        if st.button("➕ ยืนยันเพิ่มข้อมูลลงระบบ"):
            if add_soi and add_detail:
                # ตรวจสอบความขัดแย้ง
                error_msg = validate_structure(mapping_df, add_gate, add_soi, add_detail)
                
                if error_msg:
                    st.error(error_msg)
                else:
                    with st.spinner("กำลังเชื่อมต่อฐานข้อมูล..."):
                        sh = get_sheets()
                        sh.worksheet("Mapping").append_row([add_gate, add_soi, add_detail])
                        st.cache_data.clear()
                        st.success(f"✅ เพิ่มข้อมูลสำเร็จ: {add_gate} > {add_soi} > {add_detail}")
                        st.rerun()
            else:
                st.warning("กรุณากรอกข้อมูลให้ครบทุกช่อง")

        # ระบบลบข้อมูล (เพื่อความสะดวก)
        with st.expander("🗑️ ลบข้อมูลที่ผิดพลาด"):
            row_to_delete = st.number_input("ใส่เลขแถวที่ต้องการลบ (นับจากแถวแรกในตารางข้างบน):", min_value=0, step=1)
            if st.button("ยืนยันการลบ"):
                sh = get_sheets()
                sh.worksheet("Mapping").delete_rows(row_to_delete + 2) # +2 เพราะมี Header และ Index
                st.cache_data.clear()
                st.success("ลบข้อมูลแล้ว")
                st.rerun()
    else:
        st.info("กรุณาใส่รหัส 9999 เพื่อเข้าถึงการแก้ไข")

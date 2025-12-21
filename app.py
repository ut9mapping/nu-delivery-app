import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import google.generativeai as genai
import re
import pydeck as pdk

# --- 1. ตั้งค่าเบื้องต้น ---
st.set_page_config(page_title="NU Delivery Admin Pro", page_icon="🛵", layout="wide")

def get_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])

try:
    genai.configure(api_key=st.secrets["API_KEY"])
    model = genai.GenerativeModel('models/gemini-1.5-flash')
except:
    st.error("AI Config Error")

# --- 2. ฟังก์ชันจัดการข้อมูล ---
def load_mapping_df():
    try:
        sh = get_sheets()
        sheet = sh.worksheet("Mapping")
        data = sheet.get_all_records()
        df = pd.DataFrame(data) if data else pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])
        df.columns = [str(c).strip() for c in df.columns]
        return df.map(lambda x: str(x).strip() if x is not None else "")
    except:
        return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])

def display_precision_map(lat, lon, zoom=18):
    layer = pdk.Layer("ScatterplotLayer", data=pd.DataFrame({'lat': [lat], 'lon': [lon]}),
        get_position='[lon, lat]', get_color='[255, 75, 75, 230]', get_radius=3)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom), map_style='carto-positron'))

# --- 3. ส่วน UI หลัก ---
st.title("🛵 ระบบพิกัดขนส่ง มน. (Dynamic Admin)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงานส่งของ", "🔍 ค้นหาพิกัด", "⚙️ Admin Manage"])

# (Tab 1 & 2 ทำงานเหมือนเดิม)
with tab1:
    location = streamlit_geolocation()
    if location.get('latitude'):
        lat, lon = location['latitude'], location['longitude']
        st.success(f"📍 GPS พร้อม: {lat:.6f}, {lon:.6f}")
        display_precision_map(lat, lon, zoom=17)
        gate = st.selectbox("1. เลือกประตู:", ["-- เลือก --"] + sorted(mapping_df['ประตู'].unique().tolist()))
        if gate != "-- เลือก --":
            # (Logic การเลือก 5 ระดับคงเดิม)
            extra = st.text_input("✍️ หมายเหตุเพิ่มเติม:")
            if st.button("🚀 บันทึกพิกัด"):
                sh = get_sheets()
                sh.worksheet("Sheet1").append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"{gate} | {extra}", lat, lon, "URL"])
                st.balloons(); st.success("บันทึกแล้ว!")

with tab2:
    query = st.text_input("ค้นหาชื่อสถานที่:")
    if st.button("ค้นหา"):
        # (Logic การค้นหาคงเดิม)
        st.info("ระบบกำลังค้นหา...")

# --- TAB 3: ADMIN MANAGE (เวอร์ชันใหม่ กดบวกได้) ---
with tab3:
    st.header("⚙️ จัดการโครงสร้างซอย")
    admin_pin = st.text_input("กรอก Admin PIN เพื่อเข้าถึง:", type="password")
    
    if admin_pin == "9999":
        # --- ส่วนการเพิ่มข้อมูลแบบ Dynamic ---
        st.subheader("➕ เพิ่มข้อมูลชุดใหม่ (กด + เพื่อเพิ่มซอย)")
        
        # เลือก Parent (ประตู และ ฝั่ง)
        c1, c2 = st.columns(2)
        with c1:
            sel_gate = st.selectbox("เลือกประตู:", ["-- เพิ่มใหม่ --"] + sorted(mapping_df['ประตู'].unique().tolist()))
            final_gate = st.text_input("ระบุชื่อประตูใหม่:") if sel_gate == "-- เพิ่มใหม่ --" else sel_gate
        with c2:
            sel_zone = st.selectbox("เลือกฝั่ง/โซน:", ["-- เพิ่มใหม่ --"] + sorted(mapping_df[mapping_df['ประตู']==final_gate]['ฝั่งถนน/โซน'].unique().tolist())) if final_gate else "-- เพิ่มใหม่ --"
            final_zone = st.text_input("ระบุฝั่งใหม่:", value="-") if sel_zone == "-- เพิ่มใหม่ --" else sel_zone

        st.markdown("---")
        
        # ใช้ Session State เก็บรายการซอยที่กำลังจะเพิ่ม
        if 'rows_to_add' not in st.session_state:
            st.session_state.rows_to_add = [{"main": "", "sub": "-", "det": "-"}]

        def add_row():
            st.session_state.rows_to_add.append({"main": "", "sub": "-", "det": "-"})

        def remove_row(index):
            if len(st.session_state.rows_to_add) > 1:
                st.session_state.rows_to_add.pop(index)

        # แสดงรายการที่กำลังจะเพิ่ม
        for i, row in enumerate(st.session_state.rows_to_add):
            cols = st.columns([3, 3, 3, 1])
            st.session_state.rows_to_add[i]['main'] = cols[0].text_input(f"ซอยหลัก {i+1}", value=row['main'], key=f"m_{i}")
            st.session_state.rows_to_add[i]['sub'] = cols[1].text_input(f"ซอยย่อย/เชื่อม {i+1}", value=row['sub'], key=f"s_{i}")
            st.session_state.rows_to_add[i]['det'] = cols[2].text_input(f"จุดย่อย {i+1}", value=row['det'], key=f"d_{i}")
            if cols[3].button("🗑️", key=f"del_{i}"):
                remove_row(i)
                st.rerun()

        if st.button("➕ เพิ่มซอยถัดไป"):
            add_row()
            st.rerun()

        if st.button("💾 บันทึกรายการทั้งหมดลงระบบ", type="primary"):
            new_data = []
            for r in st.session_state.rows_to_add:
                if r['main']: # บันทึกเฉพาะแถวที่มีชื่อซอยหลัก
                    new_data.append([final_gate, final_zone, r['main'], r['sub'], r['det']])
            
            if new_data:
                sh = get_sheets()
                sh.worksheet("Mapping").append_rows(new_data)
                st.session_state.rows_to_add = [{"main": "", "sub": "-", "det": "-"}]
                st.success(f"บันทึก {len(new_data)} รายการสำเร็จ!"); st.rerun()
            else:
                st.error("กรุณากรอกชื่อซอยหลักอย่างน้อย 1 รายการ")

        st.divider()

        # --- ส่วนการลบข้อมูล (ต้องยืนยัน PIN) ---
        st.subheader("🗑️ รายการทั้งหมดในระบบ")
        st.dataframe(mapping_df, use_container_width=True)
        
        row_idx = st.number_input("ลำดับแถวที่ต้องการลบ (Index):", min_value=0, max_value=len(mapping_df)-1, step=1)
        
        if st.button("❌ ลบข้อมูลแถวนี้", type="secondary"):
            st.session_state.confirm_delete = True

        if st.session_state.get('confirm_delete'):
            st.warning(f"ยืนยันการลบแถวที่ {row_idx}? ข้อมูลนี้จะหายไปถาวร")
            conf_pin = st.text_input("ใส่รหัส PIN อีกครั้งเพื่อยืนยันการลบ:", type="password")
            if st.button("🔥 ยืนยันลบเด็ดขาด"):
                if conf_pin == "9999":
                    sh = get_sheets()
                    sh.worksheet("Mapping").delete_rows(int(row_idx) + 2)
                    st.session_state.confirm_delete = False
                    st.success("ลบสำเร็จ!"); st.rerun()
                else:
                    st.error("รหัสไม่ถูกต้อง")

import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import google.generativeai as genai
import re
import pydeck as pdk

# --- 1. การตั้งค่าเบื้องต้น ---
st.set_page_config(page_title="NU Precision Delivery Pro", page_icon="🛵", layout="wide")

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
        if not data:
            return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])
        df = pd.DataFrame(data)
        df.columns = [str(c).strip() for c in df.columns]
        df = df.map(lambda x: str(x).strip() if x is not None else "")
        return df
    except:
        return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])

def get_options(df, filters):
    temp_df = df.copy()
    for col, val in filters.items():
        if val and val != "-- เลือก --":
            temp_df = temp_df[temp_df[col] == val]
    target_idx = len(filters)
    if target_idx < len(df.columns):
        opts = [str(x) for x in temp_df.iloc[:, target_idx].unique() if str(x) not in ["", "-", "None"]]
        return sorted(opts)
    return []

def display_precision_map(lat, lon, zoom=18):
    layer = pdk.Layer("ScatterplotLayer", data=pd.DataFrame({'lat': [lat], 'lon': [lon]}),
        get_position='[lon, lat]', get_color='[255, 75, 75, 230]', get_radius=3, pickable=True)
    view_state = pdk.ViewState(latitude=lat, longitude=lon, zoom=zoom, pitch=0)
    st.pydeck_chart(pdk.Deck(layers=[layer], initial_view_state=view_state, map_style='carto-positron'))

# --- 3. ส่วน UI หน้าหลัก ---
st.title("🛵 ระบบพิกัดขนส่ง มน. (Admin Update)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงานส่งของ", "🔍 ค้นหาพิกัด & ภาพจำลอง", "⚙️ Admin Manage"])

# (Tab 1 และ Tab 2 คงไว้ตามเดิมจากเวอร์ชันก่อนหน้า)
# ... [ข้ามไปดู Tab 3 ที่อัปเดตใหม่] ...

with tab1:
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    if lat and lon:
        st.success(f"📍 GPS พร้อม (พิกัด: {lat:.6f}, {lon:.6f})")
        display_precision_map(lat, lon, zoom=17) 
        gate_list = [str(x) for x in mapping_df['ประตู'].unique() if str(x) not in ["", "None"]]
        gate = st.selectbox("1. เลือกประตู:", ["-- เลือก --"] + sorted(gate_list))
        if gate != "-- เลือก --":
            c1, c2 = st.columns(2)
            with c1:
                zones = get_options(mapping_df, {"ประตู": gate})
                zone = st.selectbox("2. ฝั่งถนน/โซนหลัก:", ["-- เลือก --"] + zones) if zones else "-"
            with c2:
                m_sois = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone}) if zone != "-- เลือก --" else []
                main_soi = st.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + m_sois) if m_sois else "-"
            c3, c4 = st.columns(2)
            with c3:
                s_sois = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi}) if main_soi != "-- เลือก --" else []
                sub_soi = st.selectbox("4. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + s_sois) if s_sois else "-"
            with c4:
                dets = get_options(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi, "ซอยย่อย/ทางเชื่อม": sub_soi}) if sub_soi != "-- เลือก --" else []
                detail = st.selectbox("5. ฝั่ง/จุดรายละเอียด:", ["-- เลือก --"] + dets) if dets else "-"
            extra = st.text_input("✍️ หมายเหตุเพิ่มเติม:")
            if st.button("🚀 ยืนยันบันทึกพิกัด"):
                sh = get_sheets()
                log_sheet = sh.worksheet("Sheet1")
                full_info = f"{gate} | {zone} | {main_soi} | {sub_soi} | {detail} | {extra}"
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                maps_url = f"https://www.google.com/maps?q={lat},{lon}"
                log_sheet.append_row([now, full_info, lat, lon, maps_url])
                st.balloons(); st.success("บันทึกเรียบร้อย!")
    else: st.warning("📍 กรุณาเปิด GPS")

with tab2:
    st.header("🔍 ค้นหาประวัติจุดส่ง")
    query = st.text_input("ค้นหาชื่อสถานที่:")
    if st.button("เริ่มการค้นหา"):
        sh = get_sheets(); history_df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        results = history_df[history_df['บันทึก'].str.contains(query, case=False, na=False)]
        if not results.empty:
            last = results.iloc[-1]; st.info(f"เจอข้อมูล: {last['บันทึก']}")
            display_precision_map(float(last['ละติจูด']), float(last['ลองจิจูด']), zoom=19)
        else: st.error("ไม่พบข้อมูล")

# --- TAB 3: ADMIN MANAGE (เวอร์ชันใหม่) ---
with tab3:
    st.header("⚙️ ระบบจัดการโครงสร้างซอย")
    admin_pin = st.text_input("กรอกรหัส Admin PIN:", type="password")
    
    if admin_pin == "9999":
        # --- ส่วนที่ 1: เพิ่มข้อมูลแบบ Subset ---
        st.subheader("➕ เพิ่มข้อมูลใหม่ (ต่อยอดจากเดิม)")
        col_a, col_b = st.columns(2)
        
        with col_a:
            # เลือกจากที่มีอยู่เดิมก่อน
            exist_gate = st.selectbox("เลือกประตูที่มีอยู่:", ["-- เพิ่มใหม่ --"] + sorted(mapping_df['ประตู'].unique().tolist()))
            final_gate = st.text_input("พิมพ์ชื่อประตูใหม่:", placeholder="เช่น ประตู 4") if exist_gate == "-- เพิ่มใหม่ --" else exist_gate
            
            exist_zone = st.selectbox("เลือกฝั่งถนนที่มีอยู่:", ["-- เพิ่มใหม่ --"] + sorted(mapping_df[mapping_df['ประตู']==final_gate]['ฝั่งถนน/โซน'].unique().tolist())) if final_gate else "-- เพิ่มใหม่ --"
            final_zone = st.text_input("พิมพ์ฝั่งถนนใหม่:", value="-") if exist_zone == "-- เพิ่มใหม่ --" else exist_zone

        with col_b:
            exist_soi = st.selectbox("เลือกซอยหลักที่มีอยู่:", ["-- เพิ่มใหม่ --"] + sorted(mapping_df[(mapping_df['ประตู']==final_gate) & (mapping_df['ฝั่งถนน/โซน']==final_zone)]['ซอยหลัก'].unique().tolist())) if final_zone else "-- เพิ่มใหม่ --"
            final_soi = st.text_input("พิมพ์ชื่อซอยหลักใหม่:") if exist_soi == "-- เพิ่มใหม่ --" else exist_soi
            
            final_sub = st.text_input("ซอยย่อย/เชื่อม (ถ้าไม่มีใส่ -):", value="-")
            final_det = st.text_input("ฝั่ง/จุดย่อย (ถ้าไม่มีใส่ -):", value="-")

        if st.button("✅ บันทึกโครงสร้างใหม่"):
            if final_gate and final_soi:
                sh = get_sheets()
                sh.worksheet("Mapping").append_row([final_gate, final_zone, final_soi, final_sub, final_det])
                st.cache_data.clear(); st.success("เพิ่มข้อมูลสำเร็จ!"); st.rerun()
            else: st.error("กรุณากรอกข้อมูลให้ครบ")

        st.divider()

        # --- ส่วนที่ 2: ตารางรายการและการลบ ---
        st.subheader("🗑️ รายการข้อมูลทั้งหมด (ลบข้อมูล)")
        # แสดงตารางเพื่อให้ดูง่าย
        st.dataframe(mapping_df, use_container_width=True)
        
        # ระบบลบระบุแถว
        row_to_delete = st.number_input("ใส่ลำดับแถวที่ต้องการลบ (เริ่มจาก 0):", min_value=0, max_value=len(mapping_df)-1, step=1)
        
        if st.button("❌ ลบแถวที่เลือก"):
            # สร้างการยืนยันรหัสอีกครั้งก่อนลบ
            st.warning(f"คุณกำลังจะลบข้อมูลแถวที่ {row_to_delete}: {mapping_df.iloc[row_to_delete].tolist()}")
            confirm_pin = st.text_input("ใส่รหัส PIN เพื่อยืนยันการลบ:", type="password", key="del_confirm")
            
            if st.button("🔥 ยืนยันลบถาวร"):
                if confirm_pin == "9999":
                    sh = get_sheets()
                    # ใน gspread row จะเริ่มที่ 2 เพราะแถว 1 คือ Header
                    sh.worksheet("Mapping").delete_rows(int(row_to_delete) + 2)
                    st.cache_data.clear(); st.success("ลบข้อมูลสำเร็จแล้ว!"); st.rerun()
                else:
                    st.error("รหัสยืนยันไม่ถูกต้อง")

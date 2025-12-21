import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import google.generativeai as genai
import re
import pydeck as pdk

# --- 1. การตั้งค่าพื้นฐาน ---
st.set_page_config(page_title="NU Delivery Pro: Batch Admin", page_icon="🛵", layout="wide")

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

# --- 3. UI หน้าหลัก ---
st.title("🛵 ระบบพิกัดขนส่ง มน. (Batch Entry Mode)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงานส่งของ", "🔍 ค้นหาพิกัด", "⚙️ Admin Manage"])

# --- TAB 1 & 2 (ระบบบันทึกและค้นหาแบบละเอียด) ---
with tab1:
    location = streamlit_geolocation()
    if location.get('latitude'):
        lat, lon = location['latitude'], location['longitude']
        st.success(f"📍 GPS พร้อม: {lat:.6f}, {lon:.6f}"); display_precision_map(lat, lon, zoom=17)
        gate = st.selectbox("1. เลือกประตู:", ["-- เลือก --"] + sorted([str(x) for x in mapping_df['ประตู'].unique() if x]))
        if gate != "-- เลือก --":
            def get_opts(df, filters):
                temp = df.copy()
                for k, v in filters.items():
                    if v and v != "-- เลือก --": temp = temp[temp[k] == v]
                idx = len(filters)
                return sorted([str(x) for x in temp.iloc[:, idx].unique() if str(x) not in ["", "-"]]) if idx < len(df.columns) else []
            c1, c2 = st.columns(2)
            zone = c1.selectbox("2. ฝั่งของถนน:", ["-- เลือก --"] + get_opts(mapping_df, {"ประตู": gate}))
            main_soi = c2.selectbox("3. ซอยหลัก:", ["-- เลือก --"] + get_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone}))
            c3, c4 = st.columns(2)
            sub_soi = c3.selectbox("4. ซอยย่อย/ทางเชื่อม:", ["-- เลือก --"] + get_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi}))
            detail = c4.selectbox("5. ฝั่งของซอยย่อย (ท้ายสุด):", ["-- เลือก --"] + get_opts(mapping_df, {"ประตู": gate, "ฝั่งถนน/โซน": zone, "ซอยหลัก": main_soi, "ซอยย่อย/ทางเชื่อม": sub_soi}))
            extra = st.text_input("✍️ หมายเหตุ (ชื่อหอ/ห้อง):")
            if st.button("🚀 บันทึกพิกัด"):
                sh = get_sheets(); sh.worksheet("Sheet1").append_row([datetime.now().strftime("%Y-%m-%d %H:%M:%S"), f"{gate}|{zone}|{main_soi}|{sub_soi}|{detail}|{extra}", lat, lon, "URL"])
                st.balloons(); st.success("บันทึกสำเร็จ!")

with tab2:
    query = st.text_input("🔍 ค้นหาชื่อสถานที่:")
    if st.button("ค้นหา"):
        sh = get_sheets(); history_df = pd.DataFrame(sh.worksheet("Sheet1").get_all_records())
        results = history_df[history_df['บันทึก'].str.contains(query, case=False, na=False)]
        if not results.empty:
            last = results.iloc[-1]; st.info(f"พบ: {last['บันทึก']}"); display_precision_map(float(last['ละติจูด']), float(last['ลองจิจูด']), zoom=19)
        else: st.error("ไม่พบข้อมูล")

# --- TAB 3: ADMIN MANAGE (เวอร์ชันเพิ่มได้ทุกระดับพร้อมกัน) ---
with tab3:
    st.header("⚙️ จัดการโครงสร้าง (Batch Entry)")
    if st.text_input("Admin PIN:", type="password") == "9999":
        st.subheader("➕ เพิ่มข้อมูลชุดใหญ่ (ระบุซอยหลักและซอยย่อยได้อิสระ)")
        
        # 1. ส่วนหัวคงที่: ประตู และ ฝั่งถนน (ปกติมักจะเพิ่มในโซนเดียวกันทีละเยอะๆ)
        c1, c2 = st.columns(2)
        with c1:
            sel_gate = st.selectbox("เลือกประตู:", ["-- เพิ่มใหม่ --"] + sorted([str(x) for x in mapping_df['ประตู'].unique() if x]))
            final_gate = st.text_input("ระบุประตูใหม่:") if sel_gate == "-- เพิ่มใหม่ --" else sel_gate
        with c2:
            sel_zone = st.selectbox("เลือกฝั่งถนน:", ["-- เพิ่มใหม่ --"] + sorted([str(x) for x in mapping_df[mapping_df['ประตู']==final_gate]['ฝั่งถนน/โซน'].unique() if x])) if final_gate else "-- เพิ่มใหม่ --"
            final_zone = st.text_input("ระบุฝั่งถนนใหม่:", value="-") if sel_zone == "-- เพิ่มใหม่ --" else sel_zone

        st.info(f"💡 ทุกแถวที่เพิ่มด้านล่าง จะถูกจัดเข้าสู่: **{final_gate}** > **{final_zone}**")
        st.divider()

        # 2. ส่วนตาราง Dynamic: เพิ่มซอยหลัก + ซอยย่อย + ฝั่งสุดท้าย ได้พร้อมกัน
        if 'batch_rows' not in st.session_state:
            st.session_state.batch_rows = [{"main": "", "sub": "-", "det": "-"}]

        def add_batch_row(): st.session_state.batch_rows.append({"main": "", "sub": "-", "det": "-"})
        def remove_batch_row(i): 
            if len(st.session_state.batch_rows) > 1: st.session_state.batch_rows.pop(i)

        for i, row in enumerate(st.session_state.batch_rows):
            cols = st.columns([4, 4, 4, 1])
            # ช่องซอยหลัก (กรอกใหม่ได้ทุกแถว)
            st.session_state.batch_rows[i]['main'] = cols[0].text_input(f"ซอยหลัก {i+1}", value=row['main'], key=f"bm_{i}", placeholder="ซอยหลัก")
            # ช่องซอยย่อย
            st.session_state.batch_rows[i]['sub'] = cols[1].text_input(f"ซอยย่อย {i+1}", value=row['sub'], key=f"bs_{i}", placeholder="ซอยย่อย")
            # ช่องฝั่งสุดท้าย
            st.session_state.batch_rows[i]['det'] = cols[2].text_input(f"ฝั่งสุดท้าย {i+1}", value=row['det'], key=f"bd_{i}", placeholder="ฝั่งซ้าย/ขวา")
            if cols[3].button("🗑️", key=f"bdel_{i}"):
                remove_batch_row(i); st.rerun()

        st.button("➕ เพิ่มแถวถัดไป (เพิ่มได้ทั้งซอยหลัก/ย่อยใหม่)", on_click=add_batch_row)

        if st.button("💾 บันทึกข้อมูลทั้งหมดลงฐานข้อมูล", type="primary"):
            # เตรียมข้อมูลทุกแถว
            new_data = [[final_gate, final_zone, r['main'], r['sub'], r['det']] for r in st.session_state.batch_rows if r['main']]
            
            if new_data and final_gate:
                sh = get_sheets(); sh.worksheet("Mapping").append_rows(new_data)
                st.session_state.batch_rows = [{"main": "", "sub": "-", "det": "-"}] # ล้างข้อมูลหลังบันทึก
                st.success(f"บันทึกสำเร็จ {len(new_data)} รายการ!"); st.rerun()
            else:
                st.error("กรุณากรอก 'ประตู' และ 'ซอยหลัก' อย่างน้อย 1 แถว")

        st.divider()
        # ส่วนลบข้อมูล (ปลอดภัยด้วยรหัสผ่าน)
        st.subheader("🗑️ จัดการลบข้อมูลเดิม")
        st.dataframe(mapping_df, use_container_width=True)
        del_idx = st.number_input("ลำดับแถวที่จะลบ (Index):", min_value=0, max_value=len(mapping_df)-1, step=1)
        if st.button("❌ ลบแถวที่เลือก"):
            st.session_state.confirm_del = del_idx
        
        if st.session_state.get('confirm_del') is not None:
            st.warning(f"ยืนยันลบแถวที่ {st.session_state.confirm_del}?")
            if st.text_input("ใส่ PIN ยืนยันลบถาวร:", type="password", key="v_del") == "9999":
                if st.button("🔥 ยืนยันการลบ"):
                    sh = get_sheets(); sh.worksheet("Mapping").delete_rows(int(st.session_state.confirm_del) + 2)
                    st.session_state.confirm_del = None; st.success("ลบสำเร็จ!"); st.rerun()

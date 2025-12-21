import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าและเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery: Ultimate Admin", page_icon="🛵", layout="wide")

def get_sheets():
    scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
    return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])

# --- 2. ฟังก์ชันจัดการข้อมูล ---
def load_mapping_df():
    try:
        sh = get_sheets()
        data = sh.worksheet("Mapping").get_all_records()
        df = pd.DataFrame(data) if data else pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])
        return df.map(lambda x: str(x).strip())
    except:
        return pd.DataFrame(columns=["ประตู", "ฝั่งถนน/โซน", "ซอยหลัก", "ซอยย่อย/ทางเชื่อม", "ฝั่ง/จุดรายละเอียด"])

# --- 3. UI ส่วนหลัก ---
st.title("🛵 ระบบจัดการพิกัด (แบบบวกเพิ่มอิสระ)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงาน", "🔍 ค้นหา", "⚙️ Admin Manage"])

# (Tab 1 & 2 คงเดิมเพื่อการใช้งานพิกัด)
with tab1:
    location = streamlit_geolocation()
    if location.get('latitude'):
        lat, lon = location['latitude'], location['longitude']
        st.success(f"📍 พิกัดปัจจุบัน: {lat:.6f}, {lon:.6f}")
        # ... (โค้ดแสดงแผนที่และ Selectbox กรอง 5 ระดับเหมือนเดิม)

# --- TAB 3: ADMIN MANAGE (Nested Dynamic Form) ---
with tab3:
    st.header("⚙️ จัดการโครงสร้างแบบละเอียด")
    admin_pin = st.text_input("กรอก Admin PIN:", type="password")
    
    if admin_pin == "9999":
        st.subheader("🛠️ ตัวสร้างโครงสร้าง (Hierarchy Builder)")
        
        # ส่วนคงที่ (ระดับบนสุด)
        c1, c2 = st.columns(2)
        with c1:
            sel_g = st.selectbox("เลือกประตู:", ["-- เพิ่มใหม่ --"] + sorted(mapping_df['ประตู'].unique().tolist()))
            gate_final = st.text_input("ระบุประตูใหม่:") if sel_g == "-- เพิ่มใหม่ --" else sel_g
        with c2:
            sel_z = st.selectbox("เลือกฝั่งถนน:", ["-- เพิ่มใหม่ --"] + sorted(mapping_df[mapping_df['ประตู']==gate_final]['ฝั่งถนน/โซน'].unique().tolist())) if gate_final else "-- เพิ่มใหม่ --"
            zone_final = st.text_input("ระบุฝั่งถนนใหม่:", value="-") if sel_z == "-- เพิ่มใหม่ --" else sel_z

        st.divider()

        # ระบบ Session State สำหรับเก็บโครงสร้างที่กำลังพิมพ์
        # โครงสร้าง: [ { "main": "", "subs": [ { "name": "", "details": [""] } ] } ]
        if 'tree_data' not in st.session_state:
            st.session_state.tree_data = [{"main": "", "subs": [{"name": "-", "details": ["-"]}]}]

        # ฟังก์ชันเพิ่ม/ลด
        def add_main(): st.session_state.tree_data.append({"main": "", "subs": [{"name": "-", "details": ["-"]}]})
        def add_sub(m_idx): st.session_state.tree_data[m_idx]["subs"].append({"name": "", "details": ["-"]})
        def add_det(m_idx, s_idx): st.session_state.tree_data[m_idx]["subs"][s_idx]["details"].append("")

        # แสดงผลการบวกเพิ่ม
        for m_idx, m_item in enumerate(st.session_state.tree_data):
            with st.expander(f"🏘️ ซอยหลักที่ {m_idx+1}: {m_item['main'] if m_item['main'] else 'ยังไม่ได้ระบุ'}", expanded=True):
                m_item['main'] = st.text_input(f"ชื่อซอยหลัก", value=m_item['main'], key=f"main_{m_idx}")
                
                # ระดับซอยย่อย
                for s_idx, s_item in enumerate(m_item['subs']):
                    st.markdown(f"---")
                    c_s1, c_s2 = st.columns([1, 10])
                    s_item['name'] = c_s2.text_input(f"↳ ซอยย่อย/ทางเชื่อม", value=s_item['name'], key=f"sub_{m_idx}_{s_idx}")
                    
                    # ระดับจุดรายละเอียด/ฝั่ง
                    for d_idx, d_item in enumerate(s_item['details']):
                        c_d1, c_d2, c_d3 = st.columns([2, 8, 1])
                        s_item['details'][d_idx] = c_d2.text_input(f"  ↳ ฝั่ง/จุดสุดท้าย", value=d_item, key=f"det_{m_idx}_{s_idx}_{d_idx}")
                    
                    # ปุ่มบวกรายละเอียด (Level 3)
                    st.button(f"➕ บวกฝั่ง/จุด ในซอยย่อยนี้", key=f"btn_d_{m_idx}_{s_idx}", on_click=add_det, args=(m_idx, s_idx))

                # ปุ่มบวกซอยย่อย (Level 2)
                st.button(f"➕ บวกซอยย่อย ใน{m_item['main']}", key=f"btn_s_{m_idx}", on_click=add_sub, args=(m_idx,))

        # ปุ่มบวกซอยหลัก (Level 1)
        st.button("➕ เพิ่มซอยหลักใหม่", on_click=add_main)

        st.divider()
        
        if st.button("💾 บันทึกโครงสร้างทั้งหมดลง Google Sheets", type="primary"):
            final_rows = []
            for m in st.session_state.tree_data:
                if m['main']:
                    for s in m['subs']:
                        for d in s['details']:
                            final_rows.append([gate_final, zone_final, m['main'], s['name'], d])
            
            if final_rows:
                sh = get_sheets()
                sh.worksheet("Mapping").append_rows(final_rows)
                st.session_state.tree_data = [{"main": "", "subs": [{"name": "-", "details": ["-"]}]}]
                st.success(f"บันทึก {len(final_rows)} แถวเรียบร้อย!"); st.rerun()
            else:
                st.error("กรุณากรอกข้อมูลให้ครบถ้วน")

        # --- ส่วนการลบ (ต้องยืนยันรหัส) ---
        st.divider()
        st.subheader("🗑️ ลบข้อมูลเดิม (ใส่รหัสยืนยัน)")
        st.dataframe(mapping_df, use_container_width=True)
        
        del_idx = st.number_input("ลำดับ Index ที่ต้องการลบ:", min_value=0, max_value=len(mapping_df)-1, step=1)
        if st.button("❌ ลบรายการนี้"):
            st.session_state.confirm_del_idx = del_idx

        if 'confirm_del_idx' in st.session_state:
            st.warning(f"กำลังจะลบ Index: {st.session_state.confirm_del_idx} ยืนยันรหัส PIN อีกครั้ง")
            re_pin = st.text_input("รหัสยืนยันการลบ:", type="password", key="re_pin")
            if st.button("🔥 ยืนยันลบเด็ดขาด"):
                if re_pin == "9999":
                    sh = get_sheets()
                    sh.worksheet("Mapping").delete_rows(int(st.session_state.confirm_del_idx) + 2)
                    del st.session_state.confirm_del_idx
                    st.success("ลบสำเร็จ!"); st.rerun()
                else:
                    st.error("รหัสไม่ถูกต้อง")

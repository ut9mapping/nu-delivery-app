import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าและเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery: Smart Admin", page_icon="🛵", layout="wide")

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
st.title("🛵 ระบบจัดการพิกัด (Smart Entry)")
mapping_df = load_mapping_df()

tab1, tab2, tab3 = st.tabs(["📌 บันทึกงาน", "🔍 ค้นหา", "⚙️ Admin Manage"])

# ... (Tab 1 & 2 คงเดิม) ...

# --- TAB 3: ADMIN MANAGE (เวอร์ชันเลือกจากข้อมูลเก่าได้) ---
with tab3:
    st.header("⚙️ เพิ่มข้อมูล (เลือกซอยเดิม หรือ พิมพ์ซอยใหม่)")
    admin_pin = st.text_input("กรอก Admin PIN:", type="password")
    
    if admin_pin == "9999":
        # ส่วนที่ 1: เลือก ประตู และ ฝั่งถนน
        c1, c2 = st.columns(2)
        with c1:
            gates = sorted(mapping_df['ประตู'].unique().tolist())
            sel_g = st.selectbox("เลือกประตู:", ["-- เพิ่มใหม่ --"] + gates)
            final_gate = st.text_input("ระบุชื่อประตูใหม่:") if sel_g == "-- เพิ่มใหม่ --" else sel_g
            
        with c2:
            # กรองฝั่งถนนตามประตูที่เลือก
            zones = sorted(mapping_df[mapping_df['ประตู'] == final_gate]['ฝั่งถนน/โซน'].unique().tolist()) if final_gate else []
            sel_z = st.selectbox("เลือกฝั่งถนน:", ["-- เพิ่มใหม่ --"] + [z for z in zones if z and z != "-"] )
            final_zone = st.text_input("ระบุฝั่งถนนใหม่:", value="-") if sel_z == "-- เพิ่มใหม่ --" else sel_z

        st.markdown("---")

        # ส่วนที่ 2: ระบบ Batch Entry แบบฉลาด (ดึงซอยหลัก/ซอยย่อย เดิมมาให้เลือก)
        if 'rows' not in st.session_state:
            st.session_state.rows = [{"main": "", "sub": "-", "det": "-"}]

        def add_row(): st.session_state.rows.append({"main": "", "sub": "-", "det": "-"})
        def remove_row(i): 
            if len(st.session_state.rows) > 1: st.session_state.rows.pop(i)

        st.subheader("📝 รายการที่กำลังจะเพิ่ม")
        
        # ดึงรายชื่อซอยหลักที่มีอยู่แล้วใน ประตู+ฝั่ง นี้ เพื่อมาทำ Dropdown
        existing_mains = sorted(mapping_df[(mapping_df['ประตู'] == final_gate) & (mapping_df['ฝั่งถนน/โซน'] == final_zone)]['ซอยหลัก'].unique().tolist())
        
        for i, row in enumerate(st.session_state.rows):
            with st.container():
                cols = st.columns([4, 4, 4, 1])
                
                # --- ระดับ ซอยหลัก ---
                with cols[0]:
                    # ใช้ selectbox ที่มีตัวเลือก "-- พิมพ์ใหม่ --"
                    m_opts = ["-- พิมพ์ใหม่ --"] + [m for m in existing_mains if m and m != "-"]
                    sel_m = st.selectbox(f"เลือกซอยหลัก {i+1}", m_opts, key=f"sel_m_{i}")
                    if sel_m == "-- พิมพ์ใหม่ --":
                        st.session_state.rows[i]['main'] = st.text_input(f"ระบุซอยหลักใหม่ {i+1}", key=f"txt_m_{i}", placeholder="เช่น ซอย 1")
                    else:
                        st.session_state.rows[i]['main'] = sel_m

                # --- ระดับ ซอยย่อย ---
                with cols[1]:
                    # ดึงซอยย่อยเดิมของซอยหลักที่เลือกมาให้ดู
                    curr_main = st.session_state.rows[i]['main']
                    existing_subs = sorted(mapping_df[(mapping_df['ประตู'] == final_gate) & 
                                                      (mapping_df['ฝั่งถนน/โซน'] == final_zone) & 
                                                      (mapping_df['ซอยหลัก'] == curr_main)]['ซอยย่อย/ทางเชื่อม'].unique().tolist()) if curr_main else []
                    
                    s_opts = ["-- พิมพ์ใหม่/ไม่มี --"] + [s for s in existing_subs if s and s != "-"]
                    sel_s = st.selectbox(f"เลือกซอยย่อย {i+1}", s_opts, key=f"sel_s_{i}")
                    if sel_s == "-- พิมพ์ใหม่/ไม่มี --":
                        st.session_state.rows[i]['sub'] = st.text_input(f"ระบุซอยย่อยใหม่ {i+1}", value="-", key=f"txt_s_{i}")
                    else:
                        st.session_state.rows[i]['sub'] = sel_s

                # --- ระดับ ฝั่ง/จุดสุดท้าย ---
                with cols[2]:
                    st.session_state.rows[i]['det'] = st.text_input(f"ฝั่ง/จุดละเอียด {i+1}", value=row['det'], key=f"txt_d_{i}", placeholder="เช่น ฝั่งขวา / หอ A")

                with cols[3]:
                    st.write("##") # ปรับตำแหน่งปุ่มถังขยะ
                    if st.button("🗑️", key=f"del_{i}"):
                        remove_row(i); st.rerun()
            st.markdown(" ")

        st.button("➕ เพิ่มแถวถัดไป", on_click=add_row)

        if st.button("💾 บันทึกข้อมูลทั้งหมดลงระบบ", type="primary"):
            new_data = [[final_gate, final_zone, r['main'], r['sub'], r['det']] for r in st.session_state.rows if r['main']]
            if new_data:
                sh = get_sheets(); sh.worksheet("Mapping").append_rows(new_data)
                st.session_state.rows = [{"main": "", "sub": "-", "det": "-"}]
                st.success(f"บันทึกสำเร็จ {len(new_data)} รายการ!"); st.rerun()
            else:
                st.error("กรุณากรอกข้อมูลซอยหลักให้ครบถ้วน")

        st.divider()
        st.subheader("🗑️ จัดการข้อมูลเดิม")
        st.dataframe(mapping_df, use_container_width=True)
        # ... (ส่วนลบข้อมูลใส่รหัสยืนยันเหมือนเดิม) ...

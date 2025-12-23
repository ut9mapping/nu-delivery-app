import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime

# --- 1. ตั้งค่าการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery Master", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"❌ เชื่อมต่อ Google Sheets ไม่ได้: {e}")
        return None

# ฟังก์ชันโหลดข้อมูลที่ "ทนทาน" ต่อชื่อคอลัมน์ที่พิมพ์ผิด
def load_data_robust(sheet_name):
    sh = get_sheets()
    if not sh: return pd.DataFrame()
    try:
        ws = sh.worksheet(sheet_name)
        all_values = ws.get_all_values()
        if len(all_values) > 0:
            # ใช้แถวแรกเป็น Header และล้างช่องว่าง + ทำเป็นตัวพิมพ์เล็ก
            headers = [str(h).strip().lower() for h in all_values[0]]
            data = all_values[1:]
            
            # ตรวจสอบชื่อซ้ำ (Deduplicate)
            clean_headers = []
            for i, h in enumerate(headers):
                if h == "" or h in clean_headers:
                    clean_headers.append(f"{h if h != '' else 'col'}_{i}")
                else:
                    clean_headers.append(h)
            
            return pd.DataFrame(data, columns=clean_headers)
        return pd.DataFrame()
    except Exception as e:
        st.error(f"❌ โหลดแผ่นงาน {sheet_name} ไม่สำเร็จ: {e}")
        return pd.DataFrame()

# ฟังก์ชันช่วยกรองตัวเลือก Dropdown
def get_options(df, target_col, filters={}):
    if df.empty or target_col not in df.columns:
        return ["-- ไม่มีข้อมูล --"]
    
    temp_df = df.copy()
    for col, val in filters.items():
        if val and col in temp_df.columns:
            temp_df = temp_df[temp_df[col] == val]
    
    options = sorted(temp_df[target_col].unique().tolist())
    return [opt for opt in options if str(opt).strip() != ""]

# --- 2. ส่วนแสดงผลหน้าจอ ---
st.title("🛵 ระบบจัดการพิกัด (Fixed KeyError)")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน (User)", "⚙️ วิเคราะห์ข้อมูล (Admin)", "🔍 ค้นหา/นำทาง"])

# --- TAB 1: USER ---
with tab1:
    st.subheader("📝 บันทึกพิกัดใหม่")
    loc = streamlit_geolocation()
    lat, lon = loc.get('latitude'), loc.get('longitude')
    
    p_name = st.text_input("🏠 ชื่อสถานที่/บ้านเลขที่")
    note = st.text_area("🗒️ หมายเหตุ/จุดสังเกต")
    
    st.write("🖼️ รูปภาพ 3 มุม")
    c1, c2, c3 = st.columns(3)
    img1 = c1.file_uploader("รูปที่ 1", type=['jpg','png'], key="u1")
    img2 = c2.file_uploader("รูปที่ 2", type=['jpg','png'], key="u2")
    img3 = c3.file_uploader("รูปที่ 3", type=['jpg','png'], key="u3")

    if st.button("🚀 ส่งข้อมูลให้แอดมิน", use_container_width=True, type="primary"):
        if lat and p_name:
            try:
                sh = get_sheets()
                ws = sh.worksheet("Sheet1")
                imgs = ["Yes" if i else "No" for i in [img1, img2, img3]]
                # ข้อมูล 16 คอลัมน์ (A-P)
                new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, note, "รอวิเคราะห์"] + imgs + [""]*7
                ws.insert_row(new_row, index=2)
                st.success("✅ บันทึกสำเร็จ!")
            except Exception as e:
                st.error(f"บันทึกไม่สำเร็จ: {e}")
        else: st.warning("⚠️ กรุณาระบุชื่อสถานที่และพิกัด")

# --- TAB 2: ADMIN ---
with tab2:
    st.subheader("🛠️ การวิเคราะห์ข้อมูลสถานที่")
    df_raw = load_data_robust("Sheet1")
    df_map = load_data_robust("Mapping")
    
    # ตรวจสอบว่าคอลัมน์ status มีอยู่จริงไหม
    if 'status' in df_raw.columns:
        pending = df_raw[df_raw['status'] == "รอวิเคราะห์"]
        
        if not pending.empty:
            target_idx = st.selectbox("เลือกรายการที่จะวิเคราะห์:", pending.index, 
                                     format_func=lambda x: f"{pending.loc[x, 'place_name']}")
            
            # --- ส่วนการเลือกโครงสร้าง Mapping ---
            col1, col2 = st.columns(2)
            with col1:
                g = st.selectbox("1. ประตู", get_options(df_map, 'gate'))
                ma = st.selectbox("2. ซอยหลัก", get_options(df_map, 'main_alley', {'gate': g}))
            with col2:
                ms = st.selectbox("3. ฝั่งซอยหลัก", get_options(df_map, 'main_side', {'gate': g, 'main_alley': ma}))
                sa = st.selectbox("4. ซอยย่อย", get_options(df_map, 'sub_alley', {'gate': g, 'main_alley': ma}))

            if st.button("💾 บันทึกการวิเคราะห์"):
                try:
                    sh = get_sheets()
                    ws = sh.worksheet("Sheet1")
                    # หาเลขแถวใน Excel (Index ของ Pandas เริ่มที่ 0 + Header แถว 1 + Index เลื่อน 1 = +2)
                    row_num = int(target_idx) + 2
                    
                    # อัปเดต Status (คอลัมน์ F) และข้อมูลวิเคราะห์ (คอลัมน์ J-P)
                    ws.update_cell(row_num, 6, "วิเคราะห์แล้ว") # F
                    ws.update_cell(row_num, 10, g)   # J: gate
                    ws.update_cell(row_num, 13, ma)  # M: main_alley
                    ws.update_cell(row_num, 14, ms)  # N: main_side
                    ws.update_cell(row_num, 15, sa)  # O: sub_alley
                    
                    st.success("✅ อัปเดตข้อมูลสำเร็จ!")
                    st.rerun()
                except Exception as e:
                    st.error(f"อัปเดตล้มเหลว: {e}")
        else: st.info("🎉 ไม่มีข้อมูลค้างวิเคราะห์")
    else:
        st.error("❌ ไม่พบคอลัมน์ 'status' ใน Google Sheets แถวที่ 1")

# --- TAB 3: SEARCH ---
with tab3:
    st.subheader("🔍 ค้นหาและนำทาง")
    search_df = load_data_robust("Sheet1")
    if not search_df.empty:
        q = st.text_input("ค้นหา:")
        res = search_df[search_df.apply(lambda r: q.lower() in str(r.values).lower(), axis=1)]
        st.dataframe(res)

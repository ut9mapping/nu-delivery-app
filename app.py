import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk
import difflib
import re

# --- 1. ตั้งค่าการเชื่อมต่อ Google Sheets ---
st.set_page_config(page_title="NU Delivery: Smart Subset System", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"Error Connecting to Sheets: {e}")
        return None

def load_data(sheet_name="Sheet1"):
    sh = get_sheets()
    if not sh: return pd.DataFrame()
    ws = sh.worksheet(sheet_name)
    df = pd.DataFrame(ws.get_all_records())
    if not df.empty and 'lat' in df.columns:
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        return df.dropna(subset=['lat', 'lon']) if sheet_name == "Sheet1" else df
    return df

# --- 2. 🧠 SUPER AI SEARCH LOGIC (Fuzzy + Number Match) ---
def super_ai_search(df, query):
    if not query:
        return df, "สวัสดีครับ! พิมพ์ถามสิ่งที่ต้องการหาได้เลย เช่น 'บ้านเลขที่ 12/3' หรือ 'ซอย NU Plaza'"
    
    q = query.lower().strip()
    digits = re.findall(r'\d+', q)
    
    def get_score(row):
        score = 0
        name = str(row.get('place_name', '')).lower()
        note = str(row.get('note', '')).lower()
        gate = str(row.get('gate', '')).lower()
        alley = str(row.get('main_alley', '')).lower()
        
        full_text = f"{name} {note} {gate} {alley}".lower()
        
        if q in full_text: score += 10 # ค้นตรงตัว
        for n in digits:
            if n in full_text: score += 15 # ค้นเลขที่บ้าน/ตึก
            
        # ค้นหาคำใกล้เคียง (พิมพ์ผิดนิดหน่อยก็เจอ)
        similarity = difflib.SequenceMatcher(None, q, name).ratio()
        if similarity > 0.6: score += (similarity * 10)
        
        return score

    temp_df = df.copy()
    temp_df['ai_score'] = temp_df.apply(get_score, axis=1)
    results = temp_df[temp_df['ai_score'] > 2].sort_values(by='ai_score', ascending=False)
    
    if not results.empty:
        msg = f"🤖 วิเคราะห์แล้วครับ พบสถานที่ใกล้เคียงคือ **{results.iloc[0]['place_name']}**"
    else:
        msg = "😅 ไม่พบพิกัดที่ระบุ ลองพิมพ์สั้นๆ หรือใช้เลขประตูช่วยครับ"
    return results, msg

# --- 3. UI MAIN INTERFACE ---
st.title("🛵 NU Delivery Pro: Smart Subset & AI")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน", "⚙️ จัดการข้อมูล (Admin)", "🔍 ค้นหาอัจฉริยะ"])

# --- TAB 1: USER INPUT ---
with tab1:
    st.subheader("📝 บันทึกพิกัดใหม่")
    location = streamlit_geolocation()
    lat, lon = location.get('latitude'), location.get('longitude')
    
    if lat: st.success(f"📍 พิกัดพร้อม: {lat}, {lon}")
    else: st.warning("📡 กรุณาเปิด GPS และกดยอมรับสิทธิ์ที่เบราว์เซอร์")

    p_name = st.text_input("🏠 ชื่อสถานที่ / ตึกแถว / บ้านเลขที่")
    user_note = st.text_area("🗒️ จุดสังเกตดิบจากหน้างาน (User Note)")
    
    st.write("🖼️ อัปโหลดรูปภาพประกอบ (3 ช่อง)")
    c1, c2, c3 = st.columns(3)
    img1 = c1.file_uploader("รูป 1", type=['jpg','png'], key="u1")
    img2 = c2.file_uploader("รูป 2", type=['jpg','png'], key="u2")
    img3 = c3.file_uploader("รูป 3", type=['jpg','png'], key="u3")

    if st.button("🚀 ส่งข้อมูลให้แอดมิน", use_container_width=True, type="primary"):
        if lat and p_name:
            ws = get_sheets().worksheet("Sheet1")
            imgs = ["Yes" if i else "No" for i in [img1, img2, img3]]
            # บันทึกข้อมูลเบื้องต้นลงคอลัมน์ A-I (รอแอดมินมาเติม J-P)
            new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, user_note, "รอวิเคราะห์"] + imgs + [""]*7
            ws.insert_row(new_row, index=2)
            st.balloons()
            st.success("✅ ข้อมูลส่งถึงแอดมินแล้ว!")
        else: st.error("⚠️ กรุณาระบุชื่อสถานที่และเปิด GPS")

# --- TAB 2: ADMIN SUBSET SYSTEM (หัวใจสำคัญ) ---
with tab2:
    pwd = st.text_input("รหัสผ่านแอดมิน", type="password")
    if pwd == "9999":
        st.subheader("⚙️ โต๊ะทำงานแอดมิน: จัดกลุ่มซับเซต")
        
        df_mapping = load_data("Mapping")
        df_main = load_data("Sheet1")
        
        if not df_main.empty and not df_mapping.empty:
            # กรองเฉพาะงานที่ยังไม่ตรวจ
            pending_tasks = df_main[df_main['status'] == "รอวิเคราะห์"]
            
            if pending_tasks.empty:
                st.info("ไม่มีงานค้างในขณะนี้")
            
            for idx, row in pending_tasks.iterrows():
                actual_row_num = int(idx) + 2
                with st.expander(f"🆕 ตรวจสอบ: {row['place_name']} ({row['timestamp']})"):
                    st.warning(f"💬 Note: {row['note']}")
                    
                    # --- START CASCADING LOGIC (SUBSET) ---
                    m_df = df_mapping.copy()
                    
                    col_a, col_b, col_c = st.columns(3)
                    
                    with col_a:
                        # 1. เลือกประตู
                        gate_list = sorted(m_df['gate'].unique())
                        sel_gate = st.selectbox("เลือกประตู:", gate_list, key=f"g_{idx}")
                        m_df = m_df[m_df['gate'] == sel_gate]
                        
                        # 2. เลือกถนน (กรองตามประตู)
                        road_list = sorted(m_df['road'].unique())
                        sel_road = st.selectbox("เลือกถนน:", road_list, key=f"r_{idx}")
                        m_df = m_df[m_df['road'] == sel_road]
                        
                    with col_b:
                        # 3. ฝั่งถนน
                        rs_list = sorted(m_df['road_side'].unique())
                        sel_rs = st.selectbox("ฝั่งถนน:", rs_list, key=f"rs_{idx}")
                        m_df = m_df[m_df['road_side'] == sel_rs]
                        
                        # 4. ซอยหลัก
                        ma_list = sorted(m_df['main_alley'].unique())
                        sel_ma = st.selectbox("ซอยหลัก:", ma_list, key=f"ma_{idx}")
                        m_df = m_df[m_df['main_alley'] == sel_ma]
                        
                    with col_c:
                        # 5. ฝั่งซอยหลัก
                        ms_list = sorted(m_df['main_side'].unique())
                        sel_ms = st.selectbox("ฝั่งซอยหลัก:", ms_list, key=f"ms_{idx}")
                        m_df = m_df[m_df['main_side'] == sel_ms]
                        
                        # 6. ซอยย่อย
                        sa_list = sorted(m_df['sub_alley'].unique())
                        sel_sa = st.selectbox("ซอยย่อย:", sa_list, key=f"sa_{idx}")
                        m_df = m_df[m_df['sub_alley'] == sel_sa]
                    
                    # 7. ฝั่งซอยย่อย
                    ss_list = sorted(m_df[m_df['sub_alley'] == sel_sa]['sub_side'].unique())
                    sel_ss = st.selectbox("ฝั่งซอยย่อย:", ss_list, key=f"ss_{idx}")
                    
                    final_admin_note = st.text_area("สรุปจุดสังเกตใหม่ (ฉบับแอดมิน):", value=row['note'], key=f"an_{idx}")
                    
                    if st.button("💾 บันทึกซับเซตลงฐานข้อมูล", key=f"save_{idx}", use_container_width=True):
                        ws = get_sheets().worksheet("Sheet1")
                        # อัปเดตข้อมูลทั้ง 7 ระดับลงคอลัมน์ J-P
                        ws.update_cell(actual_row_num, 5, final_admin_note) # Note (E)
                        ws.update_cell(actual_row_num, 6, "วิเคราะห์แล้ว") # Status (F)
                        ws.update_cell(actual_row_num, 10, sel_gate) # J
                        ws.update_cell(actual_row_num, 11, sel_road) # K
                        ws.update_cell(actual_row_num, 12, sel_rs)   # L
                        ws.update_cell(actual_row_num, 13, sel_ma)   # M
                        ws.update_cell(actual_row_num, 14, sel_ms)   # N
                        ws.update_cell(actual_row_num, 15, sel_sa)   # O
                        ws.update_cell(actual_row_num, 16, sel_ss)   # P
                        st.success("✅ จัดหมวดหมู่สำเร็จ!")
                        st.rerun()

# --- TAB 3: AI SEARCH & MAP ---
with tab3:
    st.subheader("🔍 ค้นหาพิกัดและอาณาเขตข้อมูล")
    user_q = st.text_input("💬 พิมพ์คุยกับ AI:", placeholder="เช่น 'หอพักใกล้ประตู 4 ซอยโซนเซเว่น'")
    
    full_data = load_data("Sheet1")
    if not full_data.empty:
        search_res, ai_msg = super_ai_search(full_data, user_q)
        
        st.chat_message("assistant").write(ai_msg)
        
        if not search_res.empty:
            # แผนที่ภาพรวม (Hover ได้)
            st.pydeck_chart(pdk.Deck(
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                initial_view_state=pdk.ViewState(latitude=search_res['lat'].mean(), longitude=search_res['lon'].mean(), zoom=15),
                layers=[pdk.Layer("ScatterplotLayer", search_res, get_position='[lon, lat]', get_color='[255, 75, 75, 200]', get_radius=40, pickable=True)],
                tooltip={"html": "<b>{place_name}</b><br/>ประตู: {gate}<br/>ซอย: {main_alley}<br/>โน้ต: {note}"}
            ))
            
            # รายละเอียดรายบุคคล
            for _, r in search_res.iterrows():
                with st.expander(f"📍 {r['place_name']} (วิเคราะห์แล้วโดย AI)"):
                    ca, cb = st.columns(2)
                    with ca:
                        st.write(f"🏠 **ซอย:** {r['main_alley']} | **ซอยย่อย:** {r['sub_alley']}")
                        st.write(f"📝 **รายละเอียด:** {r['note']}")
                        st.link_button("🚗 นำทางด้วย Google Maps", f"https://www.google.com/maps?q={r['lat']},{r['lon']}")
                    with cb:
                        st.pydeck_chart(pdk.Deck(
                            map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
                            initial_view_state=pdk.ViewState(latitude=r['lat'], longitude=r['lon'], zoom=18),
                            layers=[pdk.Layer("ScatterplotLayer", pd.DataFrame([r]), get_position='[lon, lat]', get_color='[255,0,0]', get_radius=10)]
                        ))

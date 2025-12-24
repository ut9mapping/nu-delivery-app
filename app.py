import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk
import difflib  # สำหรับแก้คำพิมพ์ผิด (Fuzzy Matching)
import re      # สำหรับตรวจจับตัวเลข/เลขที่บ้าน

# --- 1. การตั้งค่าระบบและการเชื่อมต่อ ---
st.set_page_config(page_title="NU Delivery: Smart AI Pro", layout="wide")

# พิกัดกลาง (ม.นเรศวร)
DEFAULT_LAT, DEFAULT_LON = 16.7469, 100.1914

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except Exception as e:
        st.error(f"เชื่อมต่อ Google Sheets ไม่ได้: {e}")
        return None

# โหลดข้อมูลหลัก (Sheet1)
def load_main_data():
    sh = get_sheets()
    if not sh: return pd.DataFrame()
    ws = sh.worksheet("Sheet1")
    df = pd.DataFrame(ws.get_all_records())
    if not df.empty:
        df.columns = [c.strip() for c in df.columns]
        df['lat'] = pd.to_numeric(df['lat'], errors='coerce')
        df['lon'] = pd.to_numeric(df['lon'], errors='coerce')
        return df.dropna(subset=['lat', 'lon'])
    return df

# ✨ ฟังก์ชันดึงตัวเลือกจากชีต Mapping (ดึงจากภาพที่คุณส่งมา)
def get_mapping_options():
    try:
        sh = get_sheets()
        ws = sh.worksheet("Mapping")
        df_map = pd.DataFrame(ws.get_all_records())
        # ทำความสะอาดข้อมูล: กรองค่าว่างและเอาเฉพาะค่าที่ไม่ซ้ำ
        def clean_opt(col):
            return sorted([str(x) for x in df_map[col].unique() if x and x != '-'])

        return {
            "gate": clean_opt("gate"),
            "road": clean_opt("road"),
            "road_side": clean_opt("road_side"),
            "main_alley": clean_opt("main_alley"),
            "main_side": clean_opt("main_side"),
            "sub_alley": clean_opt("sub_alley"),
            "sub_side": clean_opt("sub_side")
        }
    except:
        return {k: ["-"] for k in ["gate", "road", "road_side", "main_alley", "main_side", "sub_alley", "sub_side"]}

# --- 2. 🧠 SUPER AI SEARCH LOGIC (ฉลาด เข้าใจคำถาม และคำผิด) ---
def super_ai_search(df, query):
    if not query: 
        return df, "สวัสดีครับ! ผมคือ AI ผู้ช่วยหาพิกัด พิมพ์ถามได้เลย เช่น 'บ้านเลขที่ 55' หรือ 'หอพักแถวประตู 4'"
    
    q = query.lower().strip()
    digits = re.findall(r'\d+', q) # สกัดตัวเลขออกมาสำหรับหาเลขที่บ้าน
    
    def get_score(row):
        score = 0
        name = str(row.get('place_name','')).lower()
        note = str(row.get('note','')).lower()
        full_text = f"{name} {note} {row.get('gate','')} {row.get('main_alley','')} {row.get('sub_alley','')}".lower()
        
        if q in full_text: score += 10 # ค้นหาแบบตรงตัว
        for num in digits:
            if num in full_text: score += 15 # ค้นหาเลขที่บ้าน
            
        # Fuzzy Match (พิมพ์ผิด)
        similarity = difflib.SequenceMatcher(None, q, name).ratio()
        if similarity > 0.5: score += (similarity * 10)
        
        return score

    df_res = df.copy()
    df_res['ai_score'] = df_res.apply(get_score, axis=1)
    results = df_res[df_res['ai_score'] > 2].sort_values(by='ai_score', ascending=False)
    
    if not results.empty:
        msg = f"🤖 ผมวิเคราะห์แล้วครับ พบสถานที่ที่ใกล้เคียงที่สุดคือ **{results.iloc[0]['place_name']}**"
    else:
        msg = "😅 ขออภัยครับ ผมยังไม่เจอข้อมูลที่ตรงตามนั้น ลองระบุชื่อสั้นๆ ดูครับ"
    return results, msg

# --- 3. หน้าจอหลักและการจัดการข้อมูล ---
st.title("🛵 NU Delivery Pro (Super AI + Mapping)")

tab1, tab2, tab3 = st.tabs(["📌 บันทึกหน้างาน (User)", "⚙️ วิเคราะห์ข้อมูล (Admin)", "🔍 ค้นหาและอาณาเขต"])

# --- TAB 1: USER (พิกัด + รูป 3 ช่อง) ---
with tab1:
    st.subheader("📝 ส่งข้อมูลพิกัดใหม่")
    loc = streamlit_geolocation()
    lat, lon = loc.get('latitude'), loc.get('longitude')
    
    if lat: st.success(f"📍 GPS Lock: {lat}, {lon}")
    else: st.warning("📡 กำลังรอพิกัด GPS... (โปรดกดยอมรับสิทธิ์)")

    p_name = st.text_input("🏠 ชื่อสถานที่ / ตึกแถว / บ้านเลขที่")
    note = st.text_area("🗒️ จุดสังเกตดิบจากหน้างาน (User Note)")
    
    st.write("🖼️ อัปโหลดรูปภาพประกอบ (3 รูป)")
    c1, c2, c3 = st.columns(3)
    img1 = c1.file_uploader("รูป 1", type=['jpg','png'], key="u1")
    img2 = c2.file_uploader("รูป 2", type=['jpg','png'], key="u2")
    img3 = c3.file_uploader("รูป 3", type=['jpg','png'], key="u3")

    if st.button("🚀 ส่งข้อมูลให้แอดมิน", use_container_width=True, type="primary"):
        if lat and p_name:
            ws = get_sheets().worksheet("Sheet1")
            has_imgs = ["Yes" if i else "No" for i in [img1, img2, img3]]
            # บันทึกข้อมูลเบื้องต้น
            new_row = [datetime.now().strftime("%Y-%m-%d %H:%M"), lat, lon, p_name, note, "รอวิเคราะห์"] + has_imgs + [""]*7
            ws.insert_row(new_row, index=2)
            st.balloons()
            st.success("✅ บันทึกแล้ว! รอแอดมินประมวลผลแยกหมวดหมู่")
        else: st.error("⚠️ ข้อมูลไม่ครบ")

# --- TAB 2: ADMIN (ดึงตัวเลือกจากชีต Mapping) ---
with tab2:
    pwd = st.text_input("รหัสผ่านแอดมิน", type="password")
    if pwd == "9999":
        st.subheader("⚙️ โต๊ะทำงานแอดมิน: ประมวลผลจากชีต Mapping")
        
        # ดึงตัวเลือกจากชีต Mapping มาแสดงผล
        opts = get_mapping_options()
        df_admin = load_main_data()
        
        if not df_admin.empty:
            for idx, row in df_admin.iterrows():
                actual_idx = int(idx) + 2
                status_color = "🔵" if row['status'] == "รอวิเคราะห์" else "🟢"
                
                with st.expander(f"{status_color} {row['place_name']} | {row['timestamp']}"):
                    st.info(f"💬 โน้ตจากยูสเซอร์: {row['note']}")
                    
                    # ส่วนการเลือกข้อมูลที่อ้างอิงจากชีต Mapping
                    st.write("**🧠 เลือกข้อมูลตามโครงสร้างพื้นที่ (Mapping):**")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        v_gate = st.selectbox("1. ประตู:", opts['gate'], key=f"g_{idx}")
                        v_road = st.selectbox("2. ถนน:", opts['road'], key=f"r_{idx}")
                    with col2:
                        v_road_side = st.selectbox("3. ฝั่งถนน:", opts['road_side'], key=f"rs_{idx}")
                        v_main_alley = st.selectbox("4. ซอยหลัก:", opts['main_alley'], key=f"ma_{idx}")
                    with col3:
                        v_main_side = st.selectbox("5. ฝั่งซอย:", opts['main_side'], key=f"ms_{idx}")
                        v_sub_alley = st.selectbox("6. ซอยย่อย:", opts['sub_alley'], key=f"sa_{idx}")
                    
                    v_note = st.text_area("🗒️ สรุปจุดสังเกตใหม่ (ฉบับแอดมิน):", value=row['note'], key=f"fn_{idx}")
                    
                    btn_sv, btn_dl = st.columns(2)
                    if btn_sv.button("💾 บันทึกการวิเคราะห์", key=f"save_{idx}", use_container_width=True):
                        ws = get_sheets().worksheet("Sheet1")
                        # อัปเดตข้อมูลลง Sheet1 ตามลำดับคอลัมน์ของคุณ
                        updates = [
                            {'range': f'E{actual_idx}', 'values': [[v_note]]},
                            {'range': f'F{actual_idx}', 'values': [["วิเคราะห์แล้ว"]]},
                            {'range': f'J{actual_idx}', 'values': [[v_gate]]},
                            {'range': f'K{actual_idx}', 'values': [[v_road]]},
                            {'range': f'L{actual_idx}', 'values': [[v_road_side]]},
                            {'range': f'M{actual_idx}', 'values': [[v_main_alley]]},
                            {'range': f'N{actual_idx}', 'values': [[v_main_side]]},
                            {'range': f'O{actual_idx}', 'values': [[v_sub_alley]]},
                        ]
                        for up in updates: ws.update(up['range'], up['values'])
                        st.success("✅ วิเคราะห์ข้อมูลสำเร็จ!")
                        st.rerun()

                    if btn_dl.button("🗑️ ลบทิ้ง", key=f"del_{idx}", use_container_width=True):
                        get_sheets().worksheet("Sheet1").delete_rows(actual_idx)
                        st.warning("ลบข้อมูลแล้ว")
                        st.rerun()

# --- TAB 3: SEARCH & MAP (Super AI) ---
with tab3:
    st.subheader("🔍 ผู้ช่วย AI ค้นหาและดูอาณาเขต")
    q = st.text_input("💬 ถาม AI:", placeholder="เช่น 'หอพักที่อยู่ประตู 4 ซอยโซนเซเว่น'")
    
    raw_df = load_main_data()
    if not raw_df.empty:
        results, ai_msg = super_ai_search(raw_df, q)
        
        st.chat_message("assistant").write(ai_msg)
        
        # แผนที่อาณาเขต
        st.pydeck_chart(pdk.Deck(
            map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
            initial_view_state=pdk.ViewState(latitude=results['lat'].mean() if not results.empty else DEFAULT_LAT, 
                                           longitude=results['lon'].mean() if not results.empty else DEFAULT_LON, zoom=15),
            layers=[pdk.Layer("ScatterplotLayer", results, get_position='[lon, lat]', get_color='[255, 75, 75, 180]', get_radius=40, pickable=True)],
            tooltip={"html": "<b>{place_name}</b><br/>ประตู: {gate}<br/>ซอย: {main_alley}<br/>หมายเหตุ: {note}"}
        ))
        
        for _, r in results.iterrows():
            with st.expander(f"📌 {r['place_name']} - {r['gate']}"):
                ca, cb = st.columns(2)
                with ca:
                    st.write(f"🏠 **ซอย:** {r.get('main_alley','-')} | **ซอยย่อย:** {r.get('sub_alley','-')}")
                    st.write(f"📝 **แอดมินสรุป:** {r['note']}")
                    st.link_button("🚗 นำทาง", f"https://www.google.com/maps?q={r['lat']},{r['lon']}")
                with cb:
                    st.pydeck_chart(pdk.Deck(
                        map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
                        initial_view_state=pdk.ViewState(latitude=r['lat'], longitude=r['lon'], zoom=18),
                        layers=[pdk.Layer("ScatterplotLayer", pd.DataFrame([r]), get_position='[lon, lat]', get_color='[255,0,0]', get_radius=10)]
                    ))

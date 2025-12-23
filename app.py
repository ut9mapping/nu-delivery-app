import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk

# --- 1. การตั้งค่าระบบ ---
st.set_page_config(page_title="NU Delivery: AI Brain", layout="wide")

def get_sheets():
    try:
        scope = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(st.secrets["gcp_service_account"], scopes=scope)
        return gspread.authorize(creds).open_by_key(st.secrets["SHEET_ID"])
    except: return None

def load_data():
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

# --- 2. AI Logic: ระบบคิดวิเคราะห์แทนการหาคำตรงๆ ---
def ai_brain_search(df, user_query):
    if not user_query: return df, "พิมพ์คำถามของคุณได้เลยครับ"
    
    # 🧠 จำลอง AI วิเคราะห์ Intent (ความต้องการ)
    q = user_query.lower()
    
    # วิเคราะห์เงื่อนไขพิเศษ
    is_urgent = "ด่วน" in q or "รอวิเคราะห์" in q
    has_gate = "ประตู" in q
    
    # คำนวณคะแนนความฉลาด (Smart Scoring)
    def score_row(row):
        score = 0
        full_text = f"{row['place_name']} {row['note']} {row['gate']} {row['main_alley']} {row['status']}".lower()
        
        # 1. เช็กความตรงของคำ
        for word in q.split():
            if word in full_text: score += 1
            
        # 2. เช็ก Intent (ความฉลาดเสริม)
        if "ประตู" in q:
            for i in range(1, 5):
                if f"ประตู {i}" in q and f"ประตู {i}" in str(row['gate']):
                    score += 5 # ให้ความสำคัญกับเลขประตูมากเป็นพิเศษ
                    
        if is_urgent and row['status'] == "รอวิเคราะห์":
            score += 10 # ถ้าบ่นว่าด่วน หรือถามหาที่ยังไม่ตรวจ จะยกขึ้นมาให้ก่อน
            
        return score

    df['ai_score'] = df.apply(score_row, axis=1)
    results = df[df['ai_score'] > 0].sort_values(by='ai_score', ascending=False)
    
    # สร้างคำตอบแบบ AI (AI Insight)
    if not results.empty:
        top_pick = results.iloc[0]['place_name']
        insight = f"🤖 ผมวิเคราะห์แล้วครับ พบที่เกี่ยวข้อง {len(results)} แห่ง โดยเฉพาะ '{top_pick}' ดูจะตรงกับที่คุณต้องการที่สุดครับ"
    else:
        insight = "😔 ขออภัยครับ ผมยังไม่เจอสถานที่ที่มีลักษณะตรงตามที่ระบุ ลองเปลี่ยนคำค้นหาดูนะครับ"
        
    return results, insight

# --- 3. UI หน้าจอ ---
st.title("🧠 NU Delivery: AI Intelligent System")

tab1, tab2, tab3 = st.tabs(["📌 รับงาน/ส่งพิกัด", "⚙️ โต๊ะประมวลผลแอดมิน", "🔍 ผู้ช่วยอัจฉริยะ (AI)"])

# --- TAB 2: โต๊ะประมวลผลแอดมิน (เน้นการวิเคราะห์ข้อมูลดิบ) ---
with tab2:
    pwd = st.text_input("Admin Password", type="password")
    if pwd == "9999":
        df_all = load_data()
        st.subheader("💡 แอดมินประมวลผลข้อมูล")
        
        # แสดงรายการที่ต้องจัดการ (เรียงตามความใหม่)
        for idx, row in df_all.sort_index(ascending=False).iterrows():
            actual_idx = int(idx) + 2
            with st.expander(f"📍 {row['place_name']} | สถานะ: {row['status']}"):
                st.write("**ข้อมูลที่ได้รับมา:**")
                st.caption(f"📅 เวลา: {row['timestamp']} | 🌍 พิกัด: {row['lat']}, {row['lon']}")
                st.info(f"💬 โน้ตจากผู้ใช้: {row['note']}")
                
                st.write("**🛠️ ส่วนการประมวลผล (แอดมินกรอก):**")
                c1, c2, c3 = st.columns(3)
                with c1:
                    new_gate = st.selectbox("ระบุประตู:", ["ประตู 1", "ประตู 2", "ประตู 3", "ประตู 4", "อื่นๆ"], 
                                           index=0, key=f"g_{idx}")
                with c2:
                    new_alley = st.text_input("ชื่อซอย/ถนน:", value=row.get('main_alley',''), key=f"m_{idx}")
                with c3:
                    new_status = st.selectbox("สถานะการตรวจ:", ["รอวิเคราะห์", "วิเคราะห์แล้ว", "ข้อมูลไม่ชัดเจน"], key=f"s_{idx}")
                
                new_note = st.text_area("สรุปรายละเอียดอาคาร/โครงการ (ฉบับแอดมิน):", value=row['note'], key=f"n_{idx}")
                
                save, delete = st.columns(2)
                if save.button("✅ บันทึกการประมวลผล", key=f"btn_s_{idx}", use_container_width=True):
                    ws = get_sheets().worksheet("Sheet1")
                    ws.update_cell(actual_idx, 6, new_status)
                    ws.update_cell(actual_idx, 5, new_note)
                    ws.update_cell(actual_idx, 10, new_gate)
                    ws.update_cell(actual_idx, 13, new_alley)
                    st.success("ประมวลผลเสร็จสิ้น!")
                    st.rerun()
                
                if delete.button("🗑️ ลบพิกัดนี้", key=f"btn_d_{idx}", use_container_width=True):
                    get_sheets().worksheet("Sheet1").delete_rows(actual_idx)
                    st.warning("ลบพิกัดออกจากระบบแล้ว")
                    st.rerun()

# --- TAB 3: ผู้ช่วยอัจฉริยะ (AI SEARCH) ---
with tab3:
    st.subheader("🤝 คุยกับ AI ผู้ช่วยหาพิกัด")
    search_q = st.text_input("💬 คุณกำลังมองหาสถานที่แบบไหนครับ?", placeholder="เช่น อยากได้ตึกแถวแถวประตู 4 ที่ยังไม่ได้ตรวจ...")
    
    raw_df = load_data()
    if not raw_df.empty:
        results, ai_message = ai_brain_search(raw_df, search_q)
        
        # แสดงความเห็นของ AI
        st.chat_message("assistant").write(ai_message)
        
        if not results.empty:
            # แผนที่รวม
            st.write("🌍 **อาณาเขตพื้นที่ที่เกี่ยวข้อง**")
            st.pydeck_chart(pdk.Deck(
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                initial_view_state=pdk.ViewState(latitude=results['lat'].mean(), longitude=results['lon'].mean(), zoom=14),
                layers=[pdk.Layer("ScatterplotLayer", results, get_position='[lon, lat]', get_color='[0, 128, 255, 160]', get_radius=50, pickable=True)],
                tooltip={"html": "<b>{place_name}</b><br/>{gate} - {main_alley}"}
            ))
            
            # รายละเอียดพร้อมภาพจำลอง
            for _, r in results.iterrows():
                with st.expander(f"📍 {r['place_name']} (วิเคราะห์แล้วโดย AIว่าเกี่ยวข้อง)"):
                    ca, cb = st.columns([1, 1])
                    with ca:
                        st.markdown(f"**🚪 ประตู:** {r['gate']} | **🛣️ ถนน:** {r['main_alley']}")
                        st.markdown(f"**📝 รายละเอียด:** {r['note']}")
                        st.link_button("🚗 นำทางทันที", f"https://www.google.com/maps?q={r['lat']},{r['lon']}")
                    with cb:
                        # ภาพดาวเทียมให้เห็นอาคารจริงๆ
                        st.pydeck_chart(pdk.Deck(
                            map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
                            initial_view_state=pdk.ViewState(latitude=r['lat'], longitude=r['lon'], zoom=18),
                            layers=[pdk.Layer("ScatterplotLayer", pd.DataFrame([r]), get_position='[lon, lat]', get_color='[255,0,0]', get_radius=10)]
                        ))

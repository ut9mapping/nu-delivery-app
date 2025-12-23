import streamlit as st
import gspread
import pandas as pd
from google.oauth2.service_account import Credentials
from streamlit_geolocation import streamlit_geolocation
from datetime import datetime
import pydeck as pdk
import difflib  # เพิ่มมาเพื่อช่วยเรื่องพิมพ์ผิด (Fuzzy Match)
import re      # เพิ่มมาเพื่อช่วยตรวจจับตัวเลข (เลขที่บ้าน)

# --- 1. การตั้งค่าระบบ ---
st.set_page_config(page_title="NU Delivery: Super AI", layout="wide")

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

# --- 2. 🧠 SUPER AI BRAIN (ตัวใหม่: เข้าใจคำถาม/ตัวเลข/คำผิด) ---
def super_ai_search(df, query):
    if not query: return df, "สวัสดีครับ! ระบุชื่อสถานที่ หรือเลขที่บ้านได้เลย ผมจะช่วยหาให้ครับ"
    
    q = query.lower().strip()
    
    # ดึงตัวเลขออกมา (เผื่อหาเลขที่บ้าน)
    numbers_in_query = re.findall(r'\d+', q)
    
    def calculate_smart_score(row):
        score = 0
        name = str(row['place_name']).lower()
        note = str(row['note']).lower()
        gate = str(row['gate']).lower()
        full_text = f"{name} {note} {gate} {row['main_alley']}".lower()
        
        # 1. ค้นหาคำตรงตัว (Exact Match)
        if q in full_text:
            score += 10
        
        # 2. ค้นหาเลขที่บ้าน (Number Match)
        for num in numbers_in_query:
            if num in full_text:
                score += 15 # ให้คะแนนสูงมากถ้าเลขตรงกัน
        
        # 3. ตรวจสอบคำใกล้เคียง (Fuzzy Match - ป้องกันการพิมพ์ผิด)
        words = q.split()
        for word in words:
            # หาค่าความคล้ายคลึงระหว่างคำค้น กับ ชื่อสถานที่
            similarity = difflib.SequenceMatcher(None, word, name).ratio()
            if similarity > 0.6: # ถ้าคล้ายกันมากกว่า 60%
                score += (similarity * 8)
                
        return score

    df_result = df.copy()
    df_result['ai_score'] = df_result.apply(calculate_smart_score, axis=1)
    results = df_result[df_result['ai_score'] > 2].sort_values(by='ai_score', ascending=False)
    
    # --- สร้างคำตอบจาก AI ---
    if not results.empty:
        best_match = results.iloc[0]
        score = best_match['ai_score']
        
        if q in best_match['place_name'].lower():
            msg = f"✅ เจอแล้วครับ! **{best_match['place_name']}** ตรงตามที่คุณค้นหาเลย"
        elif score > 10:
            msg = f"🤖 ผมหาพิกัดที่ใกล้เคียงที่สุดให้แล้วครับ คือ **{best_match['place_name']}** (วิเคราะห์จากเลขที่บ้านหรือจุดสังเกต)"
        else:
            msg = f"🤔 คุณน่าจะหมายถึง **{best_match['place_name']}** หรือเปล่าครับ? (ผมหาจากคำที่ใกล้เคียงที่สุด)"
    else:
        msg = "😅 ผมหาไม่เจอเลยครับ ลองพิมพ์ชื่อสั้นๆ หรือระบุแค่เลขประตูดูไหมครับ?"
        
    return results, msg

# --- 3. ส่วนการแสดงผล ---
st.title("🧠 NU Delivery: Super AI Assistant")

tab1, tab2, tab3 = st.tabs(["📌 บันทึก (User)", "⚙️ จัดการ (Admin)", "🔍 ค้นหาอัจฉริยะ"])

# (Tab 1 & 2 ใช้โค้ดเดิมได้เลย เพื่อความกระชับผมขอโชว์ Tab 3 ที่อัปเกรดแล้วครับ)

with tab3:
    st.subheader("💬 คุยกับผู้ช่วย AI (พิมพ์ผิดก็หาเจอ)")
    user_q = st.text_input("ถาม AI:", placeholder="เช่น 'บ้านเลขที่ 123' หรือ 'ส้มตำป้าไก่' (พิมพ์ผิดนิดหน่อยไม่เป็นไร)")
    
    data = load_data()
    if not data.empty:
        res, ai_msg = super_ai_search(data, user_q)
        
        with st.chat_message("assistant"):
            st.write(ai_msg)
            
        if not res.empty:
            # แผนที่ Hover Tooltip
            st.pydeck_chart(pdk.Deck(
                map_style="https://basemaps.cartocdn.com/gl/positron-gl-style/style.json",
                initial_view_state=pdk.ViewState(latitude=res['lat'].mean(), longitude=res['lon'].mean(), zoom=15),
                layers=[pdk.Layer("ScatterplotLayer", res, get_position='[lon, lat]', get_color='[255, 75, 75, 200]', get_radius=40, pickable=True)],
                tooltip={"html": "<b>{place_name}</b><br/>{gate}<br/>{note}"}
            ))
            
            for _, r in res.iterrows():
                with st.expander(f"📍 {r['place_name']} - {r['gate']}"):
                    c1, c2 = st.columns(2)
                    with c1:
                        st.write(f"**ประตู:** {r['gate']} | **ซอย:** {r['main_alley']}")
                        st.write(f"**โน้ต:** {r['note']}")
                        st.link_button("🚗 ไปที่นี่", f"https://www.google.com/maps?q={r['lat']},{r['lon']}")
                    with c2:
                        # ดาวเทียมซูม
                        st.pydeck_chart(pdk.Deck(
                            map_style="https://basemaps.cartocdn.com/gl/voyager-gl-style/style.json",
                            initial_view_state=pdk.ViewState(latitude=r['lat'], longitude=r['lon'], zoom=18),
                            layers=[pdk.Layer("ScatterplotLayer", pd.DataFrame([r]), get_position='[lon, lat]', get_color='[255,0,0]', get_radius=10)]
                        ))

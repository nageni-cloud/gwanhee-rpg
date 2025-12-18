import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import plotly.express as px
import requests
import random

# ==========================================
# 1. 구글 시트 연동 (가챠 데이터 추가)
# ==========================================
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "Gwanhee_Data" 

@st.cache_resource
def connect_to_sheet():
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    else:
        creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", SCOPE)
    client = gspread.authorize(creds)
    sh = client.open(SHEET_NAME)
    
    # 탭 연결 (없으면 생성)
    try: ws_status = sh.worksheet("Status")
    except: ws_status = sh.add_worksheet("Status", 10, 5)
    
    try: ws_logs = sh.worksheet("Logs")
    except: 
        ws_logs = sh.add_worksheet("Logs", 1000, 5)
        ws_logs.append_row(["Time", "Action", "XP", "Value"])
        
    # [NEW] 포켓몬 도감 탭 생성
    try: ws_col = sh.worksheet("Collection")
    except:
        ws_col = sh.add_worksheet("Collection", 1000, 5)
        ws_col.append_row(["ID", "Name", "Date", "Rarity"])

    return ws_status, ws_logs, ws_col

try: ws_status, ws_logs, ws_col = connect_to_sheet()
except Exception as e: st.error(f"❌ 연결 실패: {e}"); st.stop()

# ==========================================
# 2. 데이터 로드 (골드 계산 추가)
# ==========================================
def calculate_status_from_logs(logs_data, collection_data):
    total_xp = 0
    stats = {"STR": 0, "AGI": 0, "INT": 0, "WILL": 0, "LUCK": 0}
    
    # 1. 경험치 & 스탯 계산
    for log in logs_data:
        try:
            xp = int(log.get("XP", 0)) if isinstance(log, dict) else int(log[2])
            act = log.get("Action", "") if isinstance(log, dict) else log[1]
            total_xp += xp
            
            if "푸쉬업" in act or "스쿼트" in act: stats["STR"] += xp
            elif "달리기" in act: stats["AGI"] += xp
            elif "자기계발" in act or "독서" in act: stats["INT"] += xp
            elif "무지출" in act or "물" in act or "명상" in act: stats["WILL"] += xp
            elif "청소" in act: stats["LUCK"] += xp
        except: continue

    # 2. 레벨 계산
    level = 1
    current_xp = total_xp
    while True:
        req_xp = level * 100
        if current_xp >= req_xp: current_xp -= req_xp; level += 1
        else: break
            
    # 3. 골드 계산 (총 획득 XP - 사용한 골드)
    # 가챠 1회당 100 골드라고 가정 (수집한 포켓몬 수 * 100)
    used_gold = (len(collection_data) - 1) * 100 # 헤더 제외
    if used_gold < 0: used_gold = 0
    
    current_gold = total_xp - used_gold
            
    return level, current_xp, total_xp, stats, current_gold

def load_data():
    logs_data = ws_logs.get_all_records()
    col_data = ws_col.get_all_values() # 리스트 형태로 가져옴
    
    level, current_xp, total_xp, stats, gold = calculate_status_from_logs(logs_data, col_data)
    logs_data.reverse()
    
    # 도감 데이터 정리 (헤더 제외)
    my_pokemon = []
    if len(col_data) > 1:
        headers = col_data[0]
        for row in col_data[1:]:
            my_pokemon.append(dict(zip(headers, row)))
            
    return level, current_xp, total_xp, logs_data, stats, gold, my_pokemon

level, current_xp, total_xp, logs, my_stats, gold, my_pokemon = load_data()
next_level_xp = level * 100 

# ==========================================
# 3. 포켓몬 뽑기 로직 (PokeAPI)
# ==========================================
def draw_pokemon():
    if gold < 100:
        st.toast("💰 골드가 부족해! (1회 100G)", icon="🚫")
        return

    # 1세대(1) ~ 5세대(649) 랜덤 뽑기
    poke_id = random.randint(1, 649)
    
    try:
        url = f"https://pokeapi.co/api/v2/pokemon/{poke_id}"
        res = requests.get(url)
        data = res.json()
        
        name = data['name'].capitalize() # 영어 이름
        # 한글 이름 매핑은 너무 많아서 일단 영어로 저장 (나중에 고도화 가능)
        
        # 희귀도 (단순 재미용 랜덤)
        rarity_roll = random.randint(1, 100)
        rarity = "Normal"
        if rarity_roll > 98: rarity = "LEGENDARY"
        elif rarity_roll > 90: rarity = "Rare"
        
        # 저장
        now = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d")
        ws_col.append_row([poke_id, name, now, rarity])
        
        st.toast(f"🎉 {name} 획득!", icon="ball")
        st.balloons()
        st.rerun()
        
    except:
        st.error("포켓몬을 불러오지 못했어 ㅠㅠ 다시 시도해줘.")

# ==========================================
# 4. 액션 & UI
# ==========================================
TIER_MAP = [
    {"name": "Iron", "start": 1, "color": "#717171"},
    {"name": "Bronze", "start": 13, "color": "#8C7853"},
    {"name": "Silver", "start": 25, "color": "#808B96"},
    {"name": "Gold", "start": 37, "color": "#D4AC0D"},
    {"name": "Platinum", "start": 49, "color": "#27AE60"},
    {"name": "Diamond", "start": 73, "color": "#2980B9"},
    {"name": "Challenger", "start": 109, "color": "#F1C40F"}
]
def get_tier(lv):
    for i in range(len(TIER_MAP)-1, -1, -1):
        if lv >= TIER_MAP[i]["start"]: return TIER_MAP[i]["name"], TIER_MAP[i]["color"]
    return "Iron", "#717171"
cur_n, cur_c = get_tier(level)

def add_xp(amt, act, val):
    ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    ws_logs.append_row([ts, act, int(amt), val])
    st.toast("✅ 저장 완료!", icon="💾"); st.rerun()

def undo():
    if logs: ws_logs.delete_rows(len(ws_logs.get_all_values())); st.rerun()

st.set_page_config(page_title="관희의 성장 RPG", page_icon="🐾", layout="centered")

# [헤더]
c1, c2 = st.columns([2,1])
with c1: st.markdown(f"<h2 style='color:{cur_c}; margin:0;'>{cur_n} <span style='font-size:20px; color:#555'>(Lv.{level})</span></h2>", unsafe_allow_html=True)
with c2: st.metric("내 지갑", f"{gold} G")

# [메뉴]
menu = st.radio("", ["🏠 홈 (성장)", "🏪 포켓몬 뽑기", "📖 내 도감"], horizontal=True)

if menu == "🏠 홈 (성장)":
    # 그래프
    stats_df = pd.DataFrame(dict(r=[my_stats["STR"], my_stats["AGI"], my_stats["INT"], my_stats["WILL"], my_stats["LUCK"]], theta=['STR','AGI','INT','WILL','LUCK']))
    fig = px.line_polar(stats_df, r='r', theta='theta', line_close=True, range_r=[0, max(100, max(stats_df['r'])*1.2)])
    fig.update_traces(fill='toself', line_color='#FF4B4B')
    fig.update_layout(margin=dict(t=0,b=0,l=30,r=30), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)")
    st.plotly_chart(fig, use_container_width=True)
    
    st.progress(min(current_xp/next_level_xp, 1.0))
    st.caption(f"다음 레벨: {next_level_xp - current_xp} XP 남음")
    
    t1, t2 = st.tabs(["입력", "기록"])
    with t1:
        c_a, c_b = st.columns(2)
        with c_a:
            if st.button("🏃 달리기 5km (+100G)", use_container_width=True): add_xp(100, "🏃 달리기 5km", 5)
            if st.button("💪 푸쉬업 50회 (+25G)", use_container_width=True): add_xp(25, "💪 푸쉬업 50회", 50)
            if st.button("🦵 스쿼트 50회 (+25G)", use_container_width=True): add_xp(25, "🦵 스쿼트 50회", 50)
        with c_b:
            if st.button("🧠 공부 1시간 (+60G)", use_container_width=True): add_xp(60, "🧠 자기계발 60분", 60)
            if st.button("📖 독서 20쪽 (+20G)", use_container_width=True): add_xp(20, "📖 독서 20쪽", 20)
            if st.button("🧹 방 청소 (+15G)", use_container_width=True): add_xp(15, "🧹 방 청소", 0)
    with t2:
        st.dataframe(pd.DataFrame(logs)[['Time','Action','XP']], use_container_width=True)
        if st.button("취소"): undo()

elif menu == "🏪 포켓몬 뽑기":
    st.title("🎰 포켓몬 가챠샵")
    st.markdown("1회 뽑기 비용: **100 Gold**")
    st.markdown("*(1세대 ~ 5세대 포켓몬 중 랜덤 등장!)*")
    
    st.write("")
    if st.button("🔴 몬스터볼 던지기! (100G)", type="primary", use_container_width=True):
        draw_pokemon()
        
    st.info(f"현재 보유 골드: {gold} G")

elif menu == "📖 내 도감":
    st.title(f"🎒 내 가방 ({len(my_pokemon)}마리)")
    if my_pokemon:
        cols = st.columns(3) # 3열로 보여주기
        for i, mon in enumerate(my_pokemon):
            with cols[i % 3]:
                img_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{mon['ID']}.png"
                st.image(img_url, width=100)
                st.caption(f"No.{mon['ID']} **{mon['Name']}**")
                if mon['Rarity'] == 'LEGENDARY': st.write("🌟 **전설**")
    else:
        st.write("아직 잡은 포켓몬이 없어! 운동하고 뽑아보자!")
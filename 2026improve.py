import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import requests
import random
import time

# ==========================================
# 1. 구글 시트 연동 (초고속 연결)
# ==========================================
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "Gwanhee_Data" 

@st.cache_resource
def connect_to_sheet():
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    else:
        try: creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", SCOPE)
        except: st.error("인증 파일 오류"); st.stop()
            
    client = gspread.authorize(creds)
    sh = client.open(SHEET_NAME)
    
    try: ws_logs = sh.worksheet("Logs")
    except: ws_logs = sh.add_worksheet("Logs", 1000, 5); ws_logs.append_row(["Time", "Action", "XP", "Value"])
        
    try: ws_col = sh.worksheet("Collection")
    except: ws_col = sh.add_worksheet("Collection", 1000, 6); ws_col.append_row(["ID", "Name", "Date", "Rarity", "Cost", "Type"])

    return ws_logs, ws_col

try: ws_logs, ws_col = connect_to_sheet()
except Exception as e: st.error(f"서버 연결 오류: {e}"); st.stop()

# ==========================================
# 2. 데이터 처리 (캐싱으로 속도 향상)
# ==========================================
def load_data():
    logs_data = ws_logs.get_all_records()
    col_data = ws_col.get_all_values()
    
    # 골드 계산
    total_xp = 0
    for log in logs_data:
        try: total_xp += int(log.get("XP", 0)) if isinstance(log, dict) else int(log[2])
        except: continue
            
    # 쓴 돈 계산
    used_gold = 0
    my_pokemon = set() # 검색 속도 위해 set 사용
    my_poke_list = []
    
    if len(col_data) > 1:
        for row in col_data[1:]:
            try:
                cost = int(row[4])
                used_gold += cost
                pid = int(row[0])
                my_pokemon.add(pid)
                my_poke_list.append(row)
            except: continue
            
    current_gold = total_xp - used_gold
    
    # 레벨 계산
    level = 1
    temp = total_xp
    while temp >= level * 100:
        temp -= level * 100
        level += 1
        
    return level, temp, total_xp, current_gold, my_pokemon

level, current_xp, total_xp, gold, my_pokemon = load_data()
next_level_xp = level * 100

# ==========================================
# 3. 액션 함수
# ==========================================
def add_xp(amt, act, val):
    ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    ws_logs.append_row([ts, act, int(amt), val])
    st.toast(f"✅ {int(amt)}G 획득!", icon="💰")
    time.sleep(0.5) # 딜레이 최소화
    st.rerun()

def save_pokemon(poke_id, name, rarity, cost, p_type):
    now = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d")
    ws_col.append_row([poke_id, name, now, rarity, cost, p_type])
    st.toast(f"🎉 {name} 획득!", icon="ball")
    st.balloons()
    time.sleep(1)
    st.rerun()

# 1세대 이름 매핑 (API 호출 없이 즉시 변환 - 속도 핵심)
KOR_NAMES = {
    1:"이상해씨", 4:"파이리", 7:"꼬부기", 25:"피카츄", 133:"이브이", 143:"잠만보",
    149:"망나뇽", 150:"뮤츠", 151:"뮤", 94:"팬텀", 130:"갸라도스", 129:"잉어킹",
    39:"푸린", 52:"나옹", 54:"고라파덕", 68:"괴력몬", 74:"꼬마돌", 95:"롱스톤"
}

def get_poke_info_fast(pid):
    # API 호출 최소화: 이름은 딕셔너리 or 영어 / 이미지는 URL 조합
    # 상세 데이터(타입,등급)만 필요할 때 API 호출
    try:
        url = f"https://pokeapi.co/api/v2/pokemon/{pid}"
        res = requests.get(url, timeout=2).json()
        p_type = res['types'][0]['type']['name']
        
        # 이름 처리
        k_name = KOR_NAMES.get(pid, res['name'].capitalize())
        
        # 등급 판정
        stats_sum = sum([s['base_stat'] for s in res['stats']])
        rarity = "Normal"
        if stats_sum >= 580: rarity = "Legend"
        elif stats_sum >= 500: rarity = "Rare"
        if pid in [1,4,7,25,133,143,149,150,151]: rarity = "Special" # 1세대 인기몹 보정
        
        return k_name, rarity, p_type
    except:
        return "Unknown", "Normal", "normal"

# ==========================================
# 4. UI 구성 (최적화)
# ==========================================
st.set_page_config(page_title="관희의 1세대 RPG", page_icon="👾", layout="centered")

# CSS: 그림자 처리 & 버튼 스타일
st.markdown("""
<style>
    .shadow-img { filter: brightness(0) opacity(0.2); width: 60px; }
    .color-img { filter: brightness(1); width: 60px; transition: transform 0.2s; }
    .color-img:hover { transform: scale(1.1); }
    .poke-box { 
        background-color: #f8f9fa; border-radius: 10px; padding: 5px; 
        text-align: center; border: 1px solid #eee; margin-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# [헤더]
c1, c2 = st.columns([2,1])
with c1: st.markdown(f"### Lv.{level} 관희의 1세대")
with c2: st.markdown(f"<div style='text-align:right; font-size:22px; font-weight:bold; color:#D4AC0D;'>💰 {gold} G</div>", unsafe_allow_html=True)
st.progress(min(current_xp/next_level_xp, 1.0))
st.caption(f"다음 레벨까지 {next_level_xp - current_xp} XP | 수집: {len(my_pokemon)} / 151")

st.divider()

# 탭 메뉴
t1, t2, t3 = st.tabs(["💪 돈 벌기(운동)", "🎲 뽑기(Gacha)", "🎒 도감(1-151)"])

# --------------------------------------------------
# 1. 돈 벌기 (Form 사용으로 렉 방지)
# --------------------------------------------------
with t1:
    st.info("💡 기록 후 '제출'을 눌러야 저장됩니다. (입력 렉 없음)")
    
    with st.form("exercise_form"):
        c_run, c_gym = st.columns(2)
        with c_run:
            st.markdown("**🏃 유산소**")
            v_run = st.number_input("달리기 (km)", 0.0, 42.0, 0.0, 0.1)
        with c_gym:
            st.markdown("**💪 근력**")
            v_push = st.number_input("푸쉬업/스쿼트 (회)", 0, 500, 0, 10)
            
        st.markdown("**📚 자기계발**")
        c_study, c_read = st.columns(2)
        with c_study: v_study = st.number_input("공부 (분)", 0, 300, 0, 10)
        with c_read: v_read = st.number_input("독서 (쪽)", 0, 100, 0, 5)
        
        # 제출 버튼 하나로 통합 (핵심 최적화)
        submitted = st.form_submit_button("✅ 기록 제출하고 골드 받기", type="primary", use_container_width=True)
        
        if submitted:
            earned = 0
            msg = []
            if v_run > 0: earned += v_run * 50; msg.append(f"달리기 {v_run}km")
            if v_push > 0: earned += v_push * 0.5; msg.append(f"근력 {v_push}회")
            if v_study > 0: earned += v_study; msg.append(f"공부 {v_study}분")
            if v_read > 0: earned += v_read; msg.append(f"독서 {v_read}쪽")
            
            if earned > 0:
                add_xp(earned, " | ".join(msg), earned)
            else:
                st.warning("입력된 내용이 없습니다.")

# --------------------------------------------------
# 2. 뽑기 (단일 버튼)
# --------------------------------------------------
with t2:
    st.markdown("### ❓ 운명의 뽑기")
    st.write("1세대(1~151번) 중 한 마리가 랜덤으로 나옵니다.")
    
    # 여백
    st.write("")
    st.write("")
    
    btn_col, _ = st.columns([2, 1])
    with btn_col:
        if st.button("🔮 500G 내고 뽑기!", type="primary", use_container_width=True):
            if gold >= 500:
                # 1~151 랜덤
                pid = random.randint(1, 151)
                
                # 이미 있으면? (옵션: 중복 허용 or 환급. 지금은 중복 허용)
                k_name, rarity, p_type = get_poke_info_fast(pid)
                save_pokemon(pid, k_name, rarity, 500, p_type)
            else:
                st.error("골드가 부족합니다! 운동하고 오세요.")

# --------------------------------------------------
# 3. 도감 (이미지 URL 직접 계산 - 로딩 속도 최적화)
# --------------------------------------------------
with t3:
    # 한 페이지에 30마리씩 (5페이지면 끝)
    if 'dex_page' not in st.session_state: st.session_state['dex_page'] = 0
    PER_PAGE = 30
    
    page = st.session_state['dex_page']
    start = page * PER_PAGE + 1
    end = min(start + PER_PAGE, 152)
    
    # 페이지 버튼
    col_p1, col_p2, col_p3 = st.columns([1, 2, 1])
    with col_p1: 
        if page > 0: 
            if st.button("◀"): st.session_state['dex_page'] -= 1; st.rerun()
    with col_p2: st.markdown(f"<div style='text-align:center;'><b>No.{start} ~ {end-1}</b></div>", unsafe_allow_html=True)
    with col_p3: 
        if end < 151: 
            if st.button("▶"): st.session_state['dex_page'] += 1; st.rerun()
            
    st.divider()
    
    # 그리드 뷰 (API 호출 없음 - 쾌적함)
    cols = st.columns(5) # 5열 배치
    
    for i, pid in enumerate(range(start, end)):
        # 이미지 주소 직접 생성 (API 안 씀)
        img_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pid}.png"
        
        with cols[i % 5]:
            if pid in my_pokemon:
                # 보유: 컬러
                k_name = KOR_NAMES.get(pid, f"No.{pid}") # 주요 포켓몬은 이름 표시
                st.markdown(f"""
                <div class="poke-box">
                    <img src="{img_url}" class="color-img">
                    <div style="font-size:10px; font-weight:bold;">{k_name}</div>
                </div>
                """, unsafe_allow_html=True)
            else:
                # 미보유: 그림자
                st.markdown(f"""
                <div class="poke-box" style="opacity:0.6;">
                    <img src="{img_url}" class="shadow-img">
                    <div style="font-size:10px; color:#ccc;">{pid}</div>
                </div>
                """, unsafe_allow_html=True)
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import requests
import random
import time

# ==========================================
# 1. 구글 시트 연동 (캐시 해결을 위해 함수명 변경)
# ==========================================
SCOPE = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
SHEET_NAME = "Gwanhee_Data" 

# 🚨 함수 이름을 변경해서 강제로 캐시를 초기화함 (v32)
@st.cache_resource
def connect_db_v32():
    if "gcp_service_account" in st.secrets:
        creds_dict = st.secrets["gcp_service_account"]
        creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_dict, SCOPE)
    else:
        try: creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", SCOPE)
        except: st.error("인증 파일 오류"); st.stop()
            
    client = gspread.authorize(creds)
    sh = client.open(SHEET_NAME)
    
    # V18의 필수 탭 (Status)
    try: ws_status = sh.worksheet("Status")
    except: ws_status = sh.add_worksheet("Status", 10, 5)
    
    # 로그 탭
    try: ws_logs = sh.worksheet("Logs")
    except: ws_logs = sh.add_worksheet("Logs", 1000, 5); ws_logs.append_row(["Time", "Action", "XP", "Value"])
    
    # 포켓몬 데이터 탭 (Collection)
    try: ws_col = sh.worksheet("Collection")
    except: ws_col = sh.add_worksheet("Collection", 1000, 6); ws_col.append_row(["ID", "Name", "Date", "Rarity", "Cost", "Type"])

    # 3개를 리턴함 (기존 2개에서 변경됨)
    return ws_status, ws_logs, ws_col

# 함수 호출 부분도 변경됨
try: ws_status, ws_logs, ws_col = connect_db_v32()
except Exception as e: st.error(f"연결 실패: {e}"); st.stop()

# ==========================================
# 2. 데이터 계산 (V18 로직 + 골드 계산)
# ==========================================
def load_data():
    logs_data = ws_logs.get_all_records()
    col_data = ws_col.get_all_values()
    
    # 1. 총 경험치 계산
    total_xp = 0
    for log in logs_data:
        try: total_xp += int(log.get("XP", 0)) if isinstance(log, dict) else int(log[2])
        except: continue
            
    # 2. 쓴 돈 계산 (포켓몬)
    used_gold = 0
    my_pokemon = set()
    if len(col_data) > 1:
        for row in col_data[1:]:
            try:
                used_gold += int(row[4])
                my_pokemon.add(int(row[0]))
            except: continue
            
    # 3. 현재 보유 골드
    current_gold = total_xp - used_gold
    
    # 4. 레벨 계산
    level = 1
    temp = total_xp
    while temp >= level * 100:
        temp -= level * 100
        level += 1
    current_xp = temp
    
    # 최신순 정렬
    if isinstance(logs_data, list):
        logs_data.reverse()
        
    return level, current_xp, total_xp, current_gold, logs_data, my_pokemon

level, current_xp, total_xp, gold, logs, my_pokemon = load_data()
next_level_xp = level * 100

# ==========================================
# 3. V18 핵심 기능 (티어 & 스트릭)
# ==========================================
TIER_MAP = [
    {"name": "Iron", "start": 1, "color": "#717171"},
    {"name": "Bronze", "start": 13, "color": "#8C7853"},
    {"name": "Silver", "start": 25, "color": "#808B96"},
    {"name": "Gold", "start": 37, "color": "#D4AC0D"},
    {"name": "Platinum", "start": 49, "color": "#27AE60"},
    {"name": "Diamond", "start": 73, "color": "#2980B9"},
    {"name": "Master", "start": 85, "color": "#8E44AD"},
    {"name": "Challenger", "start": 109, "color": "#F1C40F"}
]
def get_tier(lv):
    for i in range(len(TIER_MAP)-1, -1, -1):
        if lv >= TIER_MAP[i]["start"]: return TIER_MAP[i]["name"], TIER_MAP[i]["color"]
    return "Iron", "#717171"
cur_n, cur_c = get_tier(level)

def get_streak(logs_data):
    if not logs_data: return 0
    try: dates = sorted(list(set([log['Time'].split(' ')[0] for log in logs_data])), reverse=True)
    except: return 0
    
    if not dates: return 0
    
    streak = 0
    now_kst = datetime.now() + timedelta(hours=9)
    today_str = now_kst.strftime("%Y-%m-%d")
    
    check_date = now_kst
    if dates[0] != today_str:
        check_date = now_kst - timedelta(days=1)
        
    for i in range(len(dates)):
        target = (check_date - timedelta(days=streak)).strftime("%Y-%m-%d")
        if target in dates: streak += 1
        else: break
    return streak
current_streak = get_streak(logs)

# ==========================================
# 4. 액션 및 포켓몬 함수
# ==========================================
def add_xp(amt, act, val):
    ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    ws_logs.append_row([ts, act, int(amt), val])
    try: ws_status.update_cell(2, 1, level)
    except: pass
    
    st.toast(f"✅ 기록 완료! (+{int(amt)}G)", icon="📝")
    time.sleep(0.5)
    st.rerun()

def undo():
    if logs:
        ws_logs.delete_rows(len(ws_logs.get_all_values()))
        st.toast("↩️ 취소됨", icon="🗑️")
        st.rerun()

def save_pokemon(poke_id, name, rarity, cost, p_type):
    now = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d")
    ws_col.append_row([poke_id, name, now, rarity, cost, p_type])
    st.toast(f"🎉 {name} 획득!", icon="ball")
    st.balloons()
    time.sleep(1.5)
    st.rerun()

KOR_NAMES = {
    1:"이상해씨", 2:"이상해풀", 3:"이상해꽃", 4:"파이리", 5:"리자드", 6:"리자몽",
    7:"꼬부기", 8:"어니부기", 9:"거북왕", 25:"피카츄", 26:"라이츄",
    39:"푸린", 52:"나옹", 54:"고라파덕", 59:"윈디", 68:"괴력몬", 74:"꼬마돌", 94:"팬텀", 95:"롱스톤",
    129:"잉어킹", 130:"갸라도스", 131:"라프라스", 133:"이브이", 143:"잠만보",
    149:"망나뇽", 150:"뮤츠", 151:"뮤"
}

def get_poke_info_fast(pid):
    try:
        url = f"https://pokeapi.co/api/v2/pokemon/{pid}"
        res = requests.get(url, timeout=2).json()
        p_type = res['types'][0]['type']['name']
        k_name = KOR_NAMES.get(pid, res['name'].capitalize())
        
        stats = sum([s['base_stat'] for s in res['stats']])
        rarity = "Normal"
        if stats >= 580: rarity = "Legend"
        elif stats >= 500: rarity = "Rare"
        if pid in [1,4,7,25,133,143,149,150,151]: rarity = "Special"
        
        return k_name, rarity, p_type
    except: return "Unknown", "Normal", "normal"

# ==========================================
# 5. UI 구성
# ==========================================
st.set_page_config(page_title="관희의 성장 RPG", page_icon="📈", layout="centered")

st.markdown("""
<style>
    .shadow-img { filter: brightness(0) opacity(0.2); width: 60px; }
    .color-img { filter: brightness(1); width: 60px; }
    .poke-box { background-color: #f9f9f9; border-radius: 8px; padding: 5px; text-align: center; border: 1px solid #eee; margin-bottom: 5px; }
</style>
""", unsafe_allow_html=True)

# [헤더]
c1, c2 = st.columns([2,1])
with c1: 
    st.markdown(f"<h2 style='color:{cur_c}; margin:0;'>{cur_n} <span style='font-size:18px; color:#555'>(Lv.{level})</span></h2>", unsafe_allow_html=True)
    st.caption(f"다음 레벨: {current_xp}/{next_level_xp} XP")
with c2: 
    if current_streak > 0: 
        st.markdown(f"<div style='text-align:right; color:#FF4B4B;'><b>🔥 {current_streak}일 연속!</b></div>", unsafe_allow_html=True)
    else:
        st.markdown(f"<div style='text-align:right; color:#999;'>연속 기록 도전!</div>", unsafe_allow_html=True)
    st.markdown(f"<div style='text-align:right; font-weight:bold; color:#D4AC0D;'>💰 {gold} G</div>", unsafe_allow_html=True)

st.progress(min(current_xp/next_level_xp, 1.0))
st.divider()

# 메인 탭
tab1, tab2, tab3 = st.tabs(["🏠 성장(V18)", "🏥 뽑기", "🎒 도감"])

# ------------------------------------------------------------------
# 1. 성장
# ------------------------------------------------------------------
with tab1:
    st.subheader("📊 성장 그래프 (7일)")
    if logs:
        df = pd.DataFrame(logs)
        df['Date'] = df['Time'].apply(lambda x: x.split(' ')[0])
        daily_xp = df.groupby('Date')['XP'].sum().tail(7)
        st.bar_chart(daily_xp, color="#FF4B4B")
    else: st.info("데이터가 쌓이면 그래프가 나타납니다!")

    st.subheader("📝 오늘의 기록")
    t_phy, t_brain, t_routine = st.tabs(["⚔️ 피지컬", "🧠 뇌지컬", "🛡️ 루틴"])
    
    with t_phy:
        c1, c2 = st.columns(2)
        with c1:
            v1 = st.number_input("달리기(km)", 0.0, 42.0, 5.0, 0.1, key="run")
            if st.button("기록 (+50G/km)", key="b1", use_container_width=True): 
                if v1>0: add_xp(v1*50, f"🏃 달리기 {v1}km", v1)
        with c2:
            v2 = st.number_input("근력운동(회)", 0, 1000, 30, 10, key="gym")
            if st.button("기록 (+0.5G/회)", key="b2", use_container_width=True): 
                if v2>0: add_xp(v2*0.5, f"💪 근력운동 {v2}회", v2)

    with t_brain:
        c3, c4 = st.columns(2)
        with c3:
            v3 = st.number_input("자기계발(분)", 0, 1440, 60, 10, key="study")
            if st.button("기록 (+1G/분)", key="b3", use_container_width=True): 
                if v3>0: add_xp(v3, f"🧠 자기계발 {v3}분", v3)
        with c4:
            v4 = st.number_input("독서(쪽)", 0, 1000, 10, 5, key="read")
            if st.button("기록 (+1G/쪽)", key="b4", use_container_width=True): 
                if v4>0: add_xp(v4, f"📖 독서 {v4}쪽", v4)

    with t_routine:
        r1, r2, r3 = st.columns(3)
        if r1.button("💰 무지출\n(20G)", use_container_width=True): add_xp(20, "💰 무지출", 0)
        if r2.button("💧 물 마시기\n(10G)", use_container_width=True): add_xp(10, "💧 물 마시기", 0)
        if r3.button("🧹 방 청소\n(15G)", use_container_width=True): add_xp(15, "🧹 방 청소", 0)

    with st.expander("📜 최근 기록 보기"):
        if logs: st.dataframe(pd.DataFrame(logs)[['Time','Action','XP']], use_container_width=True)
        if st.button("↩️ 마지막 기록 취소"): undo()

# ------------------------------------------------------------------
# 2. 뽑기
# ------------------------------------------------------------------
with tab2:
    st.markdown("### ❓ 운명의 뽑기 (1세대)")
    st.info(f"현재 보유 골드: **{gold} G**")
    st.write("")
    if st.button("🔮 500G 뽑기!", type="primary", use_container_width=True):
        if gold >= 500:
            pid = random.randint(1, 151)
            k_name, rarity, p_type = get_poke_info_fast(pid)
            save_pokemon(pid, k_name, rarity, 500, p_type)
        else: st.error("골드가 부족합니다! 성장 탭에서 운동하세요!")

# ------------------------------------------------------------------
# 3. 도감 (모바일 최적화)
# ------------------------------------------------------------------
with tab3:
    if 'dex_page' not in st.session_state: st.session_state['dex_page'] = 0
    PER_PAGE = 24
    
    page = st.session_state['dex_page']
    start = page * PER_PAGE + 1
    end = min(start + PER_PAGE, 152)
    
    c_p1, c_p2, c_p3 = st.columns([1, 2, 1])
    with c_p1: 
        if page > 0: 
            if st.button("◀"): st.session_state['dex_page'] -= 1; st.rerun()
    with c_p2: st.markdown(f"<div style='text-align:center;'><b>No.{start} ~ {end-1}</b></div>", unsafe_allow_html=True)
    with c_p3: 
        if end < 151: 
            if st.button("▶"): st.session_state['dex_page'] += 1; st.rerun()
            
    st.divider()
    
    poke_ids = list(range(start, end))
    for i in range(0, len(poke_ids), 3):
        row_cols = st.columns(3)
        for j in range(3):
            if i + j < len(poke_ids):
                pid = poke_ids[i+j]
                img_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pid}.png"
                with row_cols[j]:
                    if pid in my_pokemon:
                        k_name = KOR_NAMES.get(pid, f"No.{pid}")
                        st.markdown(f"""<div class="poke-box"><img src="{img_url}" class="color-img"><div style="font-size:11px; font-weight:bold;">{k_name}</div></div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""<div class="poke-box" style="opacity:0.5;"><img src="{img_url}" class="shadow-img"><div style="font-size:11px; color:#ccc;">{pid}</div></div>""", unsafe_allow_html=True)
import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import requests
import random
import time

# ==========================================
# 1. 구글 시트 연동
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
    
    try: ws_status = sh.worksheet("Status")
    except: ws_status = sh.add_worksheet("Status", 10, 5)
    try: ws_logs = sh.worksheet("Logs")
    except: 
        ws_logs = sh.add_worksheet("Logs", 1000, 5)
        ws_logs.append_row(["Time", "Action", "XP", "Value"])
    try: ws_col = sh.worksheet("Collection")
    except:
        ws_col = sh.add_worksheet("Collection", 1000, 5)
        ws_col.append_row(["ID", "Name", "Date", "Rarity", "Cost"])

    return ws_status, ws_logs, ws_col

try: ws_status, ws_logs, ws_col = connect_to_sheet()
except Exception as e: st.error(f"❌ 연결 실패: {e}"); st.stop()

# ==========================================
# 2. 데이터 로드 & 골드 계산
# ==========================================
def calculate_status(logs_data, col_data):
    total_xp = 0
    for log in logs_data:
        try: total_xp += int(log.get("XP", 0)) if isinstance(log, dict) else int(log[2])
        except: continue

    level = 1
    current_xp = total_xp
    while True:
        if current_xp >= level * 100: current_xp -= level * 100; level += 1
        else: break
            
    used_gold = 0
    if len(col_data) > 1:
        for row in col_data[1:]:
            try: used_gold += int(row[4])
            except: used_gold += 100
    
    current_gold = total_xp - used_gold
    return level, current_xp, total_xp, current_gold

def load_data():
    logs_data = ws_logs.get_all_records()
    col_data = ws_col.get_all_values()
    level, cur_xp, tot_xp, gold = calculate_status(logs_data, col_data)
    logs_data.reverse()
    
    my_pokemon = []
    if len(col_data) > 1:
        headers = col_data[0]
        for row in col_data[1:]:
            p_data = dict(zip(headers, row))
            if 'Cost' not in p_data: p_data['Cost'] = 100
            my_pokemon.append(p_data)
            
    return level, cur_xp, tot_xp, logs_data, gold, my_pokemon

level, current_xp, total_xp, logs, gold, my_pokemon = load_data()
next_level_xp = level * 100 

# ==========================================
# 3. 기능 함수
# ==========================================
def add_xp(amt, act, val):
    ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    ws_logs.append_row([ts, act, int(amt), val])
    st.toast("✅ 저장 완료!", icon="💾"); st.rerun()

def save_pokemon(poke_id, name, rarity, cost):
    now = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d")
    ws_col.append_row([poke_id, name, now, rarity, cost])
    st.toast(f"🎉 {name} 구매 성공!", icon="ball")
    st.balloons()
    time.sleep(1.5)
    st.rerun()

def reset_collection():
    ws_col.clear()
    ws_col.append_row(["ID", "Name", "Date", "Rarity", "Cost"])
    st.toast("🗑️ 도감이 초기화되었습니다.", icon="⚠️")
    time.sleep(1)
    st.rerun()

def get_poke_stats(poke_id):
    try:
        url = f"https://pokeapi.co/api/v2/pokemon/{poke_id}"
        res = requests.get(url).json()
        stats = {s['stat']['name']: s['base_stat'] for s in res['stats']}
        cp = stats.get('hp', 50) + stats.get('attack', 50) + stats.get('defense', 50) + stats.get('speed', 50)
        return cp, res['sprites']['front_default'], res['name'].capitalize()
    except: return 0, "", "Unknown"

# ==========================================
# 4. UI 구성
# ==========================================
st.set_page_config(page_title="관희의 성장 RPG", page_icon="⚔️", layout="centered")

# [사이드바] 데이터 관리
with st.sidebar:
    st.header("⚙️ 관리 메뉴")
    st.write(f"현재 보유 골드: **{gold} G**")
    st.warning("아래 버튼은 주의해서 사용하세요.")
    if st.button("⚠️ 포켓몬 도감 초기화", use_container_width=True):
        reset_collection()

# [헤더]
c1, c2 = st.columns([2,1])
with c1: 
    st.markdown(f"<h2 style='margin:0;'>Lv.{level} 관희 <span style='font-size:16px; color:#555'>({current_xp}/{next_level_xp} XP)</span></h2>", unsafe_allow_html=True)
with c2: 
    st.markdown(f"<div style='text-align:right; font-size:20px; font-weight:bold; color:#D4AC0D;'>💰 {gold} G</div>", unsafe_allow_html=True)

st.progress(min(current_xp/next_level_xp, 1.0))
st.divider()

# [메인 메뉴]
menu = st.radio("", ["🏠 홈 (성장)", "🏪 상점 (교환)", "⚔️ 배틀 스테이지", "🎒 내 도감"], horizontal=True)

# ----------------------------------------------------------------
# 🏠 홈 (성장) - 입력 방식 복구!
# ----------------------------------------------------------------
if menu == "🏠 홈 (성장)":
    t1, t2 = st.tabs(["📝 기록하기", "📜 지난 기록"])
    
    with t1:
        st.subheader("🏃‍♂️ 피지컬")
        c_p1, c_p2, c_p3 = st.columns(3)
        with c_p1:
            val = st.number_input("달리기 (km)", 0.0, 42.195, 5.0, 0.1)
            if st.button("기록 (+20G/km)", key="run", use_container_width=True):
                if val > 0: add_xp(val*20, f"🏃 달리기 {val}km", val)
        with c_p2:
            val = st.number_input("푸쉬업 (회)", 0, 1000, 30, 5)
            if st.button("기록 (+0.5G/회)", key="push", use_container_width=True):
                if val > 0: add_xp(val*0.5, f"💪 푸쉬업 {val}회", val)
        with c_p3:
            val = st.number_input("스쿼트 (회)", 0, 1000, 50, 5)
            if st.button("기록 (+0.5G/회)", key="squat", use_container_width=True):
                if val > 0: add_xp(val*0.5, f"🦵 스쿼트 {val}회", val)

        st.subheader("🧠 뇌지컬")
        c_b1, c_b2 = st.columns(2)
        with c_b1:
            val = st.number_input("자기계발 (분)", 0, 1440, 60, 10)
            if st.button("기록 (+1G/분)", key="study", use_container_width=True):
                if val > 0: add_xp(val, f"🧠 자기계발 {val}분", val)
        with c_b2:
            val = st.number_input("독서 (쪽)", 0, 1000, 20, 5)
            if st.button("기록 (+1G/쪽)", key="read", use_container_width=True):
                if val > 0: add_xp(val, f"📖 독서 {val}쪽", val)

        st.subheader("🛡️ 습관")
        c_h1, c_h2, c_h3 = st.columns(3)
        if c_h1.button("💰 무지출 (+20G)", use_container_width=True): add_xp(20, "💰 무지출", 0)
        if c_h2.button("💧 물 마시기 (+10G)", use_container_width=True): add_xp(10, "💧 물 마시기", 0)
        if c_h3.button("🧹 방 청소 (+15G)", use_container_width=True): add_xp(15, "🧹 방 청소", 0)

    with t2:
        if logs: st.dataframe(pd.DataFrame(logs)[['Time','Action','XP']], use_container_width=True)
        if st.button("↩️ 마지막 기록 취소", type="secondary"): 
            if logs: ws_logs.delete_rows(len(ws_logs.get_all_values())); st.rerun()

# ----------------------------------------------------------------
# 🏪 상점 (교환) - 종류 대폭 추가 & 가격 현실화
# ----------------------------------------------------------------
elif menu == "🏪 상점 (교환)":
    st.subheader("🎲 랜덤 뽑기")
    if st.button("❓ 랜덤 포켓몬 뽑기 (100 G)", type="primary", use_container_width=True):
        if gold >= 100:
            pid = random.randint(1, 649)
            res = requests.get(f"https://pokeapi.co/api/v2/pokemon/{pid}").json()
            name = res['name'].capitalize()
            rarity = "Normal"
            save_pokemon(pid, name, rarity, 100)
        else: st.toast("골드가 부족해! 더 노력하자.", icon="💸")

    st.divider()
    st.subheader("💎 지정 교환소")
    
    # [가격 및 종류 대폭 수정]
    shop_data = [
        # 초고가 라인 (전설/환상)
        {"id": 493, "name": "Arceus", "price": 100000}, # 아르세우스 (신)
        {"id": 150, "name": "Mewtwo", "price": 50000},  # 뮤츠
        {"id": 384, "name": "Rayquaza", "price": 50000}, # 레쿠쟈
        {"id": 249, "name": "Lugia", "price": 40000},   # 루기아
        {"id": 250, "name": "Ho-oh", "price": 40000},   # 칠색조
        {"id": 483, "name": "Dialga", "price": 35000},  # 디아루가
        {"id": 484, "name": "Palkia", "price": 35000},  # 펄기아
        
        # 고가 라인 (600족/인기)
        {"id": 445, "name": "Garchomp", "price": 5000}, # 한카리아스
        {"id": 376, "name": "Metagross", "price": 5000}, # 메타그로스
        {"id": 248, "name": "Tyranitar", "price": 5000}, # 마기라스
        {"id": 149, "name": "Dragonite", "price": 5000}, # 망나뇽
        {"id": 6, "name": "Charizard", "price": 4000},   # 리자몽
        
        # 중가 라인 (실전/인기)
        {"id": 448, "name": "Lucario", "price": 3000},  # 루카리오
        {"id": 94, "name": "Gengar", "price": 2500},    # 팬텀
        {"id": 130, "name": "Gyarados", "price": 2000}, # 갸라도스
        {"id": 25, "name": "Pikachu", "price": 1000},   # 피카츄
        {"id": 133, "name": "Eevee", "price": 800},     # 이브이
        {"id": 143, "name": "Snorlax", "price": 1500},  # 잠만보
        
        # 저가 라인 (스타팅/귀여움)
        {"id": 1, "name": "Bulbasaur", "price": 500},   # 이상해씨
        {"id": 4, "name": "Charmander", "price": 500},  # 파이리
        {"id": 7, "name": "Squirtle", "price": 500},    # 꼬부기
        {"id": 152, "name": "Chikorita", "price": 300}, # 치코리타
        
        # 떨이
        {"id": 129, "name": "Magikarp", "price": 50},   # 잉어킹
        {"id": 10, "name": "Caterpie", "price": 30},    # 캐터피
    ]
    
    # 2열로 배치
    cols = st.columns(2)
    for i, p in enumerate(shop_data):
        with cols[i % 2]:
            with st.container(border=True):
                c_img, c_txt, c_btn = st.columns([1, 2, 1.5])
                with c_img:
                    st.image(f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{p['id']}.png", width=50)
                with c_txt:
                    st.write(f"**{p['name']}**")
                with c_btn:
                    if st.button(f"{p['price']} G", key=f"buy_{p['id']}", use_container_width=True):
                        if gold >= p['price']:
                            save_pokemon(p['id'], p['name'], "Shop", p['price'])
                        else: st.toast("골드가 부족해!", icon="💸")

# ----------------------------------------------------------------
# ⚔️ 배틀 스테이지 - 보상 삭제 (명예만 남음)
# ----------------------------------------------------------------
elif menu == "⚔️ 배틀 스테이지":
    st.title("🔥 실전 배틀")
    st.info("⚠️ 배틀은 나의 강함을 증명하는 곳입니다. (XP 획득 없음)")
    
    if not my_pokemon:
        st.warning("포켓몬이 없습니다. 상점에서 영입하세요.")
    else:
        my_names = [f"{p['Name']} (No.{p['ID']})" for p in my_pokemon]
        choice = st.selectbox("출전 포켓몬:", my_names)
        my_p = my_pokemon[my_names.index(choice)]
        
        if 'enemy_id' not in st.session_state: st.session_state['enemy_id'] = random.randint(1, 649)
            
        c1, c2, c3 = st.columns([2, 1, 2])
        my_cp, my_img, my_name = get_poke_stats(my_p['ID'])
        en_cp, en_img, en_name = get_poke_stats(st.session_state['enemy_id'])
        
        with c1:
            st.image(my_img, width=100); st.write(f"**{my_name}**"); st.caption(f"CP: {my_cp}")
        with c2: st.markdown("## VS")
        with c3:
            st.image(en_img, width=100); st.write(f"**Wild {en_name}**"); st.caption(f"CP: {en_cp}")
            
        st.divider()
        if st.button("🔥 배틀 시작!", type="primary", use_container_width=True):
            my_pow = my_cp + random.randint(-20, 50)
            en_pow = en_cp + random.randint(-20, 50)
            
            st.write(f"⚔️ 나: {my_pow} vs 적: {en_pow}")
            if my_pow >= en_pow:
                st.success("🏆 승리! 강함을 증명했습니다.")
                st.balloons()
                # 기록에는 남기지만 XP는 0
                ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
                ws_logs.append_row([ts, "⚔️ 배틀 승리", 0, 1])
                st.session_state['enemy_id'] = random.randint(1, 649)
                time.sleep(2); st.rerun()
            else:
                st.error("💀 패배... 더 강해져서 돌아오세요.")
                st.session_state['enemy_id'] = random.randint(1, 649)
        
        if st.button("다른 적 찾기"):
            st.session_state['enemy_id'] = random.randint(1, 649); st.rerun()

# ----------------------------------------------------------------
# 🎒 내 도감
# ----------------------------------------------------------------
elif menu == "🎒 내 도감":
    st.title(f"🎒 보유 포켓몬 ({len(my_pokemon)}마리)")
    if my_pokemon:
        cols = st.columns(3)
        for i, mon in enumerate(my_pokemon):
            with cols[i % 3]:
                st.image(f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{mon['ID']}.png", width=80)
                st.caption(f"**{mon['Name']}**")
    else: st.info("도감이 비었습니다.")
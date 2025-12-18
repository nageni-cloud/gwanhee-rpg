import streamlit as st
import pandas as pd
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from datetime import datetime, timedelta
import requests
import random
import time
import math

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
        ws_col.append_row(["ID", "Name", "Date", "Rarity", "Cost", "Type"])

    return ws_status, ws_logs, ws_col

try: ws_status, ws_logs, ws_col = connect_to_sheet()
except Exception as e: st.error(f"❌ 연결 실패: {e}"); st.stop()

# ==========================================
# 2. 데이터 로드
# ==========================================
def load_data():
    logs_data = ws_logs.get_all_records()
    col_data = ws_col.get_all_values()
    
    total_xp = 0
    for log in logs_data:
        try: total_xp += int(log.get("XP", 0)) if isinstance(log, dict) else int(log[2])
        except: continue

    # 레벨 계산
    level = 1
    current_xp = total_xp
    while True:
        if current_xp >= level * 100: current_xp -= level * 100; level += 1
        else: break
            
    # 골드 계산
    used_gold = 0
    if len(col_data) > 1:
        for row in col_data[1:]:
            try: used_gold += int(row[4])
            except: used_gold += 100 # 기본값
    
    gold = total_xp - used_gold
    
    # 도감 데이터 딕셔너리화
    my_pokemon = {}
    if len(col_data) > 1:
        headers = col_data[0]
        for row in col_data[1:]:
            p_data = dict(zip(headers, row))
            my_pokemon[int(p_data['ID'])] = p_data
            
    return level, current_xp, total_xp, list(reversed(logs_data)), gold, my_pokemon

level, current_xp, total_xp, logs, gold, my_pokemon = load_data()
next_level_xp = level * 100 

# ==========================================
# 3. 포켓몬 데이터 & 배틀 로직 (핵심!)
# ==========================================

# 1. 타입 상성표 (본가 5세대 기준 + 페어리 포함 최신화)
TYPE_CHART = {
    'normal': {'rock':0.5, 'ghost':0, 'steel':0.5},
    'fire': {'fire':0.5, 'water':0.5, 'grass':2, 'ice':2, 'bug':2, 'rock':0.5, 'dragon':0.5, 'steel':2},
    'water': {'fire':2, 'water':0.5, 'grass':0.5, 'ground':2, 'rock':2, 'dragon':0.5},
    'electric': {'water':2, 'electric':0.5, 'grass':0.5, 'ground':0, 'flying':2, 'dragon':0.5},
    'grass': {'fire':0.5, 'water':2, 'grass':0.5, 'poison':0.5, 'ground':2, 'flying':0.5, 'bug':0.5, 'rock':2, 'dragon':0.5, 'steel':0.5},
    'ice': {'fire':0.5, 'water':0.5, 'grass':2, 'ice':0.5, 'ground':2, 'flying':2, 'dragon':2, 'steel':0.5},
    'fighting': {'normal':2, 'ice':2, 'poison':0.5, 'flying':0.5, 'psychic':0.5, 'bug':0.5, 'rock':2, 'ghost':0, 'dark':2, 'steel':2, 'fairy':0.5},
    'poison': {'grass':2, 'poison':0.5, 'ground':0.5, 'rock':0.5, 'ghost':0.5, 'steel':0, 'fairy':2},
    'ground': {'fire':2, 'electric':2, 'grass':0.5, 'poison':2, 'flying':0, 'bug':0.5, 'rock':2, 'steel':2},
    'flying': {'electric':0.5, 'grass':2, 'fighting':2, 'bug':2, 'rock':0.5, 'steel':0.5},
    'psychic': {'fighting':2, 'poison':2, 'psychic':0.5, 'dark':0, 'steel':0.5},
    'bug': {'fire':0.5, 'grass':2, 'fighting':0.5, 'poison':0.5, 'flying':0.5, 'psychic':2, 'ghost':0.5, 'dark':2, 'steel':0.5, 'fairy':0.5},
    'rock': {'fire':2, 'ice':2, 'fighting':0.5, 'ground':0.5, 'flying':2, 'bug':2, 'steel':0.5},
    'ghost': {'normal':0, 'psychic':2, 'ghost':2, 'dark':0.5},
    'dragon': {'dragon':2, 'steel':0.5, 'fairy':0},
    'dark': {'fighting':0.5, 'psychic':2, 'ghost':2, 'dark':0.5, 'fairy':0.5},
    'steel': {'fire':0.5, 'water':0.5, 'electric':0.5, 'ice':2, 'rock':2, 'steel':0.5, 'fairy':2},
    'fairy': {'fire':0.5, 'fighting':2, 'poison':0.5, 'dragon':2, 'dark':2, 'steel':0.5}
}

def get_type_effectiveness(atk_type, def_type):
    if atk_type not in TYPE_CHART: return 1.0
    return TYPE_CHART[atk_type].get(def_type, 1.0)

# 2. 한글 이름 매핑 (주요 포켓몬 + 스타팅 + 전설)
KOR_NAMES = {
    "Bulbasaur": "이상해씨", "Ivysaur": "이상해풀", "Venusaur": "이상해꽃",
    "Charmander": "파이리", "Charmeleon": "리자드", "Charizard": "리자몽",
    "Squirtle": "꼬부기", "Wartortle": "어니부기", "Blastoise": "거북왕",
    "Pikachu": "피카츄", "Raichu": "라이츄", "Eevee": "이브이",
    "Dratini": "미뇽", "Dragonair": "신뇽", "Dragonite": "망나뇽",
    "Mewtwo": "뮤츠", "Mew": "뮤", "Articuno": "프리져", "Zapdos": "썬더", "Moltres": "파이어",
    "Chikorita": "치코리타", "Cyndaquil": "브케인", "Totodile": "리아코",
    "Lugia": "루기아", "Ho-oh": "칠색조", "Tyranitar": "마기라스",
    "Treecko": "나무지기", "Torchic": "아차모", "Mudkip": "물짱이",
    "Rayquaza": "레쿠쟈", "Kyogre": "가이오가", "Groudon": "그란돈",
    "Salamence": "보만다", "Metagross": "메타그로스",
    "Turtwig": "모부기", "Chimchar": "불꽃숭이", "Piplup": "팽도리",
    "Dialga": "디아루가", "Palkia": "펄기아", "Giratina": "기라티나",
    "Garchomp": "한카리아스", "Lucario": "루카리오", "Arceus": "아르세우스",
    "Snivy": "주리비얀", "Tepig": "뚜꾸리", "Oshawott": "수댕이",
    "Reshiram": "레시라무", "Zekrom": "제크로무", "Kyurem": "큐레무"
}

# 3. 가격 책정 로직 (유저 요청 반영)
def calculate_price(poke_id, stats_sum, name):
    # 전설/환상/600족/인기 포켓몬 ID 리스트 (하드코딩)
    premium_ids = [
        150, 151, 144, 145, 146, 249, 250, 243, 244, 245, 382, 383, 384, 380, 381, 
        483, 484, 487, 493, 643, 644, 646, # 전설
        149, 248, 373, 376, 445, 635, # 600족
        6, 25, 133, 448, 94, 130 # 인기 (리자몽, 피카츄, 이브이, 루카리오, 팬텀, 갸라도스)
    ]
    
    # 스타팅 포켓몬 ID (1,4,7, 152,155,158 ...)
    starter_ids = [1,2,3, 4,5,6, 7,8,9, 152,155,158, 252,255,258, 387,390,393, 495,498,501]

    if poke_id in premium_ids:
        if stats_sum >= 600: return 50000 # 초전설/600족
        else: return 10000 # 인기/일반전설
    elif poke_id in starter_ids:
        return 5000 # 스타팅
    elif stats_sum >= 500: # 꽤 강한 애들
        return 3000
    else:
        return 2000 # 일반/비인기 (반값 할인)

# 4. 실전 배틀용 스탯 계산 (Lv.50 기준)
def get_battle_stats(poke_id):
    try:
        url = f"https://pokeapi.co/api/v2/pokemon/{poke_id}"
        res = requests.get(url).json()
        
        # 기본 정보
        name_en = res['name'].capitalize()
        name_kr = KOR_NAMES.get(name_en, name_en)
        types = [t['type']['name'] for t in res['types']]
        p_type = types[0]
        img = res['sprites']['front_default']
        
        # 종족값 가져오기
        bs = {s['stat']['name']: s['base_stat'] for s in res['stats']}
        
        # Lv.50 실전 스탯 공식 (개체값 31, 노력치 0 가정)
        # HP = (Base*2 + 31 + 0)/2 + 50 + 10
        # Other = (Base*2 + 31 + 0)/2 + 5
        stats = {}
        stats['hp'] = int((bs['hp'] * 2 + 31) * 0.5 + 60)
        stats['atk'] = int((bs['attack'] * 2 + 31) * 0.5 + 5)
        stats['def'] = int((bs['defense'] * 2 + 31) * 0.5 + 5)
        stats['spa'] = int((bs['special-attack'] * 2 + 31) * 0.5 + 5)
        stats['spd'] = int((bs['special-defense'] * 2 + 31) * 0.5 + 5)
        stats['spe'] = int((bs['speed'] * 2 + 31) * 0.5 + 5)
        
        # 기술 배치 (타입 기반 가상 기술)
        moves = get_moves_by_type(p_type, types[1] if len(types)>1 else None)
        
        return {
            "id": poke_id, "name": name_kr, "img": img, "type": types,
            "stats": stats, "moves": moves, "max_hp": stats['hp'], "current_hp": stats['hp']
        }
    except: return None

# 5. 기술 배치 생성기 (간이)
def get_moves_by_type(t1, t2=None):
    # 타입별 대표 기술 (이름, 위력, 타입, 분류) 분류: 0=물리, 1=특수
    move_pool = {
        'normal': [("몸통박치기", 40, 'normal'), ("은혜갚기", 102, 'normal'), ("파괴광선", 150, 'normal')],
        'fire': [("불꽃세례", 40, 'fire'), ("화염방사", 90, 'fire'), ("불대문자", 110, 'fire')],
        'water': [("물대포", 40, 'water'), ("파도타기", 90, 'water'), ("하이드로펌프", 110, 'water')],
        'grass': [("덩굴채찍", 45, 'grass'), ("에너지볼", 90, 'grass'), ("솔라빔", 120, 'grass')],
        'electric': [("전기쇼크", 40, 'electric'), ("10만볼트", 90, 'electric'), ("번개", 110, 'electric')],
        'ice': [("얼음뭉치", 40, 'ice'), ("냉동빔", 90, 'ice'), ("눈보라", 110, 'ice')],
        'fighting': [("바위깨기", 40, 'fighting'), ("인파이트", 120, 'fighting'), ("기합구슬", 120, 'fighting')],
        'poison': [("독침", 15, 'poison'), ("오물폭탄", 90, 'poison'), ("더스트슈트", 120, 'poison')],
        'ground': [("진흙뿌리기", 20, 'ground'), ("지진", 100, 'ground'), ("대지의힘", 90, 'ground')],
        'flying': [("쪼기", 35, 'flying'), ("제비반환", 60, 'flying'), ("브레이브버드", 120, 'flying')],
        'psychic': [("염동력", 50, 'psychic'), ("사이코키네시스", 90, 'psychic'), ("미래예지", 120, 'psychic')],
        'bug': [("벌레의야단법석", 90, 'bug'), ("시저크로스", 80, 'bug'), ("메가폰", 120, 'bug')],
        'rock': [("돌떨구기", 50, 'rock'), ("스톤샤워", 75, 'rock'), ("스톤에지", 100, 'rock')],
        'ghost': [("핥기", 30, 'ghost'), ("섀도볼", 80, 'ghost'), ("섀도클로", 70, 'ghost')],
        'dragon': [("용의숨결", 60, 'dragon'), ("용의파동", 85, 'dragon'), ("역린", 120, 'dragon')],
        'dark': [("물기", 60, 'dark'), ("악의파동", 80, 'dark'), ("깨물어부수기", 80, 'dark')],
        'steel': [("메탈크로우", 50, 'steel'), ("러스터캐논", 80, 'steel'), ("코멧펀치", 90, 'steel')],
        'fairy': [("요정의바람", 40, 'fairy'), ("문포스", 95, 'fairy'), ("치근거리기", 90, 'fairy')]
    }
    
    # 기술 4개 선정: 자속기 2개 + 견제기(노말/서브) 2개
    moves = []
    # 1. 메인 타입 기술
    pool1 = move_pool.get(t1, move_pool['normal'])
    moves.append(random.choice(pool1)) # 약한 거/중간 거 중 랜덤
    moves.append(pool1[-1]) # 강한 거
    
    # 2. 서브 타입 or 노말
    if t2:
        pool2 = move_pool.get(t2, move_pool['normal'])
        moves.append(pool2[-1])
    else:
        moves.append(("은혜갚기", 102, 'normal'))
        
    # 3. 랜덤 견제기
    rand_type = random.choice(list(move_pool.keys()))
    moves.append(move_pool[rand_type][1]) # 중간 위력 기술
    
    # 이름/위력/타입 딕셔너리로 변환
    return [{"name": m[0], "power": m[1], "type": m[2]} for m in moves[:4]]

# ==========================================
# 4. 기능 함수 (저장, 리셋)
# ==========================================
def add_xp(amt, act, val):
    ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    ws_logs.append_row([ts, act, int(amt), val])
    st.toast("✅ 저장 완료!", icon="💾"); st.rerun()

def save_pokemon(poke_id, name, rarity, cost, p_type):
    now = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d")
    ws_col.append_row([poke_id, name, now, rarity, cost, p_type])
    st.toast(f"🎉 {name} 획득!", icon="ball")
    st.balloons()
    time.sleep(1.5); st.rerun()

def reset_collection():
    ws_col.clear()
    ws_col.append_row(["ID", "Name", "Date", "Rarity", "Cost", "Type"])
    st.rerun()

# ==========================================
# 5. UI 구성
# ==========================================
st.set_page_config(page_title="관희의 포켓몬 RPG", page_icon="🧢", layout="centered")

# CSS: 실루엣 & 탭 스타일
st.markdown("""
<style>
    .shadow-img { filter: brightness(0) opacity(0.2); }
    .color-img { filter: brightness(1); }
    .stTabs [data-baseweb="tab-list"] { gap: 10px; }
    .stTabs [data-baseweb="tab"] { height: 50px; white-space: pre-wrap; background-color: #f0f2f6; border-radius: 4px; }
    .stTabs [aria-selected="true"] { background-color: #ff4b4b; color: white; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.write(f"💰 보유: **{gold} G**")
    if st.button("⚠️ 도감 초기화"): reset_collection()

# 헤더
c1, c2 = st.columns([2,1])
with c1: st.markdown(f"### Lv.{level} 관희 ({current_xp}/{next_level_xp} XP)")
with c2: st.markdown(f"<div style='text-align:right; font-size:18px; font-weight:bold; color:#D4AC0D;'>💰 {gold} G</div>", unsafe_allow_html=True)
st.progress(min(current_xp/next_level_xp, 1.0))

menu = st.radio("", ["🏠 홈", "🏥 포켓몬센터", "⚔️ 실전 배틀", "🎒 도감"], horizontal=True)

# ----------------------------------------------------------------
# 🏠 홈 (기록)
# ----------------------------------------------------------------
if menu == "🏠 홈":
    t1, t2 = st.tabs(["📝 활동 기록", "📜 로그"])
    with t1:
        st.caption("🏃 달리기는 50G/km, 나머지는 효율 조정됨")
        c1, c2 = st.columns(2)
        with c1:
            val = st.number_input("달리기 (km)", 0.0, 42.195, 5.0, 0.1)
            if st.button("기록 (50G/km)", use_container_width=True): 
                if val>0: add_xp(val*50, f"🏃 달리기 {val}km", val)
            
            val = st.number_input("푸쉬업 (회)", 0, 1000, 30, 5)
            if st.button("기록 (0.5G/회)", use_container_width=True): 
                if val>0: add_xp(val*0.5, f"💪 푸쉬업 {val}회", val)
                
        with c2:
            val = st.number_input("자기계발 (분)", 0, 1440, 60, 10)
            if st.button("기록 (1G/분)", use_container_width=True): 
                if val>0: add_xp(val, f"🧠 자기계발 {val}분", val)
                
            val = st.number_input("독서 (쪽)", 0, 500, 20, 5)
            if st.button("기록 (1G/쪽)", use_container_width=True): 
                if val>0: add_xp(val, f"📖 독서 {val}쪽", val)
    with t2:
        if logs: st.dataframe(pd.DataFrame(logs)[['Time','Action','XP']], use_container_width=True)
        if st.button("↩️ 취소"): 
            if logs: ws_logs.delete_rows(len(ws_logs.get_all_values())); st.rerun()

# ----------------------------------------------------------------
# 🏥 포켓몬 센터 (탭 방식 & 뽑기 부활)
# ----------------------------------------------------------------
elif menu == "🏥 포켓몬 센터":
    st.subheader("🎁 행운의 뽑기")
    if st.button("📦 랜덤 박스 뽑기 (500 G)", type="primary", use_container_width=True):
        if gold >= 500:
            pid = random.randint(1, 649)
            res = requests.get(f"https://pokeapi.co/api/v2/pokemon/{pid}").json()
            name_en = res['name'].capitalize()
            name_kr = KOR_NAMES.get(name_en, name_en)
            p_type = res['types'][0]['type']['name']
            
            # 가격 계산해서 등급 매기기
            stats_sum = sum([s['base_stat'] for s in res['stats']])
            price = calculate_price(pid, stats_sum, name_kr)
            rarity = "Legendary" if price >= 10000 else ("Rare" if price >= 3000 else "Normal")
            
            save_pokemon(pid, name_kr, rarity, 500, p_type) # 구매가는 500으로 기록
        else: st.toast("골드가 부족해!", icon="💸")
    
    st.divider()
    st.subheader("🛒 포켓몬 구매 (세대별)")
    
    # 탭으로 세대 구분
    gens = st.tabs(["1세대", "2세대", "3세대", "4세대", "5세대"])
    gen_ranges = [(1,151), (152,251), (252,386), (387,493), (494,649)]
    
    for i, tab in enumerate(gens):
        with tab:
            st.caption("※ 이미지는 로딩 속도를 위해 즉시 표시되며, 구매 시 상세 정보를 불러옵니다.")
            start, end = gen_ranges[i]
            
            # 그리드 (3열)
            cols = st.columns(3)
            for pid in range(start, end+1):
                with cols[(pid-start)%3]:
                    img_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pid}.png"
                    st.image(img_url, width=80)
                    
                    # 버튼 누르면 가격 계산 및 구매 시도
                    if st.button(f"No.{pid} 구매", key=f"buy_btn_{pid}"):
                        if pid in my_pokemon:
                            st.warning("이미 있어!")
                        else:
                            # 즉시 정보 로드
                            try:
                                res = requests.get(f"https://pokeapi.co/api/v2/pokemon/{pid}").json()
                                name_en = res['name'].capitalize()
                                name_kr = KOR_NAMES.get(name_en, name_en)
                                stats_sum = sum([s['base_stat'] for s in res['stats']])
                                price = calculate_price(pid, stats_sum, name_kr)
                                p_type = res['types'][0]['type']['name']
                                rarity = "Legendary" if price >= 10000 else "Normal"
                                
                                if gold >= price:
                                    save_pokemon(pid, name_kr, rarity, price, p_type)
                                else:
                                    st.error(f"{name_kr}: {price} G 필요 (잔액 부족)")
                            except: st.error("통신 오류")

# ----------------------------------------------------------------
# ⚔️ 실전 배틀 (턴제 & 기술 선택)
# ----------------------------------------------------------------
elif menu == "⚔️ 실전 배틀":
    st.title("🔥 실전 배틀 (Lv.50)")
    
    # 1. 포켓몬 선택 단계
    if 'battle_state' not in st.session_state:
        if not my_pokemon:
            st.warning("포켓몬이 없어!")
        else:
            my_names = [f"{v['Name']} (No.{k})" for k, v in my_pokemon.items()]
            choice = st.selectbox("출전 포켓몬:", my_names)
            
            if st.button("배틀 시작! (상대 탐색)", type="primary"):
                my_id = int(choice.split("No.")[1].replace(")",""))
                en_id = random.randint(1, 649)
                
                with st.spinner("선수 입장 중..."):
                    p1 = get_battle_stats(my_id)
                    p2 = get_battle_stats(en_id)
                
                if p1 and p2:
                    st.session_state['battle_state'] = {
                        'p1': p1, 'p2': p2, 
                        'turn': 0, 'logs': ["⚔️ 배틀이 시작되었다!"]
                    }
                    st.rerun()

    # 2. 배틀 진행 단계
    else:
        bs = st.session_state['battle_state']
        p1 = bs['p1']
        p2 = bs['p2']
        
        # UI: 체력바 및 정보
        c1, c2, c3 = st.columns([2,1,2])
        with c1:
            st.image(p1['img'], width=100)
            st.write(f"**{p1['name']}** (Lv.50)")
            hp_pct = p1['current_hp'] / p1['max_hp']
            st.progress(hp_pct)
            st.write(f"HP: {p1['current_hp']} / {p1['max_hp']}")
        with c2: st.markdown("## VS")
        with c3:
            st.image(p2['img'], width=100)
            st.write(f"**{p2['name']}** (Lv.50)")
            hp_pct2 = p2['current_hp'] / p2['max_hp']
            st.progress(hp_pct2)
            st.write(f"HP: {p2['current_hp']} / {p2['max_hp']}")
            
        st.divider()
        st.write("📜 **배틀 로그**")
        for log in bs['logs'][-3:]: st.caption(log)
        
        # 게임 종료 체크
        if p1['current_hp'] <= 0:
            st.error("💀 패배했습니다...")
            if st.button("돌아가기"): del st.session_state['battle_state']; st.rerun()
        elif p2['current_hp'] <= 0:
            st.success("🏆 승리했습니다!")
            st.balloons()
            if st.button("돌아가기"): 
                # 승리 기록 (보상 없음)
                ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
                ws_logs.append_row([ts, "⚔️ 배틀 승리", 0, 1])
                del st.session_state['battle_state']; st.rerun()
        
        # 내 턴 (기술 선택)
        else:
            st.subheader("공격 기술 선택")
            cols = st.columns(2)
            for i, move in enumerate(p1['moves']):
                with cols[i%2]:
                    # 기술 버튼
                    btn_label = f"{move['name']} ({move['type']}/{move['power']})"
                    if st.button(btn_label, key=f"move_{i}", use_container_width=True):
                        
                        # 1. 내 공격
                        eff = get_type_effectiveness(move['type'], p2['type'][0])
                        if len(p2['type']) > 1: eff *= get_type_effectiveness(move['type'], p2['type'][1])
                        
                        crit = 1.5 if random.random() < 0.05 else 1.0 # 급소 5%
                        stab = 1.5 if move['type'] in p1['type'] else 1.0 # 자속 보정
                        
                        # 데미지 공식 (약식)
                        damage = (((2*50/5 + 2) * move['power'] * (p1['stats']['atk']/p2['stats']['def']) / 50) + 2) * eff * crit * stab * random.uniform(0.85, 1.0)
                        damage = int(damage)
                        
                        p2['current_hp'] = max(0, p2['current_hp'] - damage)
                        
                        log_msg = f"👊 {p1['name']}의 {move['name']}! (데미지: {damage})"
                        if crit > 1: log_msg += " ⚡급소!"
                        if eff > 1: log_msg += " 🔥효과  굉장!"
                        elif eff < 1: log_msg += " 💧효과 별로..."
                        bs['logs'].append(log_msg)
                        
                        # 2. 적 공격 (생존 시)
                        if p2['current_hp'] > 0:
                            en_move = random.choice(p2['moves'])
                            eff2 = get_type_effectiveness(en_move['type'], p1['type'][0])
                            if len(p1['type']) > 1: eff2 *= get_type_effectiveness(en_move['type'], p1['type'][1])
                            
                            crit2 = 1.5 if random.random() < 0.05 else 1.0
                            stab2 = 1.5 if en_move['type'] in p2['type'] else 1.0
                            
                            dmg2 = (((2*50/5 + 2) * en_move['power'] * (p2['stats']['atk']/p1['stats']['def']) / 50) + 2) * eff2 * crit2 * stab2 * random.uniform(0.85, 1.0)
                            dmg2 = int(dmg2)
                            
                            p1['current_hp'] = max(0, p1['current_hp'] - dmg2)
                            bs['logs'].append(f"🛡️ 적 {p2['name']}의 {en_move['name']}! (받은 데미지: {dmg2})")
                        
                        st.rerun()

    if st.button("도망치기 (배틀 종료)"):
        del st.session_state['battle_state']; st.rerun()

# ----------------------------------------------------------------
# 🎒 내 도감 (실루엣)
# ----------------------------------------------------------------
elif menu == "🎒 도감":
    st.title(f"🎒 도감 ({len(my_pokemon)} / 649)")
    gens = st.tabs(["1세대", "2세대", "3세대", "4세대", "5세대"])
    gen_ranges = [(1,151), (152,251), (252,386), (387,493), (494,649)]
    
    for i, tab in enumerate(gens):
        with tab:
            start, end = gen_ranges[i]
            cols = st.columns(4)
            for pid in range(start, end+1):
                with cols[(pid-start)%4]:
                    img_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pid}.png"
                    if pid in my_pokemon:
                        st.markdown(f"""<div style="text-align:center;"><img src="{img_url}" width="70" class="color-img"><div style="font-size:12px;">No.{pid}</div><div style="font-size:12px;font-weight:bold;">{my_pokemon[pid]['Name']}</div></div>""", unsafe_allow_html=True)
                    else:
                        st.markdown(f"""<div style="text-align:center; opacity:0.5;"><img src="{img_url}" width="70" class="shadow-img"><div style="font-size:12px;">No.{pid}</div><div style="font-size:12px;">???</div></div>""", unsafe_allow_html=True)
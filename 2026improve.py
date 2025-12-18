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
    
    total_xp = sum([int(log['XP']) for log in logs_data if str(log['XP']).isdigit()])
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
    gold = total_xp - used_gold
    
    my_pokemon = {}
    if len(col_data) > 1:
        headers = col_data[0]
        for row in col_data[1:]:
            p_data = dict(zip(headers, row))
            my_pokemon[int(p_data['ID'])] = p_data
            
    return level, current_xp, total_xp, logs_data, gold, my_pokemon

level, current_xp, total_xp, logs, gold, my_pokemon = load_data()
next_level_xp = level * 100 

def add_xp(amt, act, val):
    ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
    ws_logs.append_row([ts, act, int(amt), val])
    st.toast("✅ 저장 완료!", icon="💾"); st.rerun()

def save_pokemon(poke_id, name, rarity, cost, p_type):
    now = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d")
    ws_col.append_row([poke_id, name, now, rarity, cost, p_type])
    st.toast(f"🎉 {name} 획득!", icon="ball"); time.sleep(1.5); st.rerun()

def reset_collection():
    ws_col.clear(); ws_col.append_row(["ID", "Name", "Date", "Rarity", "Cost", "Type"]); st.rerun()

# ==========================================
# 3. 배틀 엔진 (Battle Engine) - 핵심!
# ==========================================

# 3-1. 타입 상성표 (Gen 6+ 기준)
TYPE_CHART = {
    "normal": {"rock": 0.5, "ghost": 0, "steel": 0.5},
    "fire": {"fire": 0.5, "water": 0.5, "grass": 2, "ice": 2, "bug": 2, "rock": 0.5, "dragon": 0.5, "steel": 2},
    "water": {"fire": 2, "water": 0.5, "grass": 0.5, "ground": 2, "rock": 2, "dragon": 0.5},
    "electric": {"water": 2, "electric": 0.5, "grass": 0.5, "ground": 0, "flying": 2, "dragon": 0.5},
    "grass": {"fire": 0.5, "water": 2, "grass": 0.5, "poison": 0.5, "ground": 2, "flying": 0.5, "bug": 0.5, "rock": 2, "dragon": 0.5, "steel": 0.5},
    "ice": {"fire": 0.5, "water": 0.5, "grass": 2, "ice": 0.5, "ground": 2, "flying": 2, "dragon": 2, "steel": 0.5},
    "fighting": {"normal": 2, "ice": 2, "poison": 0.5, "flying": 0.5, "psychic": 0.5, "bug": 0.5, "rock": 2, "ghost": 0, "dark": 2, "steel": 2, "fairy": 0.5},
    "poison": {"grass": 2, "poison": 0.5, "ground": 0.5, "rock": 0.5, "ghost": 0.5, "steel": 0, "fairy": 2},
    "ground": {"fire": 2, "electric": 2, "grass": 0.5, "poison": 2, "flying": 0, "bug": 0.5, "rock": 2, "steel": 2},
    "flying": {"electric": 0.5, "grass": 2, "fighting": 2, "bug": 2, "rock": 0.5, "steel": 0.5},
    "psychic": {"fighting": 2, "poison": 2, "psychic": 0.5, "dark": 0, "steel": 0.5},
    "bug": {"fire": 0.5, "grass": 2, "fighting": 0.5, "poison": 0.5, "flying": 0.5, "psychic": 2, "ghost": 0.5, "dark": 2, "steel": 0.5, "fairy": 0.5},
    "rock": {"fire": 2, "ice": 2, "fighting": 0.5, "ground": 0.5, "flying": 2, "bug": 2, "steel": 0.5},
    "ghost": {"normal": 0, "psychic": 2, "ghost": 2, "dark": 0.5},
    "dragon": {"dragon": 2, "steel": 0.5, "fairy": 0},
    "dark": {"fighting": 0.5, "psychic": 2, "ghost": 2, "dark": 0.5, "fairy": 0.5},
    "steel": {"fire": 0.5, "water": 0.5, "electric": 0.5, "ice": 2, "rock": 2, "steel": 0.5, "fairy": 2},
    "fairy": {"fire": 0.5, "fighting": 2, "poison": 0.5, "dragon": 2, "dark": 2, "steel": 0.5}
}

def get_effectiveness(atk_type, def_types):
    multiplier = 1.0
    for dt in def_types:
        if atk_type in TYPE_CHART:
            multiplier *= TYPE_CHART[atk_type].get(dt, 1.0)
    return multiplier

# 3-2. 실전 기술 데이터베이스 (샘플)
MOVES_DB = {
    # 물리
    "Takle": {"name": "몸통박치기", "type": "normal", "cat": "phy", "pow": 40, "acc": 100},
    "Quick Attack": {"name": "전광석화", "type": "normal", "cat": "phy", "pow": 40, "acc": 100, "priority": 1},
    "Return": {"name": "은혜갚기", "type": "normal", "cat": "phy", "pow": 102, "acc": 100},
    "Close Combat": {"name": "인파이트", "type": "fighting", "cat": "phy", "pow": 120, "acc": 100},
    "Earthquake": {"name": "지진", "type": "ground", "cat": "phy", "pow": 100, "acc": 100},
    "Stone Edge": {"name": "스톤에지", "type": "rock", "cat": "phy", "pow": 100, "acc": 80, "crit": True},
    "Flare Blitz": {"name": "플레어드라이브", "type": "fire", "cat": "phy", "pow": 120, "acc": 100, "eff": "burn", "eff_rate": 10},
    "Waterfall": {"name": "폭포오르기", "type": "water", "cat": "phy", "pow": 80, "acc": 100, "eff": "flinch", "eff_rate": 20},
    "Thunder Punch": {"name": "번개펀치", "type": "electric", "cat": "phy", "pow": 75, "acc": 100, "eff": "paralysis", "eff_rate": 10},
    "Dragon Claw": {"name": "드래곤크루", "type": "dragon", "cat": "phy", "pow": 80, "acc": 100},
    "Crunch": {"name": "깨물어부수기", "type": "dark", "cat": "phy", "pow": 80, "acc": 100},
    "Iron Head": {"name": "아이언헤드", "type": "steel", "cat": "phy", "pow": 80, "acc": 100, "eff": "flinch", "eff_rate": 30},
    # 특수
    "Psychic": {"name": "사이코키네시스", "type": "psychic", "cat": "spe", "pow": 90, "acc": 100},
    "Shadow Ball": {"name": "섀도볼", "type": "ghost", "cat": "spe", "pow": 80, "acc": 100},
    "Thunderbolt": {"name": "10만볼트", "type": "electric", "cat": "spe", "pow": 90, "acc": 100, "eff": "paralysis", "eff_rate": 10},
    "Ice Beam": {"name": "냉동빔", "type": "ice", "cat": "spe", "pow": 90, "acc": 100, "eff": "freeze", "eff_rate": 10},
    "Flamethrower": {"name": "화염방사", "type": "fire", "cat": "spe", "pow": 90, "acc": 100, "eff": "burn", "eff_rate": 10},
    "Surf": {"name": "파도타기", "type": "water", "cat": "spe", "pow": 90, "acc": 100},
    "Energy Ball": {"name": "에너지볼", "type": "grass", "cat": "spe", "pow": 90, "acc": 100},
    "Sludge Bomb": {"name": "오물폭탄", "type": "poison", "cat": "spe", "pow": 90, "acc": 100, "eff": "poison", "eff_rate": 30},
    "Dragon Pulse": {"name": "용의파동", "type": "dragon", "cat": "spe", "pow": 85, "acc": 100},
    "Moonblast": {"name": "문포스", "type": "fairy", "cat": "spe", "pow": 95, "acc": 100},
    "Air Slash": {"name": "에어슬래시", "type": "flying", "cat": "spe", "pow": 75, "acc": 95, "eff": "flinch", "eff_rate": 30},
    # 변화기 (구현 복잡도상 일부 효과만 적용)
    "Hypnosis": {"name": "최면술", "type": "psychic", "cat": "status", "pow": 0, "acc": 60, "eff": "sleep", "eff_rate": 100},
    "Will-O-Wisp": {"name": "도깨비불", "type": "fire", "cat": "status", "pow": 0, "acc": 85, "eff": "burn", "eff_rate": 100},
    "Thunder Wave": {"name": "전기자석파", "type": "electric", "cat": "status", "pow": 0, "acc": 90, "eff": "paralysis", "eff_rate": 100},
    "Confuse Ray": {"name": "이상한빛", "type": "ghost", "cat": "status", "pow": 0, "acc": 100, "eff": "confusion", "eff_rate": 100},
}

# 3-3. 포켓몬 객체 생성 (Lv.50 실능 계산)
class Battler:
    def __init__(self, poke_id, is_player=True):
        self.is_player = is_player
        self.data = self.fetch_data(poke_id)
        
        # Lv.50 실능 계산 (개체값 31, 노력치 85 가정)
        # HP: (종족값*2 + 31 + 85/4)/2 + 50 + 10
        # Others: (종족값*2 + 31 + 85/4)/2 + 5
        base = self.data['stats']
        self.max_hp = int((base['hp']*2 + 31 + 21)/2 + 60)
        self.hp = self.max_hp
        self.atk = int((base['attack']*2 + 31 + 21)/2 + 5)
        self.defense = int((base['defense']*2 + 31 + 21)/2 + 5)
        self.sp_atk = int((base['special-attack']*2 + 31 + 21)/2 + 5)
        self.sp_def = int((base['special-defense']*2 + 31 + 21)/2 + 5)
        self.speed = int((base['speed']*2 + 31 + 21)/2 + 5)
        
        self.types = self.data['types'] # list
        self.name = self.data['name']
        self.img = self.data['img']
        self.status = None # burn, sleep, paralysis, poison, freeze
        self.status_turn = 0 # for sleep/confusion
        self.confusion = 0
        self.flinch = False
        
        # 기술 배치 자동 생성
        self.moves = self.assign_moves()

    def fetch_data(self, pid):
        # (기존 get_poke_data 활용, 캐싱됨)
        d = get_poke_data(pid)
        # API에서 타입과 스탯 상세 가져오기 위해 한 번 더 호출하거나 d를 확장해야 함
        # 여기서는 편의상 d에 stats와 types가 있다고 가정하고 get_poke_data 수정 필요
        # ** get_poke_data 함수를 아래에서 수정했음 ** return d

    def assign_moves(self):
        # 종족값 기반 물리/특수 판단
        is_phy = self.atk >= self.sp_atk
        moves = []
        
        # 1. 자속기 (STAB)
        for t in self.types:
            pool = [k for k,v in MOVES_DB.items() if v['type'] == t and (v['cat'] == ('phy' if is_phy else 'spe'))]
            if pool: moves.append(random.choice(pool))
            
        # 2. 견제기/서브웨폰 (부족하면 채움)
        while len(moves) < 3:
            pool = [k for k,v in MOVES_DB.items() if v['cat'] == ('phy' if is_phy else 'spe') and v['pow'] > 0]
            m = random.choice(pool)
            if m not in moves: moves.append(m)
            
        # 3. 변화기 1개
        pool_status = [k for k,v in MOVES_DB.items() if v['cat'] == 'status']
        moves.append(random.choice(pool_status))
        
        return moves[:4]

# 3-4. 데미지 계산 및 턴 실행
def run_turn(atkr, defr, move_key):
    logs = []
    move = MOVES_DB[move_key]
    
    # 1. 상태이상 체크 (행동 불가)
    if atkr.status == 'sleep':
        atkr.status_turn -= 1
        if atkr.status_turn <= 0:
            atkr.status = None
            logs.append(f"🔔 {atkr.name}은(는) 잠에서 깨어났다!")
        else:
            logs.append(f"💤 {atkr.name}은(는) 쿨쿨 자고 있다...")
            return 0, logs
    if atkr.status == 'freeze':
        if random.random() < 0.2:
            atkr.status = None
            logs.append(f"🧊 {atkr.name}의 얼음이 녹았다!")
        else:
            logs.append(f"🧊 {atkr.name}은(는) 얼어서 움직일 수 없다!")
            return 0, logs
    if atkr.status == 'paralysis' and random.random() < 0.25:
        logs.append(f"⚡ {atkr.name}은(는) 몸이 저려 움직일 수 없다!")
        return 0, logs
    if atkr.flinch:
        logs.append(f"😵 {atkr.name}은(는) 풀죽어서 움직일 수 없다!")
        atkr.flinch = False
        return 0, logs
    if atkr.confusion > 0:
        atkr.confusion -= 1
        logs.append(f"🌀 {atkr.name}은(는) 혼란에 빠져있다!")
        if random.random() < 0.33:
            dmg = int(((2*50/5+2) * 40 * atkr.atk / atkr.defense / 50 + 2))
            atkr.hp -= dmg
            logs.append(f"💥 {atkr.name}은(는) 자해했다! (-{dmg})")
            return 0, logs

    # 2. 명중 체크
    if random.randint(1, 100) > move['acc']:
        logs.append(f"🚫 {atkr.name}의 {move['name']}! ...빗나갔다!")
        return 0, logs

    # 3. 변화기 처리
    if move['cat'] == 'status':
        logs.append(f"✨ {atkr.name}의 {move['name']}!")
        eff = move.get('eff')
        if eff == 'sleep' and not defr.status:
            defr.status = 'sleep'; defr.status_turn = random.randint(2, 4)
            logs.append(f"💤 {defr.name}은(는) 잠들어버렸다!")
        elif eff == 'burn' and not defr.status and 'fire' not in defr.types:
            defr.status = 'burn'
            logs.append(f"🔥 {defr.name}은(는) 화상을 입었다!")
        elif eff == 'paralysis' and not defr.status and 'electric' not in defr.types:
            defr.status = 'paralysis'
            logs.append(f"⚡ {defr.name}은(는) 마비되었다!")
        elif eff == 'confusion' and defr.confusion == 0:
            defr.confusion = random.randint(2, 5)
            logs.append(f"🌀 {defr.name}은(는) 혼란에 빠졌다!")
        else:
            logs.append("...하지만 실패했다!")
        return 0, logs

    # 4. 데미지 계산 (공격기)
    # (Level*2/5 + 2) * Power * A/D / 50 + 2
    a = atkr.atk if move['cat'] == 'phy' else atkr.sp_atk
    d = defr.defense if move['cat'] == 'phy' else defr.sp_def
    
    # 화상 패널티 (물리)
    if atkr.status == 'burn' and move['cat'] == 'phy': a = int(a * 0.5)
    
    dmg = ((2 * 50 / 5 + 2) * move['pow'] * a / d / 50 + 2)
    
    # 보정 (자속, 상성, 급소, 난수)
    stab = 1.5 if move['type'] in atkr.types else 1.0
    type_eff = get_effectiveness(move['type'], defr.types)
    crit = 1.5 if random.randint(1, 24) == 1 else 1.0
    rand = random.uniform(0.85, 1.0)
    
    final_dmg = int(dmg * stab * type_eff * crit * rand)
    defr.hp -= final_dmg
    
    # 로그 작성
    logs.append(f"👊 {atkr.name}의 {move['name']}!")
    if crit > 1: logs.append("⚡ **급소에 맞았다!!**")
    if type_eff > 1: logs.append("🔥 **효과가 굉장했다!**")
    elif type_eff == 0: logs.append("👻 효과가 없는 것 같다...")
    elif type_eff < 1: logs.append("💧 효과가 별로인 듯하다...")
    
    # 부가 효과 (공격기)
    if 'eff' in move and random.randint(1, 100) <= move.get('eff_rate', 0):
        eff = move['eff']
        if eff == 'flinch': defr.flinch = True
        elif eff == 'burn' and not defr.status: defr.status = 'burn'; logs.append(f"🔥 {defr.name}은(는) 화상을 입었다!")
        elif eff == 'paralysis' and not defr.status: defr.status = 'paralysis'; logs.append(f"⚡ {defr.name}은(는) 마비되었다!")
        
    return final_dmg, logs

# ==========================================
# 4. API 데이터 함수 (수정됨: 스탯/타입 상세 포함)
# ==========================================
@st.cache_data(ttl=3600) 
def get_poke_data(poke_id):
    try:
        url = f"https://pokeapi.co/api/v2/pokemon/{poke_id}"
        res = requests.get(url, timeout=2).json()
        
        stats = {s['stat']['name']: s['base_stat'] for s in res['stats']}
        types = [t['type']['name'] for t in res['types']]
        
        total_stats = sum(stats.values())
        price = total_stats * 4
        rarity = "Normal"
        if total_stats >= 580: price = total_stats * 50; rarity = "Legendary"
        elif total_stats >= 500: price = total_stats * 15; rarity = "Rare"
        
        starters = list(range(1,10)) + list(range(152,161)) + list(range(252,261))
        if poke_id in starters: price = int(price * 2.0); rarity = "Starter" if rarity=="Normal" else rarity
            
        eng_name = res['name'].capitalize()
        kor_name = get_korean_name(eng_name)
        img_url = res['sprites']['front_default']
        
        return {
            "id": poke_id, "name": kor_name, "types": types, "stats": stats,
            "price": int(price), "rarity": rarity, "img": img_url
        }
    except: return None

def get_korean_name(eng_name):
    # 한글 매핑 (생략된 부분 포함해야 함, 여기선 예시 유지)
    mapping = {
        "Bulbasaur": "이상해씨", "Charmander": "파이리", "Squirtle": "꼬부기", "Pikachu": "피카츄",
        "Charizard": "리자몽", "Dragonite": "망나뇽", "Mewtwo": "뮤츠", "Gengar": "팬텀",
        "Arceus": "아르세우스", "Rayquaza": "레쿠쟈", "Lugia": "루기아", "Ho-oh": "칠색조",
        "Gyarados": "갸라도스", "Snorlax": "잠만보", "Eevee": "이브이", "Lucario": "루카리오",
        "Garchomp": "한카리아스", "Metagross": "메타그로스", "Tyranitar": "마기라스"
    }
    return mapping.get(eng_name, eng_name) # 실제론 더 많이 필요

def get_type_icon(type_name):
    icons = {"fire": "🔥", "water": "💧", "grass": "🌿", "electric": "⚡", "psychic": "🔮", "dragon": "🐲", "normal": "⚪", "fighting": "👊"}
    return icons.get(type_name, type_name)

# ==========================================
# 5. UI 구성
# ==========================================
st.set_page_config(page_title="관희의 성장 RPG", page_icon="⚔️", layout="centered")

st.markdown("""
<style>
    .shadow-img { filter: brightness(0) opacity(0.1); width: 80px; }
    .color-img { filter: brightness(1); width: 80px; }
    .battle-log { background-color: #f0f2f6; padding: 10px; border-radius: 5px; height: 150px; overflow-y: auto; font-size: 14px; }
    .move-btn { height: 60px; font-weight: bold; }
</style>
""", unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ 관리")
    st.write(f"보유 골드: **{gold} G**")
    if st.button("⚠️ 도감 초기화"): reset_collection()

# 헤더 & 메인 메뉴
c1, c2 = st.columns([2,1])
with c1: st.markdown(f"<h2 style='margin:0;'>Lv.{level} 관희 <span style='font-size:16px; color:#555'>({current_xp}/{next_level_xp} XP)</span></h2>", unsafe_allow_html=True)
with c2: st.markdown(f"<div style='text-align:right; font-size:20px; font-weight:bold; color:#D4AC0D;'>💰 {gold} G</div>", unsafe_allow_html=True)
st.progress(min(current_xp/next_level_xp, 1.0))
st.divider()

menu = st.radio("", ["🏠 홈", "🏥 포켓몬 센터", "⚔️ 실전 배틀", "🎒 도감"], horizontal=True)

if menu == "🏠 홈":
    st.info("운동/공부 기록하고 골드를 모으세요!")
    # (기록 UI 생략 - 기존 코드 유지하거나 필요 시 복구)
    # 지면상 생략했으나 V26의 입력 탭 코드를 여기에 넣으면 됨
    
    t1, t2 = st.tabs(["📝 기록하기", "📜 지난 기록"])
    with t1:
        st.subheader("🏃‍♂️ 피지컬")
        c1, c2, c3 = st.columns(3)
        with c1:
            val = st.number_input("달리기 (km)", 0.0, 42.195, 5.0, 0.1)
            if st.button("기록 (50G/km)", key="run", use_container_width=True):
                if val>0: add_xp(val*50, f"🏃 달리기 {val}km", val)
        with c2:
            val = st.number_input("푸쉬업 (회)", 0, 1000, 30, 5)
            if st.button("기록 (0.5G/회)", key="push", use_container_width=True):
                if val>0: add_xp(val*0.5, f"💪 푸쉬업 {val}회", val)
        with c3:
            val = st.number_input("스쿼트 (회)", 0, 1000, 50, 5)
            if st.button("기록 (0.5G/회)", key="squat", use_container_width=True):
                if val>0: add_xp(val*0.5, f"🦵 스쿼트 {val}회", val)

        st.subheader("🧠 뇌지컬")
        c4, c5 = st.columns(2)
        with c4:
            val = st.number_input("자기계발 (분)", 0, 1440, 60, 10)
            if st.button("기록 (1G/분)", key="study", use_container_width=True):
                if val>0: add_xp(val, f"🧠 자기계발 {val}분", val)
        with c5:
            val = st.number_input("독서 (쪽)", 0, 1000, 20, 5)
            if st.button("기록 (1G/쪽)", key="read", use_container_width=True):
                if val>0: add_xp(val, f"📖 독서 {val}쪽", val)
        
        st.subheader("🛡️ 습관")
        ch1, ch2, ch3 = st.columns(3)
        if ch1.button("💰 무지출 (20G)", use_container_width=True): add_xp(20, "💰 무지출", 0)
        if ch2.button("💧 물 (10G)", use_container_width=True): add_xp(10, "💧 물 마시기", 0)
        if ch3.button("🧹 청소 (15G)", use_container_width=True): add_xp(15, "🧹 방 청소", 0)
    with t2:
         if logs: st.dataframe(pd.DataFrame(logs)[['Time','Action','XP']], use_container_width=True)

elif menu == "🏥 포켓몬 센터":
    st.subheader("🎲 500G 뽑기")
    if st.button("❓ 랜덤 뽑기", type="primary"):
        if gold >= 500:
            pid = random.randint(1, 649); p = get_poke_data(pid)
            if p: save_pokemon(pid, p['name'], "Gacha", 500, p['types'][0])
        else: st.toast("돈 부족!", icon="💸")
    # (상점 리스트 코드 생략 - V26 유지)
    
elif menu == "🎒 도감":
    # (도감 코드 생략 - V26 유지)
    if 'dex_page' not in st.session_state: st.session_state['dex_page'] = 0
    DEX_PER_PAGE = 24
    page = st.session_state['dex_page']
    start_id = page * DEX_PER_PAGE + 1
    end_id = start_id + DEX_PER_PAGE
    
    c_prev, c_page, c_next = st.columns([1, 2, 1])
    with c_prev:
        if page > 0:
            if st.button("◀ 이전"): st.session_state['dex_page'] -= 1; st.rerun()
    with c_page:
        st.markdown(f"<div style='text-align:center;'><b>도감 {page+1}권</b> (No.{start_id}~{end_id-1})</div>", unsafe_allow_html=True)
    with c_next:
        if end_id < 650:
            if st.button("다음 ▶"): st.session_state['dex_page'] += 1; st.rerun()
    
    cols = st.columns(4)
    for i, pid in enumerate(range(start_id, end_id)):
        if pid > 649: break
        with cols[i % 4]:
            img_url = f"https://raw.githubusercontent.com/PokeAPI/sprites/master/sprites/pokemon/{pid}.png"
            if pid in my_pokemon:
                st.markdown(f"<div style='text-align:center;'><img src='{img_url}' class='color-img'><br><small>No.{pid}<br>{my_pokemon[pid]['Name']}</small></div>", unsafe_allow_html=True)
            else:
                st.markdown(f"<div style='text-align:center; opacity:0.3;'><img src='{img_url}' class='shadow-img'><br><small>No.{pid}<br>???</small></div>", unsafe_allow_html=True)


elif menu == "⚔️ 실전 배틀":
    st.title("🔥 Lv.50 실전 배틀")
    
    if 'battle_state' not in st.session_state: st.session_state['battle_state'] = 'prep' # prep, fighting, end
    if 'turn_logs' not in st.session_state: st.session_state['turn_logs'] = []
    
    if st.session_state['battle_state'] == 'prep':
        if not my_pokemon: st.warning("포켓몬이 없습니다."); st.stop()
        
        my_names = [f"{v['Name']} (No.{k})" for k, v in my_pokemon.items()]
        choice = st.selectbox("내 포켓몬 선택:", my_names)
        my_id = int(choice.split("No.")[1].replace(")",""))
        
        if st.button("⚔️ 배틀 시작!", type="primary", use_container_width=True):
            # 배틀 초기화
            p1 = Battler(my_id, True)
            p2 = Battler(random.randint(1, 649), False)
            
            st.session_state['p1'] = p1
            st.session_state['p2'] = p2
            st.session_state['battle_state'] = 'fighting'
            st.session_state['turn_logs'] = [f"⚔️ 배틀 시작! {p1.name} vs {p2.name}"]
            st.rerun()
            
    elif st.session_state['battle_state'] == 'fighting':
        p1 = st.session_state['p1']
        p2 = st.session_state['p2']
        
        # UI: 체력바 및 정보
        c1, c2, c3 = st.columns([2, 0.5, 2])
        with c1:
            st.image(p1.img, width=100)
            st.write(f"**{p1.name}** (Lv.50)")
            hp_per = max(0, p1.hp / p1.max_hp)
            st.progress(hp_per)
            st.caption(f"HP: {p1.hp}/{p1.max_hp} {get_type_icon(p1.status) if p1.status else ''}")
        with c2: st.markdown("## VS")
        with c3:
            st.image(p2.img, width=100)
            st.write(f"**{p2.name}** (Lv.50)")
            hp_per2 = max(0, p2.hp / p2.max_hp)
            st.progress(hp_per2)
            st.caption(f"HP: {p2.hp}/{p2.max_hp} {get_type_icon(p2.status) if p2.status else ''}")
            
        st.divider()
        
        # 로그창
        log_txt = "\n".join(st.session_state['turn_logs'])
        st.text_area("배틀 로그", log_txt, height=150, disabled=True)
        
        # 기술 선택 (2x2 그리드)
        st.write("🔻 기술 선택")
        mc1, mc2 = st.columns(2)
        
        # 플레이어 턴 처리
        for i, m_key in enumerate(p1.moves):
            m = MOVES_DB[m_key]
            btn_col = mc1 if i % 2 == 0 else mc2
            if btn_col.button(f"{m['name']}\n({m['type']}/{m['cat']})", key=f"mv_{i}", use_container_width=True):
                
                # 1. 스피드 판정 (마비 고려)
                sp1 = p1.speed * (0.5 if p1.status=='paralysis' else 1)
                sp2 = p2.speed * (0.5 if p2.status=='paralysis' else 1)
                
                # 우선도 체크 (전광석화 등) -> 단순화: 스피드만 비교
                first, second = (p1, p2) if sp1 >= sp2 else (p2, p1)
                first_move = m_key if first == p1 else random.choice(p2.moves)
                second_move = random.choice(p2.moves) if first == p1 else m_key
                
                # 선공 실행
                _, l1 = run_turn(first, second, first_move)
                st.session_state['turn_logs'].extend(l1)
                
                if second.hp <= 0:
                    st.session_state['turn_logs'].append(f"💀 {second.name}은(는) 쓰러졌다!")
                    st.session_state['battle_state'] = 'end'
                    st.session_state['result'] = 'win' if first == p1 else 'lose'
                    st.rerun()
                
                # 후공 실행
                _, l2 = run_turn(second, first, second_move)
                st.session_state['turn_logs'].extend(l2)
                
                if first.hp <= 0:
                    st.session_state['turn_logs'].append(f"💀 {first.name}은(는) 쓰러졌다!")
                    st.session_state['battle_state'] = 'end'
                    st.session_state['result'] = 'lose' if first == p1 else 'win'
                    st.rerun()
                    
                # 턴 종료 (화상/독 데미지)
                for p in [p1, p2]:
                    if p.status == 'burn':
                        dmg = int(p.max_hp / 16); p.hp -= dmg
                        st.session_state['turn_logs'].append(f"🔥 {p.name}은(는) 화상 데미지를 입었다 (-{dmg})")
                    if p.status == 'poison':
                        dmg = int(p.max_hp / 8); p.hp -= dmg
                        st.session_state['turn_logs'].append(f"☠️ {p.name}은(는) 독 데미지를 입었다 (-{dmg})")
                    if p.hp <= 0:
                        st.session_state['battle_state'] = 'end'
                        st.session_state['result'] = 'win' if p == p2 else 'lose'
                        
                st.rerun()

    elif st.session_state['battle_state'] == 'end':
        res = st.session_state['result']
        if res == 'win':
            st.success("🏆 승리했습니다! 명예로운 승리!")
            st.balloons()
            # 승리 기록
            ts = (datetime.now() + timedelta(hours=9)).strftime("%Y-%m-%d %H:%M:%S")
            ws_logs.append_row([ts, "⚔️ 배틀 승리", 0, 1])
        else:
            st.error("💀 패배했습니다... 다음엔 더 강해져서 오세요.")
            
        if st.button("다시 배틀하기"):
            st.session_state['battle_state'] = 'prep'
            st.rerun()
"""The Pet Parent Games: a small-room, multiplayer Streamlit game show.

Run: streamlit run app.py
For multi-device use, deploy with persistent shared SQLite storage or run on a
single machine reachable by everyone's phones on the same Wi-Fi network.
"""
import io
import hmac
import os
import random
import sqlite3
import time
from pathlib import Path

import pandas as pd
import plotly.express as px
import qrcode
import streamlit as st
from features import join_code, match_ui, setup_trivia, trivia_ui
from matching import host_quiz_answers

BASE = Path(__file__).resolve().parent
DB = Path(os.getenv("PET_GAME_DB", str(BASE / "pet_games.sqlite3")))
HOST_PIN = os.getenv("PET_GAME_HOST_PIN", "")

st.set_page_config(page_title="The Pet Parent Games 🐾", page_icon="🐾", layout="wide", initial_sidebar_state="collapsed")
st.markdown("""<style>
:root { color-scheme: dark; }
.stApp, [data-testid="stAppViewContainer"] {background:#15151d;color:#f5f3f7;}
[data-testid="stHeader"] {background:#15151d;}
[data-testid="stSidebar"] {background:#20202c;color:#f5f3f7;}
h1,h2,h3,h4,h5,h6 {color:#f5f3f7;}
[data-testid="stCaptionContainer"] {color:#c6c2d1;}
a {color:#ff9dca;}
div.stButton > button[kind="primary"],
[data-testid="stFormSubmitButton"] button[kind="primary"],
button[data-testid="stBaseButton-primaryFormSubmit"] {
    background:#ff9dca;border-color:#ff9dca;color:#211321;
}
button[data-testid="stBaseButton-primaryFormSubmit"] p,
button[data-testid="stBaseButton-primary"] p {color:#211321;}
[class*="st-key-answer_"] button {min-height:110px;white-space:normal;color:#f5f3f7;font-weight:700;border-width:1px;border-radius:12px;background:#262633;}
[class*="st-key-answer_paw_"] button {background:#262633;border-color:#ff9dca;}
[class*="st-key-answer_bone_"] button {background:#262633;border-color:#75dce0;}
[class*="st-key-answer_fish_"] button {background:#262633;border-color:#b6bfff;}
[class*="st-key-answer_feather_"] button {background:#262633;border-color:#f3cc73;}
button:focus-visible, input:focus-visible {outline:3px solid #ff9dca;outline-offset:2px;}
</style>""", unsafe_allow_html=True)


def dark_chart(fig):
    fig.update_layout(template="plotly_dark", paper_bgcolor="#15151d",
                      plot_bgcolor="#20202c", font_color="#f5f3f7")
    return fig

PETS = [
    {"name":"London", "species":"Dog", "role":"Tiny CEO", "bio":"Toy poodle. Big personality. Loves carpet and crickets.", "photo":"london.jpg"},
    {"name":"Wilford Brimley", "species":"Cat", "role":"Head of Investigations", "bio":"Food explorer. Loves cardboard and fried chicken.", "photo":"wilford.jpg"},
    {"name":"Potato", "species":"Cat", "role":"Window Surveillance Director", "bio":"Professional window watcher and getaway runner.", "photo":"potato.jpg"},
]
SCENARIOS = [
    {"title":"3 AM Emergency", "story":"Your pet starts making a mysterious noise at 3 AM. What do you do?", "choices":[
        ("Investigate immediately", -5,-20,5,"You found nothing. Your pet found entertainment."),
        ("Ignore it and try to sleep", 0,-15,-10,"The noise is now louder. Outstanding."),
        ("Check they're safe, then settle them", -5,-10,10,"Reasonable pet parenting. Still tired, though.")]},
    {"title":"The Expensive Surprise", "story":"Your pet destroys something you just bought. Your response?", "choices":[
        ("Buy a replacement and pet-proof the room",-40,0,15,"Your wallet is crying, but future-you is grateful."),
        ("Give a 10-minute lecture",0,0,-15,"Your pet does not speak English."),
        ("Ignore the hazard and move on",0,0,-25,"Risk management has left the chat.")]},
    {"title":"Meeting Takeover", "story":"Your pet demands attention during an important work call.", "choices":[
        ("Introduce them to the team",0,0,15,"They are now more popular than you."),
        ("Offer an appropriate toy",-10,0,10,"You bought approximately four minutes of peace."),
        ("Let them walk across your keyboard",0,0,-15,"Your pet has sent an email to the CEO.")]},
    {"title":"The Vet Bill", "story":"Your pet needs an unexpected vet visit. What's your plan?", "choices":[
        ("Arrange veterinary care and use emergency savings",-55,0,20,"Responsible choice. This is why emergency funds matter."),
        ("Ask about payment options and arrange care",-30,0,15,"Good planning: get needed care and discuss costs."),
        ("Wait indefinitely to save money",0,0,-35,"Delaying needed care can make things worse.")]},
]

def connect():
    DB.parent.mkdir(parents=True, exist_ok=True)
    con=sqlite3.connect(str(DB), timeout=15)
    con.row_factory=sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA busy_timeout=15000")
    return con

def init():
    with connect() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS players (name TEXT PRIMARY KEY COLLATE NOCASE, joined INTEGER DEFAULT 0);
        CREATE TABLE IF NOT EXISTS matches (name TEXT PRIMARY KEY COLLATE NOCASE, result TEXT, answers TEXT);
        CREATE TABLE IF NOT EXISTS survival (name TEXT, round_idx INTEGER, choice_idx INTEGER, PRIMARY KEY(name,round_idx));
        """)
        c.execute("INSERT OR IGNORE INTO settings VALUES('stage','lobby')")
        c.execute("INSERT OR IGNORE INTO settings VALUES('round_idx','0')")

def setting(k):
    with connect() as c:
        r=c.execute("SELECT value FROM settings WHERE key=?",(k,)).fetchone()
        return r["value"] if r else ""

def set_setting(k,v):
    with connect() as c:
        c.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(k,str(v)))

def rows(sql,params=()):
    with connect() as c:
        return [dict(x) for x in c.execute(sql,params).fetchall()]

def execute(sql,params=()):
    with connect() as c:
        c.execute(sql,params)

def image_pet(pet, width=260):
    path=BASE/"assets"/pet["photo"]
    if path.exists(): st.image(str(path),width=width)
    else: st.info(f"📷 Add assets/{pet['photo']} to show {pet['name']}'s photo")

def survival_scores(name):
    choices=rows("SELECT round_idx,choice_idx FROM survival WHERE name=?",(name,))
    cash,sleep,sanity=100,100,100
    for r in choices:
        delta=SCENARIOS[r["round_idx"]]["choices"][r["choice_idx"]]
        cash+=delta[1];sleep+=delta[2];sanity+=delta[3]
    return max(0,cash),max(0,sleep),max(0,sanity)

init()
setup_trivia(connect)
trivia_live=setting('stage')=='trivia'
if trivia_live:
    st.markdown("""<style>
    [data-testid="stMainBlockContainer"] {max-width:1000px;padding-top:2rem;}
    [data-testid="stMain"] h3 {font-size:2rem;line-height:1.3;margin:1rem 0 1.5rem;}
    </style>""",unsafe_allow_html=True)
else:
    st.title("🐾 The Pet Parent Games")
    st.caption("Find your animal match, test your trivia knowledge, and compete for the top spot.")
role=st.sidebar.radio("Choose your view",["🎮 Player","🎤 Host"])

if role=="🎤 Host":
    if not HOST_PIN:
        st.info("Host access is being configured. Players can join while setup finishes.")
        st.stop()
    if not st.session_state.get("host_authenticated", False):
        with st.sidebar.form("host_login", clear_on_submit=True):
            pin = st.text_input("Host PIN", type="password")
            login = st.form_submit_button("Log in", type="primary")
        if login:
            if not pin.strip():
                st.sidebar.error("Enter your host PIN.")
            elif hmac.compare_digest(pin.encode("utf-8"), HOST_PIN.encode("utf-8")):
                st.session_state.host_authenticated = True
                st.rerun()
            else:
                st.sidebar.error("Incorrect host PIN. Please try again.")
        st.info("Enter the host PIN and click Log in, or press Enter.")
        st.stop()
    st.sidebar.success("Logged in as host.")
    if st.sidebar.button("Log out"):
        st.session_state.host_authenticated = False
        st.rerun()
    with st.expander('Host controls', expanded=not trivia_live):
        st.subheader("🎤 Host control room")
        st.info("Share this screen in the room or on your video call. Players join on their own devices.")
        url=st.text_input("Public/player URL (for QR code)",value=os.getenv("PET_GAME_PUBLIC_URL", "https://pet-parent-games-genababy.streamlit.app"))
        qr=qrcode.make(url)
        b=io.BytesIO();qr.save(b,format="PNG")
        a,bcol=st.columns([1,3])
        with a: st.image(b.getvalue(),caption="Scan to join",width=260)
        with bcol: st.code(url);st.caption("Share this public link or QR code with people in the room and working from home.")
        stages=[("lobby","Join the Show"),("match","Find Your Match"),("trivia","🏆 Pet Trivia Live"),("survival","Pet Parent Simulator"),("results","Final Awards")]
        stage=setting("stage")
        stage_labels=dict(stages)
        chosen=st.selectbox("Live game",[x[0] for x in stages],index=[x[0] for x in stages].index(stage),format_func=lambda x:stage_labels[x])
        if st.button("🚀 Switch live game",type="primary"):
            set_setting("stage",chosen);st.rerun()
        st.write("**Currently live:**",stage_labels.get(stage,stage))
        players=rows("SELECT name FROM players ORDER BY joined")
        st.metric("Players joined",len(players))
        if players: st.write(", ".join(x["name"] for x in players))
        st.divider()
    if stage=="match":
        data=rows("SELECT result,COUNT(*) AS count FROM matches WHERE answers LIKE ? GROUP BY result ORDER BY count DESC", ('%"version": 4%',))
        st.subheader("💘 Live pet matches")
        if data: st.plotly_chart(dark_chart(px.bar(pd.DataFrame(data),x="result",y="count",color="result",title="Who's matching with whom?")),use_container_width=True)
        else: st.write("Waiting for matches...")
        host_quiz_answers(rows)
    elif stage=="trivia":
        trivia_ui(True, "", connect, rows, execute)
    elif stage=="survival":
        idx=int(setting("round_idx"));s=SCENARIOS[idx]
        st.subheader(f"🎮 Round {idx+1}: {s['title']}");st.write(s["story"])
        for i,c in enumerate(s["choices"]): st.write(f"**{chr(65+i)}.** {c[0]}")
        tally=rows("SELECT choice_idx,COUNT(*) AS count FROM survival WHERE round_idx=? GROUP BY choice_idx",(idx,))
        if tally:
            data=pd.DataFrame([{"Choice":chr(65+r["choice_idx"]),"Votes":r["count"]} for r in tally])
            st.plotly_chart(dark_chart(px.bar(data,x="Choice",y="Votes",title="Audience decisions")),use_container_width=True)
        if st.button("➡️ Next scenario",disabled=idx==len(SCENARIOS)-1):
            set_setting("round_idx",idx+1);st.rerun()
        if st.button("↩️ Return to first scenario"):
            set_setting("round_idx",0);st.rerun()
    elif stage=="results":
        st.subheader("🏆 Final survival leaderboard")
        board=[]
        for p in players:
            n=p["name"];cash,sleep,sanity=survival_scores(n)
            count=rows("SELECT COUNT(*) AS n FROM survival WHERE name=?",(n,))[0]["n"]
            if count:
                board.append({"Player":n,"Money":cash,"Sleep":sleep,"Sanity":sanity,"Score":round((cash+sleep+sanity)/3),"Rounds":count})
        if board: st.dataframe(pd.DataFrame(board).sort_values(["Score","Rounds"],ascending=False),hide_index=True,use_container_width=True)
        else: st.write("No survival scores yet.")
    else:
        st.subheader("👋 Welcome to the show!")
        st.write("Find your animal match, test your trivia knowledge, and compete for the top spot.")
        st.caption("Players can join from the room or from home. Start a game when everyone is ready.")
    st.divider()
    with st.expander("⚠️ Reset all game data (host only)"):
        st.warning("This permanently clears nicknames, quiz results, and scores.")
        if st.button("Reset everything",type="secondary"):
            with connect() as c:
                for t in ("players","matches","survival","trivia_votes"): c.execute(f"DELETE FROM {t}")
            execute("UPDATE trivia_state SET game=game+1, question=-1, phase='waiting', deadline=0 WHERE id=1")
            set_setting("stage","lobby");set_setting("round_idx",0);st.rerun()
    @st.fragment(run_every="3s")
    def host_refresh():
        st.caption(f"Live responses saved • {len(rows('SELECT name FROM players'))} players connected • updated {time.strftime('%H:%M:%S')}")
        if st.button("🔄 Refresh live charts and results"): st.rerun()
    host_refresh()
else:
    if "player_name" not in st.session_state: st.session_state.player_name=""
    if not st.session_state.player_name:
        st.subheader("Join the show 🎟️")
        st.markdown("**Play here, or scan to join on your phone.**")
        join_code()
        with st.form("join"):
            nickname=st.text_input("Your nickname",max_chars=24,placeholder="e.g. Cat Mom 3000")
            submitted=st.form_submit_button("Join 🐾",type="primary")
        if submitted:
            nickname=nickname.strip()
            if len(nickname)<2: st.error("Enter at least two characters.")
            else:
                try:
                    execute("INSERT INTO players(name,joined) VALUES(?,?)",(nickname,int(time.time())))
                    st.session_state.player_name=nickname;st.rerun()
                except sqlite3.IntegrityError: st.error("That nickname is taken. Choose another!")
        st.stop()
    name=st.session_state.player_name
    if not trivia_live:st.success(f"Welcome, {name}! 🐾")
    @st.fragment(run_every="3s")
    def player_game():
        stage=setting("stage")
        if stage=="lobby":
            st.subheader("Waiting for the host 🎤")
            st.write("You’re in! Get ready to find your animal match and compete in pet trivia.")
            st.caption("The next game will appear here when the host starts it.")
            join_code()
        elif stage=="match":
            match_ui(name, rows, execute)
        elif stage=="trivia":
            trivia_ui(False, name, connect, rows, execute)
        elif stage=="survival":
            idx=int(setting("round_idx"));s=SCENARIOS[idx]
            st.subheader(f"🎮 {s['title']}");st.write(s["story"])
            existing=rows("SELECT choice_idx FROM survival WHERE name=? AND round_idx=?",(name,idx))
            if existing:
                c=s["choices"][existing[0]["choice_idx"]]
                st.success(c[4]);cash,sleep,sanity=survival_scores(name)
                st.metric("💸 Money",f"${cash}");st.metric("💤 Sleep",f"{sleep}%");st.metric("🧠 Sanity",f"{sanity}%")
                st.caption("Waiting for the next scenario...")
            else:
                for i,c in enumerate(s["choices"]):
                    if st.button(f"{chr(65+i)}. {c[0]}",key=f"survival_{idx}_{i}",use_container_width=True):
                        execute("INSERT OR IGNORE INTO survival VALUES(?,?,?)",(name,idx,i));st.rerun()
        else:
            st.subheader("🏆 You survived the Pet Parent Games!")
            cash,sleep,sanity=survival_scores(name)
            st.write(f"**Your final stats:** 💸 ${cash} · 💤 {sleep}% · 🧠 {sanity}%")
            st.write("Thanks for playing!")
    player_game()
    if not trivia_live:st.caption("The game checks for host updates every few seconds. If a new round doesn't appear, refresh the page.")

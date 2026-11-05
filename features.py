"""Breed matching and multiplayer trivia, shared by host and player views."""
import io
import os
import html
import hashlib
import json
import math
import time
import pandas as pd
import qrcode
import streamlit as st
import streamlit.components.v1 as components

PUBLIC_URL = os.getenv('PET_GAME_PUBLIC_URL', 'https://pet-parent-games-genababy.streamlit.app')
from matching import match_ui

def join_code(url=None):
    url=url or PUBLIC_URL
    if not url:
        st.caption('Use the public game link shared by your host.')
        return
    image=io.BytesIO(); qrcode.make(url).save(image,format='PNG')
    st.image(image.getvalue(),width=240,caption='Scan to join · works from home too')
    st.markdown(f'[Open the player link]({url})')

# Fact-checked general animal trivia. Sources appear only after the reveal.
TRIVIA = [('Which of these dog breeds is considered hypoallergenic?', ['Golden Retriever', 'Beagle', 'Poodle', 'German Shepherd'], 2, 'Poodles are commonly described as hypoallergenic because their curly coats shed very little.'), ('An octopus has eight arms. How many hearts is it working with?', ['One', 'Two', 'Three', 'Eight'], 2, 'Three: two move blood through the gills, and one sends it around the body.'), ('Which flavor can cats NOT taste?', ['Salty', 'Sweet', 'Bitter', 'Sour'], 1, 'Cats lack a working sweet-taste receptor. The sweet part of your dessert is lost on them.'), ('Which of these animals has the MALE carry the pregnancy and give birth?', ['Clownfish', 'Emperor penguin', 'Sea turtle', 'Seahorse'], 3, 'Male seahorses carry developing young in a brood pouch and give birth. Penguin dads incubate eggs, which is different.'), ('A flamingo’s pink color comes mainly from…', ['Sun exposure', 'Pigments in its food', 'Being born pink', 'The color of its lake'], 1, 'Pigments from their diet produce the pink color. Their food supplies the color, not the water around them.'), ('Butterflies have taste receptors on which unlikely body part?', ['Wings', 'Eyes', 'Feet', 'The tip of the abdomen only'], 2, 'Their feet have taste receptors, helping them check plants before laying eggs. They also have receptors elsewhere.'), ('Why do hamsters stuff food into their cheeks?', ['To carry it back and stash it', 'To help them breathe', 'To look bigger', 'To cool themselves down'], 0, 'Their stretchy cheek pouches are built for carrying food back to a safe spot to eat or store.'), ('A shark’s skeleton is made mainly of what?', ['Cartilage', 'Bone', 'Keratin — like fingernails', 'A shell hidden under its skin'], 0, 'Cartilage supports the skeleton. It is the same general material found in your ears and the tip of your nose.'), ('Which of these mammals lays eggs?', ['Platypus only', 'Echidna only', 'Neither — mammals never lay eggs', 'Both platypus and echidna'], 3, 'Both! They belong to the monotremes: mammals that lay eggs and produce milk for their young.'), ('FINAL ROUND: Which of these has individual fingerprints similar to ours?', ['Penguin', 'Koala', 'Dolphin', 'Snake'], 1, 'Koalas have individual fingerprints with ridge patterns similar to human fingerprints.')]
TRIVIA_SOURCES = ['https://www.akc.org/expert-advice/lifestyle/hypoallergenic-breeds-poodle-schnauzer-allergies/', 'https://ocean.si.edu/ocean-life/invertebrates/octopuses-squids-and-relatives', 'https://pmc.ncbi.nlm.nih.gov/articles/PMC2063449/', 'https://oceanservice.noaa.gov/facts/seahorse.html', 'https://animals.sandiegozoo.org/animals/flamingo', 'https://www.si.edu/object/silgoi_68308', 'https://www.rspca.org.uk/adviceandwelfare/pets/rodents/hamsters/diet', 'https://www.fisheries.noaa.gov/national/outreach-and-education/fun-facts-about-shocking-sharks', 'https://www.nhm.ac.uk/discover/the-platypus-puzzle.html', 'https://www.sydney.edu.au/study/student-life/student-news/2018/09/10/9-things-you-need-to-know-about-koalas.html']
ICONS=['🐾','🦴','🐟','🪶']

def setup_trivia(connect):
    with connect() as c:
        c.executescript('''
        CREATE TABLE IF NOT EXISTS trivia_state (id INTEGER PRIMARY KEY CHECK(id=1), game INTEGER DEFAULT 0, question INTEGER DEFAULT -1, phase TEXT DEFAULT 'waiting', deadline REAL DEFAULT 0);
        INSERT OR IGNORE INTO trivia_state(id) VALUES(1);
        CREATE TABLE IF NOT EXISTS trivia_votes (game INTEGER, question INTEGER, name TEXT COLLATE NOCASE, answer INTEGER, points INTEGER, PRIMARY KEY(game,question,name));
        ''')

def state(rows): return rows('SELECT * FROM trivia_state WHERE id=1')[0]

def board(rows,game,podium=False):
    players=rows('SELECT name FROM players ORDER BY joined')
    scores={r['name'].casefold():r for r in rows('SELECT name,SUM(points) AS Points,SUM(points>0) AS Correct FROM trivia_votes WHERE game=? GROUP BY name',(game,))}
    data=[{'Player':p['name'],'Points':scores.get(p['name'].casefold(),{}).get('Points',0),'Correct':scores.get(p['name'].casefold(),{}).get('Correct',0)} for p in players]
    if not data:
        st.info('Players will appear here when they join.')
        return
    data.sort(key=lambda r:-r['Points'])
    for i,r in enumerate(data):
        r['Rank']=next(j+1 for j,x in enumerate(data) if x['Points']==r['Points'])
    icons=['🐾','🦊','🐻','🐼','🐨','🦁','🐸','🐧']
    def avatar(name):return icons[int(hashlib.sha256(name.encode()).hexdigest()[:4],16)%len(icons)]
    def card(r,position):
        name=html.escape(r['Player'])
        return f'<div class="podium-seat seat-{position}"><div class="podium-avatar">{avatar(r["Player"])}</div><div class="podium-name">{name}</div><div class="podium-score">{r["Points"]:,} pts</div><div class="podium-step"><strong>{r["Rank"]}</strong><span>PLACE</span></div></div>'
    content=''
    if podium:
        finalists=data[:3]
        order=[1,0,2] if len(finalists)==3 else [1,0] if len(finalists)==2 else [0]
        content+='<div class="podium-stage">'+''.join(card(finalists[i],i+1) for i in order)+'</div>'
    content+='<div class="ranked-players">'
    for r in data:
        name=html.escape(r['Player'])
        content+=f'<div class="rank-card {"rank-first" if r["Rank"]==1 else ""}"><span class="rank-number">{r["Rank"]}</span><span class="rank-avatar">{avatar(r["Player"])}</span><span class="rank-name">{name}</span><span class="rank-score">{r["Points"]:,}<small>points</small></span></div>'
    content+='</div>'
    st.html("""<style>
    .ranked-players {display:grid;gap:12px;margin:22px 0;font-family:inherit;}
    .rank-card {display:flex;align-items:center;gap:18px;background:#292535;border:1px solid #49415c;border-radius:14px;padding:18px 22px;color:#f5f3f7;}
    .rank-card.rank-first {background:#3a2b48;border-color:#ff9dca;}
    .rank-number {font-size:24px;font-weight:800;min-width:28px;color:#d1c5e5;}
    .rank-avatar {font-size:30px;}
    .rank-name {flex:1;min-width:0;overflow-wrap:anywhere;font-size:20px;font-weight:700;}
    .rank-score {font-size:27px;font-weight:800;text-align:right;white-space:nowrap;}
    .rank-score small {display:block;font-size:12px;font-weight:400;color:#c9c0d4;}
    .podium-stage {display:flex;align-items:flex-end;justify-content:center;gap:14px;padding:30px 12px 0;background:#211b30;border-radius:20px;font-family:inherit;color:#f5f3f7;}
    .podium-seat {width:30%;max-width:270px;text-align:center;min-width:0;}
    .podium-avatar {font-size:48px;margin-bottom:10px;}
    .podium-name {font-size:21px;font-weight:800;overflow-wrap:anywhere;}
    .podium-score {font-size:16px;color:#d1c5e5;margin:8px 0 18px;}
    .podium-step {display:flex;flex-direction:column;justify-content:center;min-height:100px;background:#423451;border-radius:12px 12px 0 0;}
    .seat-1 .podium-step {min-height:170px;background:#694563;border-top:3px solid #ff9dca;}
    .seat-2 .podium-step {min-height:125px;background:#49405e;}
    .podium-step strong {font-size:44px;font-weight:900;}
    .podium-step span {font-size:11px;letter-spacing:2px;opacity:.8;}
    @media(max-width:550px) {.rank-card{gap:10px;padding:15px 12px}.rank-name{font-size:17px}.rank-score{font-size:22px}.rank-avatar{font-size:24px}.podium-stage{gap:7px;padding:22px 6px 0}.podium-name{font-size:16px}.podium-avatar{font-size:34px}.podium-score{font-size:13px}.podium-step strong{font-size:36px}}
    </style>"""+content)


def start_question(connect, question, game):
    with connect() as c:
        if question>0:
            changed=c.execute("UPDATE trivia_state SET question=?, phase='open', deadline=? WHERE id=1 AND game=? AND question=? AND phase='reveal' AND deadline<=?",(question,time.time()+25,game,question-1,time.time())).rowcount
            return bool(changed)
        c.execute("UPDATE trivia_state SET game=?, question=?, phase='open', deadline=? WHERE id=1",(game,question,time.time()+25))
        return True


def vote(connect,name,expected,answer,now=None):
    with connect() as c:
        c.execute('BEGIN IMMEDIATE')
        now=time.time() if now is None else now
        s=dict(c.execute('SELECT * FROM trivia_state WHERE id=1').fetchone())
        if s['game']!=expected['game'] or s['question']!=expected['question'] or s['phase']!='open' or now>=s['deadline']:
            return False
        correct=answer==TRIVIA[s['question']][2]
        previous=c.execute('SELECT question,points FROM trivia_votes WHERE game=? AND name=? ORDER BY question DESC',(s['game'],name)).fetchall()
        streak=0
        for r in previous:
            if r['question']!=s['question']-streak-1 or not r['points']: break
            streak+=1
        base=200 if s['question']==len(TRIVIA)-1 else 100
        points=(base+min(streak,3)*25) if correct else 0
        changed=c.execute('INSERT OR IGNORE INTO trivia_votes VALUES(?,?,?,?,?)',(s['game'],s['question'],name,answer,points)).rowcount
        return bool(changed)


def winner_confetti(game):
    key=f'confetti_started_{game}'
    if key not in st.session_state:
        st.session_state[key]=time.time()
    if time.time()-st.session_state[key]>4.5:
        return
    colors=['#ff9dca','#90d9d0','#e8ce82','#bbb1ec']
    pieces=''.join(
        f'<i style="left:{(i*37)%100}%;background:{colors[i%4]};animation-delay:{(i%7)*.08}s;--drift:{(i%9-4)*24}px;--spin:{360+i*23}deg"></i>'
        for i in range(48)
    )
    st.html("""<style>
    .winner-confetti {position:fixed;inset:0;z-index:9999;pointer-events:none;overflow:hidden;}
    .winner-confetti i {position:absolute;top:-20px;width:9px;height:14px;border-radius:2px;
      opacity:0;animation:winner-fall 3.6s ease-in forwards;}
    @keyframes winner-fall {0% {opacity:1;transform:translate(0,-20px) rotate(0deg);}
      85% {opacity:1;}100% {opacity:0;transform:translate(var(--drift),105vh) rotate(var(--spin));}}
    @media (prefers-reduced-motion:reduce) {.winner-confetti {display:none;}}
    </style><div class="winner-confetti" aria-hidden="true">"""+pieces+'</div>')


def trivia_audio():
    # This iframe stays mounted while the one-second question fragment updates.
    # Audio starts only after a host click; players never mount this component.
    components.html("""
    <style>body{margin:0;background:#211b30;color:#f5f3f7;font:14px system-ui}
    button{background:#49324c;color:#fff;border:1px solid #ff9dca;border-radius:9px;padding:10px 16px;cursor:pointer}
    #music{margin-top:12px}p{color:#d1c5e5;margin:8px 0}</style>
    <button id="sound">Enable game audio</button> <button id="test">Test sound</button>
    <p>One click enables music and answer pops. Music plays while waiting and during questions.</p>
    <p id="audio-status" role="status">Audio is off.</p>
    <div id="music"><iframe id="music-player" width="100%" height="170" title="Trivia music from YouTube"
      src="https://www.youtube.com/embed/DjtvI2s8E0M?playsinline=1&enablejsapi=1"
      allow="autoplay; encrypted-media; picture-in-picture" referrerpolicy="strict-origin-when-cross-origin" allowfullscreen></iframe></div>
    <script>
    let audio,enabled=false,lastKey=null,lastCount=0;
    let player,ready=false,started=false,musicMode='idle',observed=null,applied=null;
    window.onYouTubeIframeAPIReady=()=>{
      player=new YT.Player('music-player',{
        events:{onReady:()=>{ready=true;},onError:()=>{document.getElementById('audio-status').textContent='YouTube music could not load. Test sound checks answer pops.';},onStateChange:e=>{
          if(e.data===YT.PlayerState.PLAYING&&!started){started=true;applied=null;}
        }}
      });
    };
    const api=document.createElement('script');api.src='https://www.youtube.com/iframe_api';document.head.appendChild(api);
    function syncMusic(key,phase){
      observed={key,phase};
      if(!ready||!started)return;
      const signature=key+':'+phase;
      if(signature!==applied){
        applied=signature;
        if(phase==='open'||phase==='waiting'){
          musicMode='question';player.seekTo(0,true);player.playVideo();
        }else if(phase==='reveal'||phase==='finished'){
          musicMode='ending';player.seekTo(20,true);player.playVideo();
        }else{musicMode='idle';player.pauseVideo();}
      }
      const t=player.getCurrentTime();
      if(musicMode==='question'&&t>=19.9)player.seekTo(0,true);
      if(musicMode==='ending'&&t>=22){player.pauseVideo();musicMode='done';}
    }

    const toggle=document.getElementById('sound');
    toggle.onclick=()=>{
      audio=audio||new (window.AudioContext||window.webkitAudioContext)();
      audio.resume();enabled=!enabled;started=enabled;applied=null;
      toggle.textContent=enabled?'Game audio on · mute':'Enable game audio';
      document.getElementById('audio-status').textContent=enabled?'Music and answer pops are on.':'Audio is off.';
      if(enabled){
        if(ready){player.unMute();player.setVolume(65);player.playVideo();}
        audio.resume().then(()=>pop(0));
      }else if(ready){player.pauseVideo();}
    };
    document.getElementById('test').onclick=()=>{
      audio=audio||new (window.AudioContext||window.webkitAudioContext)();
      audio.resume().then(()=>{pop(0);pop(.18);});
      document.getElementById('audio-status').textContent='Playing two test pops. If silent, check your speaker volume and whether this tab is muted.';
    };
    function pop(delay){
      const t=audio.currentTime+delay,o=audio.createOscillator(),g=audio.createGain();
      o.type='sine';o.frequency.setValueAtTime(800,t);o.frequency.exponentialRampToValueAtTime(230,t+.09);
      g.gain.setValueAtTime(.0001,t);g.gain.exponentialRampToValueAtTime(.22,t+.006);
      g.gain.exponentialRampToValueAtTime(.0001,t+.11);o.connect(g);g.connect(audio.destination);
      o.start(t);o.stop(t+.12);
    }
    // Read the counter rendered by Streamlit; never request or change game data.
    setInterval(()=>{
      let marker;try{marker=parent.document.querySelector('[data-trivia-counter]')}catch(e){return}
      if(!marker)return;
      const key=marker.dataset.round,count=Number(marker.dataset.count),phase=marker.dataset.phase;
      syncMusic(key,phase);
      if(key===lastKey&&count>lastCount&&phase==='open'&&enabled&&audio?.state==='running'){
        for(let i=0;i<count-lastCount;i++)pop(i*.09);
      }
      lastKey=key;lastCount=count;toggle.title=count+' answers received';
    },150);
    </script>
    """,height=345)


def trivia_ui(host,name,connect,rows,execute):
    s=state(rows)
    if host:
        with st.expander('Music & answer sounds',expanded=False):
            trivia_audio()
    if s['phase']=='waiting':
        st.subheader('Pet Trivia')
        st.write('10 questions. Four choices. One winner.')
        st.caption('25 seconds to answer · correct answers + streak bonuses · double base points in the final round')
        if host and st.button('Start trivia',type='primary'):
            start_question(connect,0,s['game']+1); st.rerun()
        elif not host:st.info('Waiting for the host to start.')
    @st.fragment(run_every='1s')
    def live():
        s=state(rows)
        count=rows('SELECT COUNT(*) AS n FROM trivia_votes WHERE game=? AND question=?',(s['game'],s['question']))[0]['n']
        st.html(f'<span data-trivia-counter data-round="{s["game"]}_{s["question"]}" data-count="{count}" data-phase="{s["phase"]}" style="display:none"></span>')
        remaining=max(0,math.ceil(s['deadline']-time.time()))
        if s['phase']=='open' and remaining==0:
            execute("UPDATE trivia_state SET phase='reveal', deadline=? WHERE id=1 AND game=? AND question=? AND phase='open'",(time.time()+10,s['game'],s['question']))
            st.rerun()
        if s['phase']=='waiting':
            return
        if s['phase']=='finished':
            st.subheader('Final podium')
            winners=rows('SELECT name,SUM(points) AS score FROM trivia_votes WHERE game=? GROUP BY name ORDER BY score DESC',(s['game'],))
            if winners:
                best=winners[0]['score']; tied=[w['name'] for w in winners if w['score']==best]
                st.success('Winner'+('s' if len(tied)>1 else '')+': '+', '.join(tied)+f' · {best} points')
                if host or name.casefold() in {n.casefold() for n in tied}:
                    winner_confetti(s['game'])
            board(rows,s['game'],podium=True)
            if host and st.button('Play again'):
                start_question(connect,0,s['game']+1);st.rerun()
            return
        idx=s['question']; question,options,correct,explanation=TRIVIA[idx]
        with st.container(key='trivia_question'):
            st.caption(f'QUESTION {idx+1} / {len(TRIVIA)}'+(' · DOUBLE POINTS' if idx==len(TRIVIA)-1 else ''))
            st.subheader(question)
            if s['phase']=='open':st.metric('Time remaining',f'{remaining}s')
        total=rows('SELECT COUNT(*) AS n FROM players')[0]['n']
        st.html(f'<div style="text-align:center;font-size:20px;font-weight:700;color:#f5f3f7;margin:8px 0 22px" aria-live="polite">{count} / {total} answered</div>')
        votes=rows('SELECT answer,points FROM trivia_votes WHERE game=? AND question=? AND name=?',(s['game'],idx,name)) if not host else []
        if s['phase']=='open':
            tiles=st.columns(2,gap='medium')
            for i,option in enumerate(options):
                with tiles[i%2]:
                    if st.button(f'{ICONS[i]} {chr(65+i)} · {option}',key=f'answer_{["paw","bone","fish","feather"][i]}_{s["game"]}_{idx}',disabled=host or bool(votes),use_container_width=True):
                        if not vote(connect,name,s,i):st.warning('This round closed or your answer is already locked.')
                        st.rerun()
            if votes:st.success('Answer locked in')
            if host and st.button('Skip timer'):
                execute("UPDATE trivia_state SET phase='reveal', deadline=? WHERE id=1 AND game=? AND question=? AND phase='open'",(time.time()+10,s['game'],idx));st.rerun()
        elif s['phase']=='reveal':
            st.success(f'{ICONS[correct]} {options[correct]}')
            st.write(explanation)
            if votes:st.markdown(f'**+{votes[0]["points"]} points**')
            elif not host:st.caption('No answer this round · 0 points')
            st.caption(f'Next round available in {remaining}s' if remaining else 'Ready for the next round')
            if host:
                if remaining>0 and st.button('Skip explanation timer'):
                    execute("UPDATE trivia_state SET deadline=0 WHERE id=1 AND game=? AND question=? AND phase='reveal'",(s['game'],idx));st.rerun()
                if idx<len(TRIVIA)-1:
                    if st.button('Next question',type='primary',disabled=remaining>0):
                        start_question(connect,idx+1,s['game']);st.rerun()
                elif st.button('Show final podium',type='primary',disabled=remaining>0):
                    execute("UPDATE trivia_state SET phase='finished' WHERE id=1 AND phase='reveal' AND deadline<=?",(time.time(),));st.rerun()
            with st.expander('Leaderboard',expanded=True):
                board(rows,s['game'])
    live()

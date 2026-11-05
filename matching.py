"""Situation-based animal personality game; researched profiles supply breed traits."""
import base64
import hashlib
import json
from pathlib import Path
import streamlit as st

CATALOG_DATA=json.loads((Path(__file__).parent/'pet_catalog.json').read_text())
CATALOG=CATALOG_DATA['profiles']
BY_ID={p['id']:p for p in CATALOG}
VERSION=4
QUESTIONS=[
('Your Saturday has no plans. What happens next?', ['I am going out. Someone grab a leash.','Sofa, snacks, and company that respects the sofa.','I could lose hours setting up a tiny habitat.','Nothing. That is the entire plan.']),
('Someone wants your attention for the fifth time in ten minutes.', ['Fine. Let’s teach you something.','Come sit with me, but we are staying here.','We can hang out for a bit this evening.','Absolutely not. Please entertain yourself.']),
('Be honest about cleaning.', ['I can vacuum fur. I already own the vacuum.','Bedding, little tunnels, spot cleaning? Fine.','I would rather maintain a tank than clean a litter box.','Nah. I do not want another chore.']),
('Your new roommate has opinions. Loud ones.', ['Good. I will talk back.','A little noise is fine.','I prefer the quiet, slightly mysterious type.','Absolutely not. I have enough meetings.']),
('How do you actually want to interact?', ['Affection. Sit with me. Follow me around.','Gentle handling and little play sessions.','Mostly watch them do weird little things.','From a respectful distance. Very respectful.']),
('Dinner time. What are you willing to deal with?', ['Prepared food and fresh foods. Keep it familiar.','Live insects do not bother me.','I can handle feeding prepared whole prey.','A small amount of fish food is more my speed.']),
('What would you happily make room for?', ['A companion sharing my living space.','A proper enclosure with room to explore.','A tank or terrarium I can make look good.','I have land, secure fencing, and suitable shelter.']),
('It is cold outside. Your pet still needs exercise.', ['Coat on. We are going.','Can we play inside instead?','I prefer something with its own indoor setup.','No. I am not doing that.']),
('What is your position on grooming?', ['I can handle brushing and grooming appointments.','A regular brush is fine. Nothing elaborate.','I would rather manage a habitat than a coat.','I am not booking hair appointments for another person.']),
('When do you actually have energy for a pet?', ['Daytime adventures and regular activity.','Evenings. I become a person after work.','I enjoy checking on a habitat throughout the day.','Very limited. Work has already used me up.']),
('A pet needs you to repeat the same thing. Again.', ['That is how learning works. I am patient.','I can handle it, with some boundaries.','I would prefer a more independent arrangement.','Nope. My patience was gone three repetitions ago.']),
('Which arrangement sounds best?', ['An enthusiastic companion who joins in.','A housemate. We like each other, but have separate plans.','Something unusual I can observe and care for.','I admire you. You swim over there.']),
]
# Each choice contributes category affinity and/or a preference dimension.
# These are game-design rules, not scientific suitability probabilities.
RULES=[
[({'Dog':4},{'activity':2}),({'Cat':4},{'activity':0}),({'Reptile':3,'Amphibian':3,'Invertebrate':3,'Fish':2},{}),({'Fish':4},{'activity':0})],
[({'Dog':3,'Small mammal':2,'Bird':2},{'training':2}),({'Cat':3,'Dog':2},{'affection':2}),({'Small mammal':3},{'affection':1}),({'Fish':3,'Reptile':2,'Invertebrate':2},{'affection':0})],
[({'Dog':2,'Cat':2},{'shedding':2}),({'Small mammal':5},{}),({'Fish':5,'Amphibian':3},{}),({'Fish':4},{'grooming':0})],
[({'Bird':6},{'noise':2}),({'Dog':2,'Small mammal':1},{'noise':1}),({'Reptile':4,'Invertebrate':3},{'noise':0}),({'Fish':4},{'noise':0})],
[({'Dog':3,'Cat':3},{'affection':2}),({'Small mammal':5},{'handling':1}),({'Reptile':3,'Invertebrate':3,'Amphibian':3,'Fish':2},{'handling':0}),({'Fish':4,'Invertebrate':2},{'handling':0})],
[({'Dog':1,'Cat':1,'Small mammal':1,'Bird':1},{}),({'Reptile':4,'Invertebrate':4,'Amphibian':3},{}),({'Reptile':6},{}),({'Fish':5},{})],
[({'Dog':2,'Cat':2},{}),({'Small mammal':4,'Bird':3},{}),({'Fish':3,'Reptile':3,'Amphibian':3,'Invertebrate':3},{}),({'Outdoor animal':12},{})],
[({'Dog':6},{'activity':2}),({'Cat':3,'Small mammal':2},{'activity':1}),({'Reptile':3,'Fish':2,'Amphibian':2,'Invertebrate':2},{}),({'Fish':4},{'activity':0})],
[({'Dog':3,'Cat':1},{'grooming':2}),({'Cat':3,'Dog':1},{'grooming':1}),({'Reptile':3,'Fish':2,'Amphibian':2,'Invertebrate':2},{'grooming':0}),({'Fish':3},{'grooming':0})],
[({'Dog':4,'Bird':2},{'activity':2}),({'Small mammal':5,'Cat':1},{}),({'Reptile':3,'Fish':3,'Amphibian':3,'Invertebrate':3},{}),({'Fish':4},{'activity':0})],
[({'Dog':4,'Bird':2,'Small mammal':1},{'training':2}),({'Cat':4},{'affection':1}),({'Reptile':4,'Small mammal':2,'Invertebrate':3},{'affection':0}),({'Fish':6},{'affection':0})],
[({'Dog':5,'Bird':2},{'social':2}),({'Cat':6},{'affection':1}),({'Reptile':4,'Amphibian':4,'Invertebrate':4},{}),({'Fish':7},{})],
]
LOW_EFFORT=((0,3),(1,3),(2,3),(4,3),(7,3),(8,3),(9,3),(10,3))

def rank_matches(a):
    if len(a)!=len(QUESTIONS) or any(not isinstance(v,int) or not 0<=v<4 for v in a):raise ValueError('Invalid quiz answers')
    affinity={};preferences={}
    for i,choice in enumerate(a):
        categories,traits=RULES[i][choice]
        for category,n in categories.items():affinity[category]=affinity.get(category,0)+n
        for trait,v in traits.items():preferences.setdefault(trait,[]).append(v)
    preferences={k:sum(v)/len(v) for k,v in preferences.items()}
    low=sum(a[i]==option for i,option in LOW_EFFORT)
    fish_mode=low>=3 or (a[10]==3 and low>=2)
    pool=[p for p in CATALOG if not p['outdoor'] or a[6]==3]
    if fish_mode:pool=[p for p in pool if p['category']=='Fish']
    ranked=[]
    for p in pool:
        distances=[(p['traits'][trait]-v)**2 for trait,v in preferences.items() if trait in p['traits']]
        distance=sum(distances)/len(distances) if distances else 1
        score=affinity.get(p['category'],0)-3*distance
        # Snake and hamster clues affect species selection, without asking people
        # to pick the animal they want as their answer.
        if p['name'] in ('Corn snake','Royal python (ball python)') and a[5]==2:score+=8
        if p['name']=='Syrian hamster' and a[9]==1 and a[1] in (2,3):score+=4
        tie=hashlib.sha256((json.dumps(a)+p['id']).encode()).hexdigest()
        ranked.append((-score,tie,p))
    return [p for _,_,p in sorted(ranked,key=lambda r:(r[0],r[1]))]

def result_image(p):
    filename={'Dog':'dog.png','Cat':'cat.png','Bird':'bird.png','Fish':'fish.gif'}.get(p['category'])
    if p['name']=='Domestic rabbit':filename='rabbit.png'
    if filename:
        path=Path(__file__).parent/'assets/results'/filename
        if not path.exists():path=Path(__file__).parent/filename
        if path.suffix=='.gif':st.image('data:image/gif;base64,'+base64.b64encode(path.read_bytes()).decode(),width=320)
        else:st.image(str(path),width=320)
    else:
        icon={'Small mammal':'🐹','Reptile':'🦎','Amphibian':'🦎','Invertebrate':'🕷️','Outdoor animal':'🐐'}.get(p['category'],'🐾')
        if 'snake' in p['name'].lower() or 'python' in p['name'].lower():icon='🐍'
        elif 'horse' in p['name'].lower():icon='🐴'
        elif 'hen' in p['name'].lower():icon='🐔'
        st.markdown(f'<div style="font-size:100px;line-height:1.2">{icon}</div>',unsafe_allow_html=True)

def result_line(p):
    if p['category']=='Cat':return 'A roommate. You will be covering the rent.'
    if p['category']=='Dog':return 'You wanted company. Privacy may be harder to arrange.'
    if p['category']=='Bird':return 'You are getting company and unsolicited commentary.'
    if p['name']=='Syrian hamster':return 'Your schedules finally align: unavailable until evening.'
    if p['name']=='Domestic rabbit':return 'Looks innocent. Keep an eye on your charging cables.'
    if p['category']=='Reptile':return 'Quiet company. No small talk.'
    return ''

def show_result(p):
    if p['category']=='Fish':st.subheader('Your best bet is to get a fish.')
    else:st.subheader('Your match: '+p['category']+' · '+p['name'])
    result_image(p)
    if p['category']!='Fish':
        line=result_line(p)
        if line:st.write(line)
    if st.button('Retake quiz'):
        return True
    return False

def match_ui(name,rows,execute):
    saved=rows('SELECT answers FROM matches WHERE name=?',(name,))
    data=None
    if saved:
        try:
            value=json.loads(saved[0]['answers'])
            if isinstance(value,dict) and value.get('version')==VERSION and value.get('id') in BY_ID:data=value
        except (ValueError,TypeError):pass
    if data:
        if show_result(BY_ID[data['id']]):
            execute('DELETE FROM matches WHERE name=?',(name,))
            for i in range(len(QUESTIONS)):
                st.session_state.pop(f'pet_v4_{i}',None)
            st.rerun()
        return
    st.subheader('Find your animal match')
    st.caption('12 situations. Pick the answer you would actually give.')
    with st.form('animal_quiz_v4'):
        responses=[]
        for i,(q,opts) in enumerate(QUESTIONS):
            if i:
                st.markdown('<div style="height:24px" aria-hidden="true"></div>',unsafe_allow_html=True)
            responses.append(st.radio(f'**{i+1}. {q}**',opts,index=None,key=f'pet_v4_{i}'))
        go=st.form_submit_button('Show my match',type='primary')
    if go:
        if any(v is None for v in responses):st.error('Answer all 12 questions to get your match.')
        else:
            answers=[QUESTIONS[i][1].index(v) for i,v in enumerate(responses)]
            p=rank_matches(answers)[0]
            payload={'version':VERSION,'answers':answers,'id':p['id']}
            execute('INSERT OR REPLACE INTO matches VALUES(?,?,?)',(name,p['category']+' · '+p['name'],json.dumps(payload)))
            st.rerun()


def host_quiz_answers(rows):
    @st.fragment(run_every='3s')
    def review():
        players=rows('SELECT name FROM players ORDER BY joined')
        records=rows('SELECT name,result,answers FROM matches ORDER BY name COLLATE NOCASE')
        complete={}
        for r in records:
            try:
                payload=json.loads(r['answers'])
                a=payload.get('answers',[]) if isinstance(payload,dict) else []
                if not isinstance(payload,dict) or payload.get('version')!=VERSION or len(a)!=len(QUESTIONS):continue
                if any(not isinstance(v,int) or not 0<=v<len(QUESTIONS[i][1]) for i,v in enumerate(a)):continue
                complete[r['name'].casefold()]={**r,'decoded':a}
            except (ValueError,TypeError):continue
        submitted=[p for p in players if p['name'].casefold() in complete]
        pending=[p['name'] for p in players if p['name'].casefold() not in complete]
        st.subheader('Quiz answers')
        st.write(f'**{len(submitted)} of {len(players)} players finished**')
        if pending:st.caption('Waiting for: '+', '.join(pending))
        elif players:st.success('Everyone has finished. Review their answers below.')
        if not submitted:
            st.caption('Completed quizzes will appear here automatically.')
            return
        names=[p['name'] for p in submitted]
        selected=st.selectbox('View a player’s answers',names,key='host_quiz_player')
        r=complete[selected.casefold()]
        st.markdown(f'**{selected} · {r["result"]}**')
        st.dataframe([{'Question':f'{i+1}. {q}','Answer':opts[r['decoded'][i]]} for i,(q,opts) in enumerate(QUESTIONS)],hide_index=True,use_container_width=True)
    review()

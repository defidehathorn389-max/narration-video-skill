"""Validate animation data, not subjective motion quality or spoken pronunciation.
Usage: --storyboard file.json --layout file.json --expected-images 48 --min-state-scenes 3
Exits nonzero for broken time anchors, repeated popup spam or missing state plans.
"""
import argparse,json,re
from pathlib import Path
from collections import Counter

def validate(d,l,expected=None,min_states=1):
 checks=[]
 def check(name,ok,evidence):checks.append({'check':name,'status':'PASS' if ok else 'FAIL','evidence':evidence})
 shots=d['shots'];caps=d['captions'];evs=[e for e in l.get('events',[]) if not e.get('skip')]
 check('base_art_count',expected is None or len({s['image'] for s in shots})==expected,len({s['image'] for s in shots}))
 check('real_character_anchors',all('chars' in c and ''.join(x['char'] for x in c['chars'])==c['text'] for c in caps),'Presence and text consistency only; does not prove ASR accuracy')
 wrong=[]
 for e in evs:
  s=shots[e['shot']];matches=[]
  for c in caps:
   for m in re.finditer(re.escape(e['word']),c['text']):
    if not c.get('chars'):continue
    t=c['chars'][m.start()]['start']
    if s['start']-.05<=t<s['end'] and abs(t-e['t0'])<=.51:matches.append(t)
  if not matches:wrong.append({'word':e['word'],'time':e['t0'],'shot':e['shot']})
 check('word_anchor_belongs_to_shot',not wrong,wrong)
 counts=Counter(e['word'] for e in evs);last={};spacing=True
 for e in sorted(evs,key=lambda x:x['t0']):
  if e['word'] in last and e['t0']-last[e['word']]<15-1e-5:spacing=False
  last[e['word']]=e['t1']
 check('word_frequency_and_spacing',bool(evs) and max(counts.values(),default=0)<=2 and spacing,dict(counts))
 zones=Counter(e.get('zone','MISSING') for e in evs)
 check('distributed_whitespace_positions','MISSING' not in zones and len(zones)>=(7 if len(evs)>=21 else min(3,len(evs))),dict(zones))
 check('big_words_outside_caption_band',all(e['y']+e['th']+40<900 for e in evs),'Geometry check, not visual overlap proof')
 state_groups={k:len(v) for k,v in d.get('states',{}).items() if len(v)>=2}
 check('planned_state_sequences',len(state_groups)>=min_states,state_groups)
 return {'checks':checks,'pass':all(x['status']=='PASS' for x in checks),'limitations':['Does not inspect video pixels','Does not validate state biology','Does not certify pronunciation or human aesthetic approval']}

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--storyboard',required=True);p.add_argument('--layout',required=True);p.add_argument('--expected-images',type=int);p.add_argument('--min-state-scenes',type=int,default=1);p.add_argument('--report');a=p.parse_args()
 r=validate(json.loads(Path(a.storyboard).read_text()),json.loads(Path(a.layout).read_text()),a.expected_images,a.min_state_scenes);text=json.dumps(r,ensure_ascii=False,indent=2)
 if a.report:Path(a.report).write_text(text)
 print(text);raise SystemExit(0 if r['pass'] else 1)

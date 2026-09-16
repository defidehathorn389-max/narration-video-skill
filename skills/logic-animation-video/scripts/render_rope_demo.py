import os, math, wave, subprocess, sys
from pathlib import Path
import numpy as np, cv2
from PIL import Image, ImageDraw, ImageFont
import imageio_ffmpeg
ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT / 'examples' / 'rope-45')
(ROOT / 'deliverables').mkdir(exist_ok=True)
FF=imageio_ffmpeg.get_ffmpeg_exe()
DRAFT = '--draft' in sys.argv
S = .75 if DRAFT else 1.5
W,H,FPS = (960,540,15) if DRAFT else (1920,1080,30)
BG='#bdbdbd';INK='#252525';GRAY='#787878';GOLD='#f7ca54';RED='#a94849';WHITE='#f8f8f5'
FONTP=os.environ.get('CHINESE_FONT', '/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc')
BOLDP=os.environ.get('CHINESE_FONT_BOLD', '/usr/share/fonts/opentype/noto/NotoSansCJK-Bold.ttc')
for font_path in [FONTP, BOLDP]:
 if not Path(font_path).is_file():
  raise FileNotFoundError('Set CHINESE_FONT and CHINESE_FONT_BOLD to installed Chinese font paths: '+font_path)
fonts={}
def ft(s,b=False):
 k=(s,b)
 if k not in fonts:fonts[k]=ImageFont.truetype(BOLDP if b else FONTP,round(s*S))
 return fonts[k]
def scale_xy(xy):
 if isinstance(xy[0],(tuple,list,np.ndarray)):return [(round(x*S),round(y*S)) for x,y in xy]
 return tuple(round(v*S) for v in xy)
class Draw:
 def __init__(self,im):self.d=ImageDraw.Draw(im)
 def line(self,xy,fill=INK,width=2):self.d.line(scale_xy(xy),fill=fill,width=max(1,round(width*S)),joint='curve')
 def ellipse(self,xy,fill=None,outline=None,width=2):self.d.ellipse(scale_xy(xy),fill=fill,outline=outline,width=max(1,round(width*S)))
 def rectangle(self,xy,fill=None,outline=None,width=2):self.d.rectangle(scale_xy(xy),fill=fill,outline=outline,width=max(1,round(width*S)))
 def round(self,xy,r=10,fill=WHITE,outline=None,width=2):self.d.rounded_rectangle(scale_xy(xy),radius=round(r*S),fill=fill,outline=outline,width=max(1,round(width*S)))
 def polygon(self,xy,fill,outline=None):self.d.polygon(scale_xy(xy),fill=fill,outline=outline,width=round(2*S))
 def arc(self,xy,a,b,fill=INK,width=2):self.d.arc(scale_xy(xy),a,b,fill=fill,width=round(width*S))
 def text(self,x,y,s,size=28,fill=INK,b=False,anchor='mm',stroke=0):self.d.text((round(x*S),round(y*S)),s,font=ft(size,b),fill=fill,anchor=anchor,stroke_width=round(stroke*S),stroke_fill='#646464')
def ease(x):x=max(0,min(1,x));return x*x*(3-2*x)
def mix(a,b,x):return a+(b-a)*ease(x)
def clamp(x):return max(0,min(1,x))
def extract(path):
 im=Image.open(path).convert('RGB');a=np.array(im);mask=np.uint8(a.min(axis=2)<211)*255
 cs,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE);mask[:]=0;cv2.drawContours(mask,[max(cs,key=cv2.contourArea)],-1,255,-1)
 im=im.convert('RGBA');im.putalpha(Image.fromarray(mask));return im.crop(im.getbbox())
characters={'think':extract('thinker.png'),'explain':extract('character.png')};sprites={}
def person(im,x,bottom,h,t,kind='think',flip=False):
 key=(kind,h,flip)
 if key not in sprites:
  sp=characters[kind].copy();sp=sp.resize((round(h*S*sp.width/sp.height),round(h*S)),Image.Resampling.LANCZOS)
  if flip:sp=sp.transpose(Image.Transpose.FLIP_LEFT_RIGHT)
  sprites[key]=sp
 sp=sprites[key];dy=math.sin(t*2.4)*1.2
 # Subtle breathing and a slow lean animate the generated character layer.
 angle=math.sin(t*1.1)*.45
 layer=sp.rotate(angle,resample=Image.Resampling.BICUBIC,expand=False)
 im.paste(layer,(round(x*S-layer.width/2),round((bottom-h+dy)*S)),layer)
def arrow(d,x1,y1,x2,y2,color=INK,width=2):
 d.line([(x1,y1),(x2,y2)],color,width);ang=math.atan2(y2-y1,x2-x1)
 d.polygon([(x2,y2),(x2-10*math.cos(ang-.42),y2-10*math.sin(ang-.42)),(x2-10*math.cos(ang+.42),y2-10*math.sin(ang+.42))],color)
def cross(d,x,y,r=15):d.line([(x-r,y-r),(x+r,y+r)],RED,6);d.line([(x-r,y+r),(x+r,y-r)],RED,6)
def check(d,x,y):d.line([(x-10,y),(x-2,y+8),(x+14,y-11)],'#46634e',4)
def heading(d,a,b=''):
 d.text(640,77,a,35,b=True)
 if b:d.text(640,128,b,21,GRAY)
def bubble(d,x,y,txt):
 tw=len(txt)*21+30;d.round((x-tw/2,y-23,x+tw/2,y+23),20,WHITE,INK)
 d.polygon([(x-8,y+22),(x+4,y+35),(x+10,y+21)],WHITE)
 d.text(x,y,txt,21,b=True)
def clock(d,x,y,minutes=0,r=49,caption='已用时间',question=False):
 d.ellipse((x-r,y-r,x+r,y+r),WHITE,INK,2)
 for k in range(12):
  a=k*math.tau/12;d.line([(x+math.sin(a)*(r-7),y-math.cos(a)*(r-7)),(x+math.sin(a)*(r-3),y-math.cos(a)*(r-3))],GRAY,1)
 a=minutes/60*math.tau;d.line([(x,y),(x+math.sin(a)*(r-13),y-math.cos(a)*(r-13))],INK,3);d.ellipse((x-3,y-3,x+3,y+3),GOLD,INK,1)
 d.round((x-45,y+r+10,x+45,y+r+40),7,WHITE)
 d.text(x,y+r+25,'?' if question else f'{minutes:.0f} 分钟',20,b=True)
 d.text(x,y-r-21,caption,17)
def flame(d,x,y,t,sz=1):
 flick=math.sin(t*21+x*.2);h=(31+5*flick)*sz;w=(12+2*math.sin(t*17))*sz
 pts=[(x,y+3),(x-w,y-3),(x-w*.8,y-h*.45),(x-w*.2,y-h*.2),(x+4*sz,y-h),(x+w*.2,y-h*.48),(x+w,y-h*.27),(x+w*.7,y-2)]
 d.polygon(pts,'#f0b43d','#9c7029');d.polygon([(x,y),(x-5*sz,y-6*sz),(x+2*sz,y-h*.59),(x+5*sz,y-5*sz)],'#ffeaa0')
 for k in range(3):
  p=(t*1.2+k*.32)%1;xx=x+math.sin(k*5+t*2)*9*p;yy=y-h-24*p;r=1.5*(1-p)+.6
  d.ellipse((xx-r,yy-r,xx+r,yy+r),'#b29763')
def lighter(d,x,y,t,on=True,angle=0):
 d.round((x-12,y-5,x+12,y+34),4,'#eeeeeb',INK,2);d.rectangle((x-12,y-12,x+12,y-1),'#6f6f6f',INK)
 d.ellipse((x-12,y-18,x-1,y-8),'#b2b2b2',INK,1)
 if on:flame(d,x+5,y-14,t,.8)
MODELS=[([0,.25,.5,.75,1],[0,6,15,45,60]),([0,.2,.4,.65,.85,1],[0,18,22,50,54,60])]
def front(minutes,model=0):
 xs,ts=MODELS[model];return float(np.interp(minutes,ts,xs))
def rope_path(x0,x1,y,n=100):
 return [(x0+(x1-x0)*i/(n-1),y+5*math.sin(i/(n-1)*math.tau)+2*math.sin(i/(n-1)*math.tau*3)) for i in range(n)]
def draw_fiber(d,points,color=GOLD,width=10,twist=True):
 d.line(points,INK,width+3);d.line(points,color,width)
 if twist:
  for i in range(2,len(points)-2,3):
   x,y=points[i];d.line([(x-2,y-width*.4),(x+2,y+width*.4)],'#a18749',1)
def rope(d,y,left=0,right=0,model=0,t=0,fireL=False,fireR=False,x0=355,x1=1030,label='',ghost=True):
 total=left+right;pl=front(min(60,left),model);pr=front(max(0,60-right),model)
 if ghost:
  for xx in np.arange(x0,x1,16):d.line([(xx,y+2),(xx+6,y+2)],'#9c9c9c',2)
 if label:d.text(x0-46,y,label,25,b=True)
 if total>=59.98:
  for j in range(11):
   xx=x0+(x1-x0)*j/10;d.ellipse((xx-2,y-2,xx+2,y+1),'#8d8d8d')
  d.text((x0+x1)/2,y-24,'烧尽',21,GRAY)
  return
 xl=x0+(x1-x0)*pl;xr=x0+(x1-x0)*pr
 pts=[]
 for p in np.linspace(pl,pr,max(8,int((pr-pl)*110))):pts.append((x0+(x1-x0)*p,y+5*math.sin(p*math.tau)+2*math.sin(p*math.tau*3)))
 draw_fiber(d,pts)
 if fireL:flame(d,*pts[0],t)
 if fireR:flame(d,*pts[-1],t+1)
 return xl,xr

def timeline(d,minute,y=563):
 x0,x1=355,1030;d.line([(x0,y),(x1,y)],'#898989',3)
 for m,label in [(0,'开始'),(30,'30 分钟'),(45,'45 分钟')]:
  x=x0+(x1-x0)*m/45;d.line([(x,y-7),(x,y+7)],INK,2);d.text(x,y+29,label,20)
 xx=x0+(x1-x0)*min(45,minute)/45
 d.line([(x0,y),(xx,y)],'#c09a35',6);d.ellipse((xx-6,y-6,xx+6,y+6),GOLD,INK,1)
 if 0<minute<45:d.text(xx,y-26,f'{minute:.0f} 分钟',21,b=True)
def table(d):
 d.polygon([(332,276),(1024,276),(1063,480),(293,480)],WHITE,INK)
 d.rectangle((293,480,1063,490),'#e9e9e6',INK)
 for x in [309,1037]:d.polygon([(x,490),(x+9,490),(x+6,549),(x-2,549)],'#eeeeeb',INK)

# The 8 narration sections are paced to roughly two minutes, with a short thinking pause.
RATE=1.18;SR=24000
script=[
 ['给你两根绳子，和一个打火机','每根绳子，从一头点燃','都需要六十分钟才能烧完','没有钟表，也不能数秒','你能不能只靠这两根绳子','准确计时四十五分钟？'],
 ['先别急着把绳子分成四段','最坑的条件来了：它们燃烧得并不均匀','有的地方烧得快，有的地方烧得慢','看起来同样长的两段','燃烧时间，可能完全不同'],
 ['所以，烧掉四分之三的长度','不一定是四十五分钟','把绳子对折，找个中点，也没有用','长度不能当时间用','题目唯一保证的是','每根绳子完整烧完，总共六十分钟'],
 ['不过，题目允许你同时点燃两头','也允许在一根烧完的瞬间，去点另一根','所有操作，都视为瞬间完成','线索就在这里','既然一头点燃要六十分钟','两头一起点，会发生什么？'],
 ['答案是三十分钟','注意，两团火不一定在绳子的正中间相遇','但不管哪里快，哪里慢','它们从两端同时烧','都会在三十分钟时烧完','现在，试着把这三十分钟用起来'],
 ['开始时，同时做两件事','第一根，两头都点燃','第二根，只点燃一头','等第一根完全烧尽','你就知道，三十分钟到了','这一刻，第二根也已经烧了三十分钟'],
 ['马上点燃第二根的另一头','它剩下的部分，如果只从一头继续烧','还需要三十分钟','现在两头一起烧，就只需要十五分钟','等第二根烧尽','总时间就是三十加十五','恰好四十五分钟'],
 ['这道题的关键，不是把长度平均分','而是把剩余的燃烧时间减半','再看一遍','第一根双头，第二根单头','第一根烧完，再点第二根另一头','两根绳子，四十五分钟','你最开始，也想过对折吗？']]
starts=[];dur=[];audios=[];pcm=[np.zeros(int(.4*SR),np.int16)];pos=.4
for i in range(8):
 subprocess.run([FF,'-y','-i',f'audio/{i+1:02}.wav','-af',f'atempo={RATE}','-ar',str(SR),f'audio/paced-{i}.wav'],capture_output=True,check=True)
 with wave.open(f'audio/paced-{i}.wav') as w:a=np.frombuffer(w.readframes(w.getnframes()),np.int16)
 starts.append(pos);dur.append(len(a)/SR);audios.append(a);pcm.append(a);pos+=len(a)/SR
 if i==3:pause=pos;pcm.append(np.zeros(int(2.5*SR),np.int16));pos+=2.5
TOTAL=pos+1.2;pcm.append(np.zeros(int(1.2*SR),np.int16));audio=np.concatenate(pcm).astype(np.float64)/32768
rng=np.random.default_rng(42)
def sound(at,kind='tick',volume=.045):
 n=int(SR*(.14 if kind=='tick' else .3));z=np.arange(n)/SR
 if kind=='tick':v=np.sin(2*math.pi*830*z)*np.exp(-z*55)
 else:v=rng.normal(0,1,n)*np.exp(-z*15)*.45+np.sin(2*math.pi*240*z)*np.exp(-z*30)*.25
 v*=volume;st=int(at*SR);nn=min(n,len(audio)-st)
 if nn>0:audio[st:st+nn]+=v[:nn]
for k in range(3):sound(pause+k*.8,'tick',.06)
for i in [0,1,4,5,6,7]:sound(starts[i]+dur[i]*.12,'fire')
for i in [5,6]:
 for j in range(1,int(dur[i])):sound(starts[i]+j,'tick',.018)
with wave.open('audio/narration-effects.wav','wb') as w:w.setnchannels(1);w.setsampwidth(2);w.setframerate(SR);w.writeframes((np.clip(audio,-1,1)*32767).astype(np.int16).tobytes())
# Snap estimated subtitle boundaries toward nearby low-energy speech pauses.
cues=[]
for i,ll in enumerate(script):
 a=audios[i].astype(float)/32768;frame=480;energy=np.array([np.sqrt(np.mean(a[k:k+frame]**2)) for k in range(0,len(a),frame)])
 weights=[len(s)+2 for s in ll];bounds=[0];p=0
 for j,v in enumerate(weights[:-1]):
  p+=dur[i]*v/sum(weights);lo=max(bounds[-1]+.6,p-.42);hi=min(dur[i]-.5,p+.42)
  cand=[k for k in range(int(lo/.02),min(len(energy),int(hi/.02))) if energy[k]<.013]
  if cand:pnew=min(cand,key=lambda k:abs(k*.02-p))*.02
  else:pnew=p
  bounds.append(pnew)
 bounds.append(dur[i])
 for j,s in enumerate(ll):cues.append((starts[i]+bounds[j],starts[i]+bounds[j+1],s))
def ts(t):
 x=round(t*1000);return f'{x//3600000:02}:{x//60000%60:02}:{x//1000%60:02},{x%1000:03}'
with open('两根绳子_字幕.srt','w') as f:
 for j,(a,b,s) in enumerate(cues):f.write(f'{j+1}\n{ts(a)} --> {ts(b)}\n{s}\n\n')

def render(t,cover=False):
 im=Image.new('RGB',(W,H),BG);d=Draw(im)
 thought=pause<=t<starts[4]
 idx=next((i for i in range(8) if starts[i]<=t<starts[i]+dur[i]),7 if t>=starts[7] else 0)
 if thought:idx=3
 u=clamp((t-starts[idx])/dur[idx])
 d.text(28,26,'脑洞试验室  /  02',14,'#eeeeee',anchor='lm')
 d.text(1250,26,'理想化逻辑题 · 请勿模仿点火',14,'#4e4e4e',anchor='rm')
 person(im,138,602,285,t,'think' if idx<4 else 'explain')
 if idx in [0,2,5,6,7]:person(im,1161,614,195,t,'explain',True)
 d=Draw(im)
 if idx==0:
  heading(d,'两根绳子，怎样计时 45 分钟？','每根烧完需要 60 分钟，但燃烧并不均匀')
  table(d)
  # The ropes slide into the scene before the problem conditions appear.
  dx=130*(1-ease(u/.11))
  rope(d,340,t=t,x0=365+dx,x1=980+dx,label='①',ghost=False)
  rope(d,423,t=t,x0=365+dx,x1=980+dx,label='②',ghost=False)
  if u>.18:
   clock(d,1122,285,60,43,'每根烧完')
   lighter(d,mix(1040,800,(u-.18)/.18),533,t,on=u>.26)
  if u>.48:
   for x,s in [(477,'没有钟表'),(695,'不能数秒')]:
    d.round((x-83,192,x+83,233),10,WHITE);d.text(x,213,s,21)
   if u>.62:bubble(d,169,274,'45 分钟？')
  d.text(674,586,'只有两根绳子 + 一个打火机',24,b=True)
 elif idx==1:
  heading(d,'陷阱：燃烧速度不均匀','同样长的两段，燃烧时间可能完全不同')
  # Local pieces are equal in length but burn in different amounts of time.
  elapsed=24*ease((u-.22)/.66)
  for j,(yy,need) in enumerate([(300,8),(451,24)]):
   p=clamp(elapsed/need);x0,x1=391,978
   d.text(321,yy,'这一段' if j==0 else '另一段',21)
   for xx in np.arange(x0,x1,16):d.line([(xx,yy+2),(xx+6,yy+2)],'#989898',2)
   if p<1:
    draw_fiber(d,rope_path(x0+(x1-x0)*p,x1,yy));flame(d,x0+(x1-x0)*p,yy,t+j)
   else:d.text(681,yy-22,'烧完',23,GRAY)
   arrow(d,x0,yy+35,x1,yy+35,GRAY);arrow(d,x1,yy+35,x0,yy+35,GRAY)
   d.text(685,yy+61,'同样长度',19,GRAY)
   clock(d,1111,yy,min(elapsed,need),40,'局部示例')
  if u>.38:bubble(d,145,260,'一样长 ≠ 一样久')
  d.text(691,570,'示例：一段 8 分钟，另一段 24 分钟',24,b=True)
 elif idx==2:
  heading(d,'错误方法：按长度分时间','长度比例，不能直接换成时间比例')
  if u<.49:
   for j in range(4):
    x0=360+j*162;draw_fiber(d,rope_path(x0,x0+146,304),GOLD if j<3 else '#d3d3c9')
    d.text(x0+73,348,'¼',25)
    if j<3:
     yy=mix(216,275,u/.24);d.line([(x0+155,yy),(x0+155,yy+56)],'#f0f0f0',3)
   d.text(680,416,'¾ 的长度 = 45 分钟？',33,b=True)
   if u>.17:cross(d,972,411,23)
   arrow(d,361,368,826,368,GRAY);d.text(680,512,'烧得快慢不同，这个换算不成立',25)
  else:
   p=ease((u-.49)/.21);pts=[]
   for q in np.linspace(0,1,110):
    sx=370+650*q;sy=337
    # Morph a straight rope into a folded hairpin.
    if q<.46:fx=390+q/.46*485;fy=289
    elif q>.54:fx=875-(q-.54)/.46*485;fy=369
    else:
     a=(q-.46)/.08*math.pi;fx=875+40*math.sin(a);fy=329-40*math.cos(a)
    pts.append((sx+(fx-sx)*p,sy+(fy-sy)*p))
   draw_fiber(d,pts)
   d.text(655,450,'对折找中点，也不行',32,b=True);cross(d,942,447,21)
   d.text(667,521,'唯一保证：整根烧完 = 60 分钟',25)
 elif idx==3:
  heading(d,'换个思路：两头一起点呢？','题设允许同时点火，操作耗时忽略不计')
  rope(d,308,t=t,fireL=True,fireR=u>.2,label='①')
  rope(d,463,t=t,label='②')
  if not thought:
   phase=clamp(u/.25)
   lighter(d,mix(346,1020,phase),362,t)
   if u>.3:
    arrow(d,1002,361,1014,424,INK);d.text(792,408,'一根烧完，再点另一根',23)
   bubble(d,160,269,'两头一起烧？')
   clock(d,1133,307,60*u,46,'需要多久',True)
  else:
   n=max(1,3-int((t-pause)/.83));d.round((575,178,790,243),17,WHITE,INK)
   d.text(683,211,f'想一想  {n}',35,b=True)
   clock(d,1133,307,60*((t-pause)/2.5),46,'需要多久',True)
  d.text(694,555,'一头：60 分钟       两头：？',29,b=True)
 elif idx==4:
  heading(d,'两头点燃，30 分钟烧完','相遇的位置不一定在绳子正中间')
  minute=30*ease((u-.05)/.57)
  rope(d,307,minute,minute,0,t,minute<30,minute<30,label='①')
  center=(355+1030)/2;meeting=355+(1030-355)*front(30)
  for yy in range(243,367,10):d.line([(center,yy),(center,yy+4)],'#eeeeee',2)
  d.text(center,386,'长度中点',18,GRAY)
  if u>.41:
   arrow(d,meeting+59,220,meeting,286);d.text(meeting+75,199,'在这里相遇',21)
  clock(d,1131,300,minute,47,'两端同时燃烧')
  # A separate time-coordinate strip makes the proof independent of spatial length.
  d.text(341,461,'时间示意',20,anchor='rm');x0=380;ww=105
  for j in range(6):
   d.round((x0+j*ww,432,x0+(j+1)*ww-5,485),3,'#eeeeea',INK,1)
   d.text(x0+j*ww+ww/2,459,'10 分钟',18)
  consume=minute/60*(6*ww)
  d.rectangle((x0,483,x0+consume,489),'#ba9233')
  if consume>5:d.rectangle((x0+6*ww-consume,483,x0+6*ww-5,489),'#ba9233')
  arrow(d,x0,520,x0+consume,520);arrow(d,x0+6*ww,520,x0+6*ww-consume,520)
  d.text(698,584,'60 ÷ 2 = 30 分钟',35,b=True)
 elif idx in [5,6]:
  second=idx==6
  heading(d,'第二步：再点第二根的另一头' if second else '第一步：一根双头，一根单头','不需要看钟，只需等第一根烧尽' if not second else '剩余单头时间 30 分钟 → 双头只需 15 分钟')
  if second:
   delta=15*ease((u-.12)/.65);minute=30+delta
   rope(d,282,30,30,0,t,label='①')
   rope(d,416,30+delta,delta,1,t,delta<15,delta<15 and u>.12,label='②')
   if u<.25:lighter(d,1027,mix(491,449,u/.12),t)
   if u>.7:
    d.round((502,177,915,227),12,WHITE)
    d.text(709,202,'30 + 15 = 45 分钟',31,b=True)
   else:d.text(689,201,'剩余时间：30 ÷ 2 = 15',27,b=True)
  else:
   minute=30*ease((u-.19)/.57)
   rope(d,282,minute,minute,0,t,minute<30 and u>.05,minute<30 and u>.05,label='①')
   rope(d,416,minute,0,1,t,u>.05,False,label='②')
   if u<.19:
    for x,y in [(355,310),(1030,310),(355,445)]:lighter(d,x,y,t)
    d.text(695,201,'同时点火',27,b=True)
   elif u>.77:
    d.text(694,201,'第一根烧尽：30 分钟到了',27,b=True);check(d,1000,227)
   else:d.text(694,201,'一根双头烧，另一根单头烧',26)
  clock(d,1141,311,minute,44,'共同计时')
  if minute<45:
   remain=60-minute if not second else 30-(minute-30)*2
   d.text(698,478,('第二根还在烧' if not second else f'剩余单头燃烧时间：{max(0,remain):.0f} 分钟'),22)
  else:d.text(694,478,'两根烧尽，计时完成',26,b=True)
  timeline(d,minute)
  if not second and u>.79:d.text(701,623,'第二根剩下的不是“一半长度”，而是 30 分钟',20)
 elif idx==7:
  if u<.21:
   heading(d,'真正被减半的，是时间','不是长度，更不是靠猜')
   rope(d,308,20,0,1,t,True,False,label='②')
   d.text(696,432,'剩余燃烧时间 ÷ 2',39,b=True)
   d.text(696,513,'长度减半',27,GRAY);cross(d,805,510,16)
  else:
   v=clamp((u-.21)/.63)
   minute=30*ease(v/.6) if v<.6 else 30+15*ease((v-.6)/.4)
   delta=max(0,minute-30)
   heading(d,'完整复盘：从 0 到 45 分钟','① 双头 + ② 单头 → ① 烧尽 → 点燃 ② 另一头')
   rope(d,282,min(30,minute),min(30,minute),0,t,minute<30,minute<30,label='①')
   rope(d,416,minute,delta,1,t,minute<45,minute>=30 and minute<45,label='②')
   clock(d,1141,311,minute,44,'总用时')
   if 30<=minute<34:lighter(d,1028,448,t)
   timeline(d,minute)
   if minute>=44.99:
    d.round((523,185,893,236),12,WHITE)
    d.text(708,211,'45 分钟，完成！',35,b=True)
    d.text(693,488,'你最开始，也想过对折吗？',29,b=True)
   elif minute<30:d.text(693,488,'先等第一根烧完',26,b=True)
   else:d.text(693,488,'再等第二根烧完',26,b=True)
 if not cover:
  line=next((s for a,b,s in cues if a<=t<b),'')
  if line:d.text(640,672,line,29,WHITE,stroke=2)
 else:
  d.text(640,669,'没有钟表，不能数秒。你会怎么做？',29,WHITE,stroke=2)
 d.rectangle((0,716,1280,720),'#b4b4b4')
 if not cover:d.rectangle((0,716,max(1,1280*t/TOTAL),720),'#d9b757')
 return im

os.makedirs('checks',exist_ok=True)
for i in range(8):
 for k,frac in enumerate([.28,.76]):
  im=render(starts[i]+dur[i]*frac);im.thumbnail((640,360));im.save(f'checks/{i}-{k}.jpg')
render(starts[0]+dur[0]*.74,True).save('两根绳子_横版封面.jpg',quality=95)
# A visual storyboard is retained for edits, but the deliverable is the finished video.
contact=Image.new('RGB',(1280,1440),'white')
for i in range(8):
 for k in range(2):
  image=Image.open(f'checks/{i}-{k}.jpg');image.thumbnail((320,180))
  contact.paste(image,((i%2)*640+k*320,(i//2)*360))
contact.save('checks/storyboard.jpg')
import sys
if '--check' in sys.argv:
 print('STORYBOARD READY',TOTAL,starts,dur)
 sys.exit(0)
output=str(ROOT / 'deliverables' / ('rope-45-draft.mp4' if DRAFT else 'rope-45-1080p.mp4'))
cmd=[FF,'-y','-f','rawvideo','-pix_fmt','rgb24','-s',f'{W}x{H}','-r',str(FPS),'-i','-','-i','audio/narration-effects.wav','-c:v','libx264','-preset','fast','-crf','19','-pix_fmt','yuv420p','-c:a','aac','-b:a','160k','-movflags','+faststart','-shortest',output]
with open('render.log','w') as log:
 p=subprocess.Popen(cmd,stdin=subprocess.PIPE,stdout=log,stderr=log)
 for k in range(math.ceil(TOTAL*FPS)):
  p.stdin.write(render(k/FPS).tobytes())
  if k%(FPS*10)==0:print(f'{k/FPS:.0f}/{TOTAL:.1f} seconds',flush=True)
 p.stdin.close()
 if p.wait():raise RuntimeError('Video encoding failed; see render.log')
print('DONE',output,TOTAL,os.path.getsize(output))

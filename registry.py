"""Persistent local application registry; shared by server and workflow hook."""
import json, os, re, hashlib, tempfile, fcntl
from pathlib import Path
from urllib.parse import urlparse
from datetime import datetime, timezone
ROOT=Path(__file__).resolve().parent
DATA=Path(os.environ.get('REA_LIBRARY_DATA',ROOT/'library-data')).resolve()

def now(): return datetime.now(timezone.utc).isoformat()
def prepare():
    DATA.mkdir(parents=True,exist_ok=True)
    for name in ['jobs','inbox']: (DATA/name).mkdir(exist_ok=True)
def atomic(path,value):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w',dir=path.parent,delete=False) as f:
        json.dump(value,f,indent=2);f.flush();os.fsync(f.fileno());tmp=f.name
    os.replace(tmp,path)
def registry_edit(fn):
    prepare()
    with (DATA/'registry.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        path=DATA/'registry.json'
        data=json.loads(path.read_text()) if path.exists() else {'version':1,'apps':[]}
        result=fn(data)
        atomic(path,data)
        return result
def apps(): return registry_edit(lambda d:d['apps'])
def valid_url(value):
    p=urlparse(value)
    if p.scheme not in ['http','https'] or not p.netloc or p.username or p.password: raise ValueError('Use an http:// or https:// launch URL without credentials.')
    return value

def artwork_asset(value):
    if not value: return ''
    if not isinstance(value,str) or not value.startswith('assets/'):
        raise ValueError('Artwork must be a library-relative assets/ path.')
    path=(ROOT/value).resolve()
    if not path.is_relative_to((ROOT/'assets').resolve()) or not path.is_file():
        raise ValueError('Artwork file must exist inside the library assets directory.')
    return value

def normalize(m):
    if not isinstance(m,dict): raise ValueError('Manifest must be an object.')
    title=str(m.get('name','')).strip()[:120]
    if not title: raise ValueError('App name is required.')
    kind=m.get('kind','app')
    if kind not in ['app','component','tool']: raise ValueError('Kind must be app, component, or tool.')
    source=m.get('source','custom')
    if source not in ['rea','custom']: raise ValueError('Source must be rea or custom.')
    path=m.get('path','');url=m.get('url','');entry=m.get('entry','index.html')
    if path:
        p=Path(path).expanduser()
        if not p.is_absolute() or not p.exists(): raise ValueError('Project path must be an existing absolute path.')
        path=str(p.resolve())
        if p.is_dir() and p.suffix=='.app' and (p/'Contents/Info.plist').is_file():
            pass
        elif p.is_dir():
            e=(p/entry).resolve()
            if not e.is_relative_to(p.resolve()) or not e.is_file(): raise ValueError('Entry must be an existing file inside the project directory.')
        elif p.suffix not in ['.html','.htm']:
            raise ValueError('Register a web project, HTML entry file, or macOS .app bundle.')
    if url: url=valid_url(url)
    if not path and not url: raise ValueError('Provide a project path or launch URL.')
    identity=path or url
    ident=m.get('id') or re.sub('[^a-z0-9-]','',title.lower().replace(' ','-'))[:50]+'-'+hashlib.sha256(identity.encode()).hexdigest()[:8]
    if not re.fullmatch(r'[a-zA-Z0-9_-]{1,90}',ident): raise ValueError('Invalid app id.')
    evidence=m.get('evidence',[])
    if not isinstance(evidence,list) or not all(isinstance(x,str) for x in evidence): raise ValueError('Evidence must be a list of strings.')
    launchType='url' if url else 'native' if path and Path(path).suffix=='.app' and Path(path).is_dir() else 'web'
    screenshots=m.get('screenshots',[])
    if not isinstance(screenshots,list) or len(screenshots)>12:raise ValueError('Use up to 12 screenshot assets.')
    artwork=dict(icon=artwork_asset(m.get('icon','')),screenshots=[artwork_asset(x) for x in screenshots],cover=artwork_asset(m.get('cover','')),artworkProvenance=str(m.get('artworkProvenance',''))[:2000],artworkPublicSafe=m.get('artworkPublicSafe') is True)
    return dict(**artwork,launchType=launchType,id=ident,name=title,description=str(m.get('description',''))[:4000],kind=kind,source=source,path=path,url=url,entry=entry,status='ready',evidence=evidence[:50],updatedAt=now(),createdAt=now(),jobId=str(m.get('jobId',''))[:90])
def register(m):
    item=normalize(m)
    def update(d):
        previous=next((x for x in d['apps'] if x['id']==item['id']),None)
        if previous:
            item['createdAt']=previous.get('createdAt',now())
            for key in ['icon','screenshots','cover','artworkProvenance','artworkPublicSafe','jobId']:
                if key not in m:item[key]=previous.get(key,item.get(key))
            d['apps'].remove(previous)
        d['apps'].append(item)
        return item
    return registry_edit(update)
def consume_inbox():
    prepare();results=[]
    for p in (DATA/'inbox').glob('*.json'):
        try:
            m=json.loads(p.read_text());a=register(m);p.rename(p.with_suffix('.registered'));results.append(a)
        except Exception as e:
            atomic(p.with_suffix('.error'),{'error':str(e)});p.rename(p.with_suffix('.rejected'))
    return results

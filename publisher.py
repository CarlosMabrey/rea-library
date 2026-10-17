"""Publish an allowlisted library catalog; local credentials and captures stay local."""
import fcntl, hashlib, json, os, re, shutil, subprocess
from pathlib import Path
from urllib.parse import urlparse
import registry

REPOSITORY='CarlosMabrey/rea-library'
URL='https://carlosmabrey.github.io/rea-library/'

def git(repo,*args):
    result=subprocess.run(['git','-C',str(repo),*args],capture_output=True,text=True,timeout=180)
    if result.returncode:raise RuntimeError('Git publication failed: '+result.stderr.strip()[-700:])
    return result.stdout.strip()

def public_text(value,default,limit=400):
    value=str(value or '').strip()
    # Publication never derives text from local paths, logs or raw evidence.
    if any(x in value for x in ('/Users/','/home/','sk-proj-','ghp_','github_pat_')):return default
    return value[:limit] or default

def catalog(items,previous,copy_asset):
    prior={x['id']:x for x in previous};result=[]
    for item in items:
        publication=item.get('publication') or {}
        if publication.get('enabled') is False:continue
        old=prior.get(item['id'],{})
        name=public_text(publication.get('name',item['name']),'Registered project',120)
        row={k:item[k] for k in ('id','kind','source','createdAt','updatedAt')}
        row.update(name=name,status='ready',launchType='companion',evidence=[],url='',description=public_text(publication.get('description',old.get('description')),'A registered '+item['kind']+' in REA Library. Open the local companion to launch or rebuild it.'))
        launch=publication.get('url',old.get('url',''))
        p=urlparse(launch)
        if p.scheme=='https' and p.netloc and not p.username and not p.password and not p.query and not p.fragment and p.hostname not in ('localhost','127.0.0.1'):
            row['url']=launch
        row['icon']=copy_asset(item['icon']) if item.get('iconPublicSafe') is True and item.get('icon') else ''
        shots=item.get('publicScreenshots',[])
        if not shots and item.get('artworkPublicSafe') is True:shots=item.get('screenshots',[])
        row['screenshots']=[copy_asset(x) for x in shots]
        row['cover']=row['screenshots'][0] if row['screenshots'] else ''
        row['artworkPublicSafe']=bool(shots)
        row['artworkProvenance']='Actual app preview reviewed for publication by the capture workflow.' if shots else 'Private screenshots remain in the local companion.'
        if {k:v for k,v in row.items() if k!='updatedAt'}=={k:v for k,v in old.items() if k!='updatedAt'}:
            row['updatedAt']=old['updatedAt']
        result.append(row)
    return sorted(result,key=lambda x:x['id'])

def publish_library():
    from pipeline import config
    cfg=config()
    if cfg.get('githubEnabled') is not True:return {'state':'needs_attention','message':'GitHub publication is not configured.'}
    repo=Path(cfg.get('repoPath','')).resolve()
    if not (repo/'.git').exists():raise ValueError('Configured GitHub checkout is unavailable.')
    if cfg.get('repository')!=REPOSITORY:raise ValueError('Unexpected publication repository.')
    registry.prepare()
    with (registry.DATA/'publication.lock').open('a') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX)
        remote=git(repo,'remote','get-url','origin').removesuffix('.git').lower()
        if remote not in {'https://github.com/'+REPOSITORY.lower(),'git@github.com:'+REPOSITORY.lower()}:raise ValueError('Publication remote does not match the configured library.')
        if git(repo,'branch','--show-current')!='main':raise ValueError('Publication checkout must be on main.')
        if git(repo,'diff','--cached','--name-only'):raise ValueError('Commit or unstage existing changes before automatic publication.')
        # Refuse pending unpushed source changes: automation must only ship its own generated catalog.
        git(repo,'fetch','origin','main')
        pending_file=registry.DATA/'publication-pending.json'
        pending=json.loads(pending_file.read_text()) if pending_file.exists() else {}
        head=git(repo,'rev-parse','HEAD');remote_head=git(repo,'rev-parse','origin/main')
        if pending.get('commit')==head and head!=remote_head and git(repo,'rev-parse','HEAD^')==remote_head:
            git(repo,'push','origin','HEAD:main');pending_file.unlink(missing_ok=True);remote_head=head
        if head!=remote_head:
            raise ValueError('GitHub checkout differs from origin/main; reconcile it before retrying publication.')
        managed=['public-catalog.json','assets/projects','docs']
        if git(repo,'status','--porcelain'):raise ValueError('GitHub checkout has local changes; finish them before retrying publication.')
        previous=json.loads((repo/'public-catalog.json').read_text())
        def copy_asset(ref):
            source=(registry.ROOT/ref).resolve()
            if not source.is_relative_to((registry.ROOT/'assets').resolve()) or not source.is_file():raise ValueError('Public artwork must be inside the library assets directory.')
            if source.suffix.lower() not in {'.png','.jpg','.jpeg','.webp','.ico','.svg'} or source.stat().st_size>20*1024*1024:raise ValueError('Unsupported public artwork.')
            data=source.read_bytes()
            # Existing SVG marks must be inert; future captures use raster files.
            if source.suffix.lower()=='.svg' and re.search(rb'<script|<foreignObject|<!DOCTYPE|<!ENTITY|\bon[a-z]+\s*=|(?:href|src)\s*=\s*[\"\x27](?!#)|url\(\s*(?!#)',data,re.I):raise ValueError('SVG contains active or remote content.')
            ref='assets/projects/published/'+hashlib.sha256(data).hexdigest()[:24]+source.suffix.lower()
            dest=repo/ref;dest.parent.mkdir(parents=True,exist_ok=True)
            if not dest.exists():dest.write_bytes(data)
            return ref
        rows=catalog(registry.apps(),previous,copy_asset)
        registry.atomic(repo/'public-catalog.json',rows)
        built=subprocess.run(['python3',str(repo/'export_site.py')],capture_output=True,text=True,timeout=60)
        if built.returncode:raise RuntimeError('Static export failed: '+built.stderr[-500:])
        git(repo,'add','--',*managed)
        if not git(repo,'diff','--cached','--name-only'):return {'state':'unchanged','url':URL,'message':'Published catalog is current.'}
        git(repo,'commit','-m','Update registered apps and reviewed artwork')
        commit=git(repo,'rev-parse','HEAD')
        try:git(repo,'push','origin','HEAD:main')
        except Exception:
            # A retry may safely push only this exact generated commit, never arbitrary source commits.
            registry.atomic(registry.DATA/'publication-pending.json',{'commit':commit})
            raise
        (registry.DATA/'publication-pending.json').unlink(missing_ok=True)
        return {'state':'published','commit':commit,'url':URL,'message':'Catalog pushed; GitHub Pages deploys it. The ChatGPT site reads the same catalog.'}

#!/usr/bin/env python3
"""Publish transparent role-level statistics without rejecting healthy partial snapshots.

A missing current-patch snapshot never masquerades as current. A verified older
snapshot can be retained as an explicitly marked fallback. No extra Python deps.
"""
from __future__ import annotations
import argparse, json, os, re, sys, time
from pathlib import Path
from datetime import datetime, timezone
from urllib.request import Request,urlopen
from urllib.error import HTTPError,URLError

ROLES=('top','jungle','middle','bottom','support')
ROOT='https://raw.githubusercontent.com/shizukaziye/lol-pool-coverage/main/data'
API='https://api.github.com/repos/shizukaziye/lol-pool-coverage/contents/data/snapshots'
VERSIONS='https://ddragon.leagueoflegends.com/api/versions.json'
PATCH=re.compile(r'^\d{2}\.\d{1,2}$')

def fetch(url,retries=3):
    last=None
    for attempt in range(retries):
        try:
            headers={'User-Agent':'RiftDraftPublic/2.0','Accept':'application/json'}
            if url.startswith('https://api.github.com/') and os.environ.get('GITHUB_TOKEN'):
                headers['Authorization']='Bearer '+os.environ['GITHUB_TOKEN']
            with urlopen(Request(url,headers=headers),timeout=50) as resp:
                data=resp.read(80_000_001)
                if len(data)>80_000_000:raise ValueError('file too large')
            return json.loads(data)
        except (HTTPError,URLError,TimeoutError,ValueError) as exc:
            last=exc
            if attempt<retries-1:time.sleep(1+attempt)
    raise RuntimeError(str(last))

def verkey(p):return tuple(map(int,p.split('.')))

def live_version(obj):
    for v in obj if isinstance(obj,list) else []:
        if isinstance(v,str) and re.match(r'^\d{2}\.\d{1,2}\.\d+',v):return '.'.join(v.split('.')[:2]),v
    raise ValueError('No valid Riot patch reported')

def valid(obj,role,kind,patch=None):
    """Structural checks: no 50-champion arbitrary minimum; real observations required."""
    if not isinstance(obj,dict) or obj.get('lane')!=role:return False,'role mismatch'
    if obj.get('schema_version')!=2:return False,'unsupported schema'
    tier=obj.get('tierlist'); matches=obj.get('matchups')
    if not isinstance(tier,dict) or not isinstance(matches,dict):return False,'missing tierlist/matchups'
    if not tier or not matches:return False,'empty statistics'
    if not any(isinstance(v,dict) and any(k in v for k in ('wr','games','pr')) for v in tier.values()):return False,'no usable tierlist rows'
    if kind=='recent':
        if obj.get('patch')!=patch:return False,'patch mismatch: '+str(obj.get('patch'))
        if not isinstance(obj.get('scraped_at'),str):return False,'missing snapshot timestamp'
    else:
        patches=obj.get('source_patches')
        if not isinstance(patches,list) or not patches:return False,'missing historical patch list'
    return True,''

def load_existing(path, fetcher=fetch, site=None):
    try:return json.loads(path.read_text(encoding='utf8'))
    except (OSError,ValueError):pass
    # GitHub Actions checks out the repository anew for each deployment. The
    # generated data directory is not committed, so on-disk retention alone
    # would never survive to the next run. Recover the last public artifact.
    repository=os.environ.get('GITHUB_REPOSITORY','')
    if site is not None and '/' in repository:
        owner,repo=repository.split('/',1)
        try:
            relative=path.relative_to(site).as_posix()
            return fetcher(f'https://{owner.lower()}.github.io/{repo}/{relative}')
        except Exception:pass
    return None

def put(path,obj):
    path.parent.mkdir(parents=True,exist_ok=True)
    temp=path.with_suffix('.tmp');temp.write_text(json.dumps(obj,separators=(',',':')),encoding='utf8');temp.replace(path)

def build(site:Path,get=fetch):
    riot,asset=live_version(get(VERSIONS))
    listing=get(API)
    patches=sorted((x['name'] for x in listing if isinstance(x,dict) and x.get('type')=='dir' and PATCH.fullmatch(str(x.get('name',''))) and verkey(x['name'])<=verkey(riot)),key=verkey,reverse=True)
    if not patches:raise ValueError('No source patches at/before Riot '+riot)
    latest=patches[0]
    manifest={'schema_version':2,'generated_at':datetime.now(timezone.utc).isoformat(),'riot_patch':riot,'source_patch':latest,'source_fresh':riot==latest,'asset_version':asset,'provider':'shizukaziye/lol-pool-coverage','recent':{},'history':{}}
    for role in ROLES:
        recent_path=site/'data'/'recent'/f'{role}.json'
        errors=[];obj=None;chosen=None;retained=False
        # Prefer the latest patch, but accept an earlier verified snapshot as a
        # visibly stale fallback. Each role is independent.
        for patch in patches[:5]:
            try:
                x=get(f'{ROOT}/snapshots/{patch}/{role}.json')
                ok,reason=valid(x,role,'recent',patch)
                if not ok:raise ValueError(reason)
                obj=x;chosen=patch;break
            except Exception as exc:errors.append(f'{patch}: {str(exc)[:130]}')
        if obj is None:
            old=load_existing(recent_path,get,site)
            oldpatch=old.get('patch') if isinstance(old,dict) else None
            if oldpatch and PATCH.fullmatch(oldpatch) and verkey(oldpatch)<=verkey(riot):
                ok,_=valid(old,role,'recent',oldpatch)
                if ok:obj=old;chosen=oldpatch;retained=True
        if obj is not None:
            put(recent_path,obj)
            manifest['recent'][role]={'available':True,'patch':chosen,'current':chosen==riot,'source_latest':chosen==latest,'retained':retained,'updated_at':obj.get('scraped_at'),'note':'; '.join(errors[:2]) if errors else ''}
        else:
            recent_path.unlink(missing_ok=True)
            manifest['recent'][role]={'available':False,'patch':None,'current':False,'error':'; '.join(errors[:3])}
        hist_path=site/'data'/'history'/f'{role}.json'
        try:
            h=get(f'{ROOT}/weighted/{role}.json')
            ok,reason=valid(h,role,'history')
            if not ok:raise ValueError(reason)
            put(hist_path,h)
            manifest['history'][role]={'available':True,'patches':h.get('source_patches',[]),'updated_at':h.get('generated_at')}
        except Exception as exc:
            old=load_existing(hist_path,get,site)
            ok,_=valid(old,role,'history')
            if ok:
                manifest['history'][role]={'available':True,'patches':old.get('source_patches',[]),'retained':True,'warning':str(exc)[:180]}
            else:
                hist_path.unlink(missing_ok=True)
                manifest['history'][role]={'available':False,'error':str(exc)[:200]}
        print(role,'recent',manifest['recent'][role], 'history', manifest['history'][role]['available'],flush=True)
    if not any(x['available'] for kind in ('recent','history') for x in manifest[kind].values()):
        raise RuntimeError('No usable statistics; aborting deployment')
    put(site/'data'/'manifest.json',manifest)
    return manifest

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--site',type=Path,default=Path(__file__).resolve().parents[1]/'site');args=parser.parse_args();build(args.site)

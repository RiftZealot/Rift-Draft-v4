#!/usr/bin/env python3
"""Optional rank-cohort League matchup collector from Riot's *official* API.

No third-party scraping; no individual data published. A cohort is seeded by
players with the named current Solo/Duo rank. It DOES NOT establish that each
player in each sampled match had that rank, or that rank was their rank at match
start. Never market the sample as all Diamond+ games. Requires a production
API key for a publicly distributed service.
"""
from __future__ import annotations
import argparse, collections, datetime, json, os, random, sys, time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

BRACKETS={
 'gold_plus':('GOLD','PLATINUM','EMERALD','DIAMOND','MASTER','GRANDMASTER','CHALLENGER'),
 'platinum_plus':('PLATINUM','EMERALD','DIAMOND','MASTER','GRANDMASTER','CHALLENGER'),
 'emerald_plus':('EMERALD','DIAMOND','MASTER','GRANDMASTER','CHALLENGER'),
 'diamond_plus':('DIAMOND','MASTER','GRANDMASTER','CHALLENGER'),
 'master_plus':('MASTER','GRANDMASTER','CHALLENGER'),
}
ROLES=('top','jungle','middle','bottom','support')
ROLEMAP={'TOP':'top','JUNGLE':'jungle','MIDDLE':'middle','BOTTOM':'bottom','UTILITY':'support'}
PLATFORMS={'NA1':'americas','BR1':'americas','LA1':'americas','LA2':'americas',
           'EUW1':'europe','EUN1':'europe','TR1':'europe','RU':'europe',
           'KR':'asia','JP1':'asia','SG2':'sea','TW2':'sea','VN2':'sea','OC1':'sea'}

class Riot:
 def __init__(self,key,platform='NA1',budget=600):
  self.key=key;self.platform=platform;self.region=PLATFORMS[platform];self.budget=budget;self.used=0
 def get(self,url):
  if self.used>=self.budget:raise RuntimeError('Riot request budget reached')
  for attempt in range(4):
   req=Request(url,headers={'X-Riot-Token':self.key,'User-Agent':'RiftDraft/1.0 (rank-aggregates)'})
   try:
    self.used+=1
    with urlopen(req,timeout=18) as r:return json.load(r)
   except HTTPError as e:
    if e.code==429 and attempt<3:
     wait=min(130,int(e.headers.get('Retry-After','4')))
     time.sleep(wait);continue
    raise RuntimeError(f'Riot HTTP {e.code} for API request') from e
   except (TimeoutError,URLError) as e:
    if attempt==3:raise RuntimeError(str(e)) from e
    time.sleep(2+attempt)
  raise RuntimeError('Failed Riot request')
 def platform_url(self,path):return f'https://{self.platform.lower()}.api.riotgames.com{path}'
 def region_url(self,path):return f'https://{self.region}.api.riotgames.com{path}'


def participants(match,patch):
 """Return role/team/champ/win tuples only for complete, current-patch SoloQ games."""
 info=match.get('info') or {}
 if info.get('queueId')!=420 or info.get('gameDuration',0)<600:return None
 version=str(info.get('gameVersion',''))
 if '.'.join(version.split('.')[:2])!=patch:return None
 p=info.get('participants') or []
 if len(p)!=10:return None
 result=[]
 for o in p:
  role=ROLEMAP.get(str(o.get('teamPosition','')).upper());cid=o.get('championId');team=o.get('teamId')
  if not role or not isinstance(cid,int) or team not in (100,200):return None
  result.append((int(team),role,str(cid),bool(o.get('win'))))
 for team in (100,200):
  if sorted(x[1] for x in result if x[0]==team)!=sorted(ROLES):return None
 return result


def aggregate(matches,patch,bracket,region='NA1'):
 """A rank-seeded sample; every unique match counted once per bracket."""
 totals=collections.defaultdict(lambda:[0,0]);same=collections.defaultdict(lambda:[0,0]);role_total=collections.Counter();used=0
 for match in matches:
  p=participants(match,patch)
  if not p:continue
  used+=1
  for team,role,cid,win in p:
   totals[(role,cid)][0]+=1;totals[(role,cid)][1]+=int(win);role_total[role]+=1
   for other_team,other_role,opp,_ in p:
    if other_team!=team:
     same[(role,cid,other_role,opp)][0]+=1;same[(role,cid,other_role,opp)][1]+=int(win)
 result={}
 for role in ROLES:
  t={};m={}
  for (r,cid),(games,wins) in totals.items():
   if r!=role:continue
   t[cid]={'wr':round(100*wins/games,4),'pr':round(100*games/max(1,role_total[role]),4),'games':games}
  for (r,cid,opp_role,opp),(games,wins) in same.items():
   if r!=role:continue
   prior=totals.get((role,cid));
   if not prior:continue
   # Baseline residual in percentage points; is NOT Lolalytics Delta2.
   delta=100*wins/games-100*prior[1]/prior[0]
   m.setdefault(cid,{}).setdefault(opp_role,{})[opp]={'d2':round(delta,4),'games':games}
  result[role]={'schema_version':2,'lane':role,'patch':patch,'rank_bracket':bracket,
                'rank_definition':'sampled players current SoloQ tier (not verified full-lobby tier)',
                'metric':'matchup win rate minus champion role win rate (percentage points)',
                'region':region,'scraped_at':datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'sample_matches':used,'tierlist':t,'matchups':m}
 return result


def sample_riot(riot,patch,max_per_tier=8,ids_per_player=4):
 """Select ranked players by current rank and fetch deduplicated match histories.

 Sampling aims for coverage, not a representative distribution. No player IDs
 or raw match data are ever included in the published JSON.
 """
 tiers=('GOLD','PLATINUM','EMERALD','DIAMOND','MASTER','GRANDMASTER','CHALLENGER')
 matches_by_tier={x:{} for x in tiers};rng=random.Random(20622)
 for tier in tiers:
  try:
   if tier in ('MASTER','GRANDMASTER','CHALLENGER'):
    url=riot.platform_url(f'/lol/league/v4/{tier.lower()}leagues/by-queue/RANKED_SOLO_5x5')
    entries=(riot.get(url) or {}).get('entries',[])
   else:
    division=rng.choice(('I','II','III','IV'))
    entries=riot.get(riot.platform_url(f'/lol/league/v4/entries/RANKED_SOLO_5x5/{tier}/{division}?page=1'))
   if not isinstance(entries,list):continue
   rng.shuffle(entries)
   for player in entries[:max_per_tier]:
    puuid=player.get('puuid')
    if not puuid:continue
    ids=riot.get(riot.region_url(f'/lol/match/v5/matches/by-puuid/{quote(puuid,safe="")}/ids?queue=420&start=0&count={ids_per_player}'))
    if not isinstance(ids,list):continue
    for match_id in ids:
     if match_id in matches_by_tier[tier]:continue
     try:matches_by_tier[tier][match_id]=riot.get(riot.region_url(f'/lol/match/v5/matches/{quote(match_id,safe="")}'))
     except RuntimeError:continue
  except RuntimeError as exc:
   print(f'{tier}: {exc}',file=sys.stderr)
   if 'budget' in str(exc):break
 return matches_by_tier


def publish(site,patch,samples,platform='NA1'):
 site=Path(site);p=site/'data'/'manifest.json'
 if not p.exists():raise RuntimeError('Run sync_data.py first: data/manifest.json missing')
 manifest=json.loads(p.read_text())
 existing=manifest.get('ranks',{})
 manifest['ranks']=existing
 for bracket,tiers in BRACKETS.items():
  # Each Riot match once per bracket, even if multiple sampled players were there.
  distinct={}
  for tier in tiers:distinct.update(samples.get(tier,{}))
  data=aggregate(distinct.values(),patch,bracket,platform)
  stats={}
  for role,doc in data.items():
   path=site/'data'/'ranks'/bracket/(role+'.json')
   if not doc['tierlist'] or doc['sample_matches']<50:
    stats[role]={'available':False,'reason':'Fewer than 50 current-patch sampled matches; not enough evidence','sample_matches':doc['sample_matches']}
    continue
   path.parent.mkdir(parents=True,exist_ok=True);path.write_text(json.dumps(doc,separators=(',',':')))
   stats[role]={'available':True,'patch':patch,'sample_matches':doc['sample_matches'],
                'source':'Riot official API; rank-anchored player sample','region':platform}
  manifest['ranks'][bracket]=stats
 p.write_text(json.dumps(manifest,separators=(',',':')))
 return manifest

if __name__=='__main__':
 ap=argparse.ArgumentParser();ap.add_argument('--site',default='site');ap.add_argument('--platform',choices=PLATFORMS,default='NA1');ap.add_argument('--max-requests',type=int,default=600);ap.add_argument('--players-per-tier',type=int,default=8);ap.add_argument('--matches-per-player',type=int,default=4)
 args=ap.parse_args();key=os.environ.get('RIOT_API_KEY','').strip()
 if not key:
  print('RIOT_API_KEY not configured; skipping optional rank-seeded datasets. Default statistics unaffected.');sys.exit(0)
 manifest=json.loads((Path(args.site)/'data'/'manifest.json').read_text())
 patch='.'.join(str(manifest['asset_version']).split('.')[:2])
 matches=sample_riot(Riot(key,args.platform,args.max_requests),patch,args.players_per_tier,args.matches_per_player)
 result=publish(args.site,patch,matches,args.platform)
 print('Rank datasets status:',{r:sum(x.get('available',False) for x in v.values()) for r,v in result['ranks'].items()})

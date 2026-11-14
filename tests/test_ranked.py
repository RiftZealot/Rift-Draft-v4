import unittest,sys,tempfile,json
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from collect_ranked import participants,aggregate,publish,BRACKETS

def make_game(patch='16.22',flip=False):
 roles=['TOP','JUNGLE','MIDDLE','BOTTOM','UTILITY']; p=[]
 for team in (100,200):
  for k,role in enumerate(roles):
   p.append({'teamId':team,'teamPosition':role,'championId':(100+k if team==100 else 200+k),'win':(team==100)!=flip})
 return {'info':{'queueId':420,'gameDuration':1500,'gameVersion':patch+'.1','participants':p}}

class TestRanked(unittest.TestCase):
 def test_aggregate_counts_and_roles(self):
  d=aggregate([make_game(),make_game(flip=True)],'16.22','diamond_plus')
  self.assertEqual(len(d),5);self.assertEqual(d['top']['tierlist']['100']['games'],2)
  self.assertEqual(d['top']['tierlist']['100']['wr'],50)
  self.assertEqual(d['top']['matchups']['100']['jungle']['201']['games'],2)
  self.assertEqual(d['top']['matchups']['100']['jungle']['201']['d2'],0)
 def test_reject_wrong_patch_or_mode(self):
  self.assertIsNone(participants(make_game('16.21'),'16.22'))
  m=make_game();m['info']['queueId']=450
  self.assertIsNone(participants(m,'16.22'))
 def test_patch_status_and_publish(self):
  with tempfile.TemporaryDirectory() as td:
   site=Path(td);(site/'data').mkdir();(site/'data'/'manifest.json').write_text(json.dumps({'riot_patch':'16.22'}))
   matches={'DIAMOND':{str(i):make_game(flip=(i%2==0)) for i in range(60)}}
   man=publish(site,'16.22',matches)
   self.assertTrue(man['ranks']['diamond_plus']['top']['available'])
   self.assertFalse(man['ranks']['master_plus']['top']['available'])
   data=json.loads((site/'data/ranks/diamond_plus/top.json').read_text())
   self.assertEqual(data['rank_bracket'],'diamond_plus')
   self.assertEqual(data['sample_matches'],60)
   self.assertEqual(data['tierlist']['100']['wr'],50)
if __name__=='__main__':unittest.main()

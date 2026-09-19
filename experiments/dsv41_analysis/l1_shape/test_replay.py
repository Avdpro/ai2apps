import sys,unittest,copy
from pathlib import Path
import numpy as np
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'dsv41_mlx'))
from l1_shape import validate_shape,SCHEMA,POLICY
from replay import layer_replay
from fit import solve
class Tests(unittest.TestCase):
    def test_growth_budget(self):
        d=dict(schema='dsv41.l1-shape/growth-v1',family='deepseek_v41',checkpoint_index_sha256='abc',capacities=[48]*8+[40]*32,hot_slots=8,policy=POLICY)
        self.assertEqual(sum(validate_shape(d,'abc')),1664)
        for caps in [[48]*7+[40]*33,[48]*9+[40]*31,[48]*8+[36]+[40]*31]:
            bad=copy.deepcopy(d);bad['capacities']=caps
            with self.assertRaises(ValueError):validate_shape(bad,'abc')
    def test_schema(self):
        d=dict(schema=SCHEMA,family='deepseek_v41',checkpoint_index_sha256='abc',capacities=[40]*40,hot_slots=8,policy=POLICY)
        self.assertEqual(validate_shape(d,'abc'),(40,)*40)
        d['checkpoint_manifest_sha256']='manifest'
        self.assertEqual(validate_shape(d,'abc',checkpoint_manifest_sha256='manifest'),(40,)*40)
        with self.assertRaises(ValueError):validate_shape(d,'abc',checkpoint_manifest_sha256='different')
        for key,value in [('schema','future'),('capacities',[40]*39),('capacities',[True]*40),('capacities',[48]*40),('capacities',[39,41]+[40]*38),('checkpoint_index_sha256','wrong'),('hot_slots',9),('policy','oracle')]:
            bad=copy.deepcopy(d);bad[key]=value
            with self.assertRaises(ValueError):validate_shape(bad,'abc')
    def test_dp_nonconcave(self):
        cost=np.zeros((40,5));cost[:,2]=-1;cost[0,4]=-20;cost[1,0]=-10
        result=solve(cost)
        self.assertEqual(sum(result),1600);self.assertEqual(result[:2],[48,32]);self.assertTrue(all(x==40 for x in result[2:]))
    def test_future_does_not_change_prefix(self):
        pre=np.tile(np.arange(6),(5,1));a=np.tile(np.arange(50,56),(64,1));b=a.copy();b[32:]=np.arange(100,106)
        left=layer_replay(pre,a,40);right=layer_replay(pre,b,40)
        self.assertEqual(left['events'][:32],right['events'][:32]);self.assertGreater(len(left['promotions']),0)
    def test_hot_and_promotion(self):
        pre=np.arange(60).reshape(10,6);dec=np.tile(np.arange(54,60),(64,1))
        r=layer_replay(pre,dec,40)
        self.assertEqual(r['counts'][2],0);self.assertGreater(r['loads'],0);self.assertGreater(r['hot_promotion_reads'],0) # promotion rereads even if Hot
if __name__=='__main__':unittest.main()

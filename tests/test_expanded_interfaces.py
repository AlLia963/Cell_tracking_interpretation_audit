"""Regression checks for declared-contract and primitive-witness obligations."""
from pathlib import Path
import unittest,tempfile,json,gzip,shutil,subprocess,sys,hashlib
import numpy as np
P=Path(__file__).resolve().parents[1]/'paper/expanded';sys.path.insert(0,str(P))
import compare
import verify_endpoints
from unittest.mock import patch

class ExpandedInterfaces(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.ref=self.root/'reference.npz';self.pred=self.root/'prediction.npz';self.perm=self.root/'permuted.npz'
        self.save(self.ref,[1,2,3],[[0,0,0,0],[1,0,0,0],[2,0,0,0]],[[1,2],[2,3]])
        ids=np.array([10,20,21,22,30]);coords=np.array([[0,0,0,0],[1,0,0,-1],[1,0,0,1],[1,0,0,1000],[2,0,0,0]],float)
        self.save(self.pred,ids,coords,[[10,20]])
        perm=[4,2,0,3,1];self.save(self.perm,ids[perm],coords[perm],[[10,20]])
    def tearDown(self):self.tmp.cleanup()
    def save(self,path,ids,coords,edges):np.savez_compressed(path,ids=np.array(ids,np.int64),coords=np.array(coords,float),edges=np.array(edges,np.int64),unit=np.array('um'))
    def create(self,contract='identical-input',after=None):
        task=self.root/'task';compare.run(self.ref,self.pred,after or self.pred,task,contract=contract);return task
    def check(self,task,after=None):
        p=subprocess.run([sys.executable,str(P/'verify_endpoints.py'),'--task',str(task),'--reference',str(self.ref),'--before',str(self.pred),'--after',str(after or self.pred)],capture_output=True,text=True)
        return p.returncode,p.stdout+p.stderr
    def mutate_family(self,task,mutation,rebind):
        r=json.loads((task/'REPORT.json').read_text(encoding='utf8'))
        for path in(task/'frame_cache').rglob('*.json.gz'):
            with gzip.open(path,'rt',encoding='utf8')as f:v=json.load(f)
            if v['frame']!=1:continue
            for w in v['worlds']:mutation(w)
            with gzip.open(path,'wt',encoding='utf8')as f:json.dump(v,f)
            if rebind:r['artifact_bindings'][str(path.relative_to(task)).replace('\\','/')]=hashlib.sha256(path.read_bytes()).hexdigest()
        (task/'REPORT.json').write_text(json.dumps(r),encoding='utf8')
    def test_row_permutation_preserves_identical_graph_zero(self):
        task=self.create(after=self.perm);r=json.loads((task/'REPORT.json').read_text(encoding='utf8'))
        self.assertEqual(r['linked_frames'],[0,1,2])
        for key in ['gains','losses','net']:self.assertEqual(r['bounds'][key],{'minimum':0,'maximum':0})
        self.assertEqual(self.check(task,self.perm)[0],0)
    def test_invalid_api_contract_or_cap_rejected_before_io(self):
        for kwargs in [{'contract':'identical-inpt'}, {'cap':True}, {'cap':1.5}, {'cap':0}]:
            with self.subTest(kwargs=kwargs), patch.object(compare.E, 'load_graph') as read:
                out=self.root/'invalid'
                with self.assertRaises(ValueError):compare.run('absent','absent','absent',out,**kwargs)
                read.assert_not_called()
                self.assertFalse(out.exists())
    def test_renamed_endpoint_cannot_hide_false_maximum(self):
        task=self.create();r=json.loads((task/'REPORT.json').read_text(encoding='utf8'))
        r['whole_map_endpoint_witnesses']['net_repeat']=r['whole_map_endpoint_witnesses'].pop('net_maximum')
        r['bounds']['net']['repeat']=0;r['bounds']['net']['maximum']=999
        (task/'REPORT.json').write_text(json.dumps(r),encoding='utf8')
        self.assertNotEqual(self.check(task)[0],0)
        del r['bounds']['net']['repeat']
        with self.assertRaisesRegex(ValueError,'ten named'):verify_endpoints.validate_endpoint_schema(r)
    def test_closed_endpoint_schema_and_integer_values(self):
        task=self.create();original=json.loads((task/'REPORT.json').read_text(encoding='utf8'))
        mutations=[
            lambda r:r['bounds'].pop('gains'),
            lambda r:r['bounds']['net'].update(maximum=False),
            lambda r:r['bounds']['net'].update(minimum=1,maximum=0),
            lambda r:r['whole_map_endpoint_witnesses']['net_minimum']['values'].update(net=0.0),
            lambda r:r['whole_map_endpoint_witnesses']['net_minimum']['values'].update(extra=0),
            lambda r:r['whole_map_endpoint_witnesses'].update(extra=r['whole_map_endpoint_witnesses']['net_minimum']),
        ]
        for mutation in mutations:
            r=json.loads(json.dumps(original));mutation(r)
            with self.assertRaises(ValueError):verify_endpoints.validate_endpoint_schema(r)
    def test_report_only_contract_relabelling_rejected(self):
        task=self.create('independent');r=json.loads((task/'REPORT.json').read_text(encoding='utf8'));r['contract']='identical-input';(task/'REPORT.json').write_text(json.dumps(r),encoding='utf8')
        code,msg=self.check(task);self.assertNotEqual(code,0);self.assertIn('contract mismatch',msg)
    def test_reference_and_edge_order_do_not_change_readouts(self):
        task=self.create();original=json.loads((task/'REPORT.json').read_text(encoding='utf8'))
        with np.load(self.ref,allow_pickle=False)as z:g={k:z[k].copy()for k in z.files}
        g['ids']=g['ids'][::-1];g['coords']=g['coords'][::-1];g['edges']=g['edges'][::-1];np.savez_compressed(self.ref,**g)
        other=self.root/'reordered';compare.run(self.ref,self.pred,self.perm,other)
        actual=json.loads((other/'REPORT.json').read_text(encoding='utf8'));self.assertEqual(original['bounds'],actual['bounds']);self.assertEqual(original['linked_frames'],actual['linked_frames']);self.assertEqual(self.check(other,self.perm)[0],0)
    def test_real_identity_and_geometry_changes_remain_unlinked(self):
        for field in ['ids','coords']:
            with np.load(self.pred,allow_pickle=False)as z:g={k:z[k].copy()for k in z.files}
            if field=='ids':g['ids'][2]=25
            else:g['coords'][2,3]=1.25
            np.savez_compressed(self.perm,**g);task=self.root/field;compare.run(self.ref,self.pred,self.perm,task)
            report=json.loads((task/'REPORT.json').read_text(encoding='utf8'));self.assertNotIn(1,report['linked_frames']);self.assertEqual(self.check(task,self.perm)[0],0)
    def test_rebound_contract_still_requires_actual_links(self):
        task=self.create('independent');r=json.loads((task/'REPORT.json').read_text(encoding='utf8'));d=json.loads((task/'COMPARISON_CONTRACT.json').read_text(encoding='utf8'));r['contract']=d['contract']='identical-input';(task/'COMPARISON_CONTRACT.json').write_text(json.dumps(d),encoding='utf8');r['artifact_bindings']['COMPARISON_CONTRACT.json']=hashlib.sha256((task/'COMPARISON_CONTRACT.json').read_bytes()).hexdigest();(task/'REPORT.json').write_text(json.dumps(r),encoding='utf8')
        code,msg=self.check(task);self.assertNotEqual(code,0);self.assertIn('links differ',msg)
    def test_changed_family_binding_rejected(self):
        task=self.create();self.mutate_family(task,lambda w:w.update({'999999':888888}),False);code,msg=self.check(task);self.assertNotEqual(code,0);self.assertIn('artifact changed',msg)
    def test_rebound_nonexistent_endpoints_rejected(self):
        task=self.create();self.mutate_family(task,lambda w:w.update({'999999':888888}),True);code,msg=self.check(task);self.assertNotEqual(code,0);self.assertIn('absent or in wrong primitive frame',msg)
    def test_rebound_wrong_frame_rejected(self):
        task=self.create();self.mutate_family(task,lambda w:w.update({'2':10}),True);code,msg=self.check(task);self.assertNotEqual(code,0);self.assertIn('wrong primitive frame',msg)
    def test_rebound_outside_gate_rejected(self):
        task=self.create();self.mutate_family(task,lambda w:w.update({'2':22}),True);code,msg=self.check(task);self.assertNotEqual(code,0);self.assertIn('outside declared gate',msg)
    def test_rebound_fractional_identity_rejected(self):
        task=self.create();self.mutate_family(task,lambda w:w.update({'2':20.5}),True);code,msg=self.check(task);self.assertNotEqual(code,0);self.assertIn('exact integer IDs',msg)
    def test_duplicate_and_unknown_frame_choices_rejected(self):
        task=self.create();original=json.loads((task/'REPORT.json').read_text(encoding='utf8'))
        for duplicate in [True,False]:
            r=json.loads(json.dumps(original));w=next(iter(r['whole_map_endpoint_witnesses'].values()));w['frame_map_choices'].append(w['frame_map_choices'][0] if duplicate else [0,99999,0]);(task/'REPORT.json').write_text(json.dumps(r),encoding='utf8');code,msg=self.check(task);self.assertNotEqual(code,0);self.assertIn('Duplicate or unknown frame map choice',msg)
    def test_isolated_incomplete_frame_emits_withheld_report(self):
        for path,start in [(self.ref,1000),(self.pred,2000)]:
            with np.load(path,allow_pickle=False)as z:g={k:z[k].copy()for k in z.files}
            g['ids']=np.concatenate([g['ids'],np.arange(start,start+8,dtype=np.int64)])
            g['coords']=np.concatenate([g['coords'],np.tile([3.,0.,0.,0.],(8,1))]);np.savez_compressed(path,**g)
        task=self.create();r=json.loads((task/'REPORT.json').read_text(encoding='utf8'));self.assertEqual(r['status'],'WITHHELD_FRAME');self.assertIsNone(r['bounds']);self.assertTrue(r['incomplete_frames']);self.assertNotIn('whole_map_endpoint_witnesses',r)

if __name__=='__main__':unittest.main()

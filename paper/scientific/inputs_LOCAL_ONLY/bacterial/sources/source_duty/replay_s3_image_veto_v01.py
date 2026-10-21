import sys
sys.dont_write_bytecode=True
import hashlib, importlib.util, json, traceback
from pathlib import Path
from collections import defaultdict
ROOT=Path(__file__).resolve().parent; OUT=ROOT/'S3_image_veto_replay_v0.1'; SCORE=ROOT/'S3_image_veto_scores_v0.1/scores.json'
def sha(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def main():
    OUT.mkdir(exist_ok=False)
    score=json.loads(SCORE.read_text(encoding='utf-8')); lookup={}
    for r in score['rows']:
        for q in r['scores']:
            key=(r['film'],r['frame'],*q['point'])
            if key in lookup:assert lookup[key]==q['score']
            lookup[key]=q['score']
    spec=importlib.util.spec_from_file_location('sensitivity',ROOT/'real_S3_policy_sensitivity_v0.1/run_sensitivity.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    ns,env=m.producer_namespace();assert sha(m.SOURCE)==score['source_sha256'];assert ns['DEEPCENTER_SAFE_DIV_VETO'];assert ns['DEEPCENTER_SAFE_DIV_THRESHOLD']==score['threshold']==0.25
    rows=[];hashes={}; used=set()
    for film in sorted(p for p in m.GRAPHS.iterdir() if p.is_dir()):
        inputs=[film/'S2_gap_closing.npz',film/'S3_safe_divisions.npz'];nodes,edges=m.load_graph(inputs[0]);n3,e3=m.load_graph(inputs[1]);assert nodes==n3
        hashes.update({str(p):sha(p) for p in inputs});queries=[]
        def veto(dataset,frame,point,bundle,frames,heatmaps,stats,prefix,threshold):
            key=(dataset,int(frame),*map(float,point));assert key in lookup,('missing_score',key)
            used.add(key);value=lookup[key];accepted=value>=threshold
            stats['deepcenter_'+prefix+'_checked']+=1;stats['deepcenter_'+prefix+('_accepted' if accepted else '_rejected')]+=1
            queries.append(dict(frame=int(frame),point=list(point),score=value,accepted=accepted));return accepted
        ns['deepcenter_accept_repair_point']=veto;stats=defaultdict(int)
        result=ns['add_safe_divisions_postlink'](nodes,edges,stats,dataset=film.name)
        old={(e['source_id'],e['target_id']) for e in edges};historical={(e['source_id'],e['target_id']) for e in e3}-old;replayed={(e['source_id'],e['target_id']) for e in result}-old
        rows.append(dict(film=film.name,historical_additions=len(historical),replayed_additions=len(replayed),exact_added_edge_parity=historical==replayed,historical_only=sorted(historical-replayed),replay_only=sorted(replayed-historical),added_edges=sorted(replayed),stats=dict(stats),queries=queries))
        print(film.name,'historical',len(historical),'replayed',len(replayed),'parity',historical==replayed,flush=True)
    (OUT/'report.json').write_text(json.dumps(dict(rows=rows,all_exact_parity=all(r['exact_added_edge_parity'] for r in rows),source_sha256=sha(m.SOURCE),score_sha256=sha(SCORE),script_sha256=sha(Path(__file__)),input_hashes=hashes,available_unique_scores=len(lookup),used_unique_scores=len(used),scope='Graph boundary image-veto replay using available readonly community checkpoint and image subset; not causal responsibility certification or historical image byte-identity proof'),indent=2),encoding='utf-8')
if __name__=='__main__':
    try:main()
    except Exception:
        if OUT.exists():(OUT/'failure.json').write_text(json.dumps(dict(traceback=traceback.format_exc())),encoding='utf-8')
        raise

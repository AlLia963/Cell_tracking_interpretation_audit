from pathlib import Path
import json
import numpy as np
import audit_engine as E
R=Path(__file__).resolve().parents[1];O=R/'04_统一重分析';D=R/'05_补证与核验/历史计数对照';records=json.loads((D/'RESOLVED_DIFFERENCES.json').read_text(encoding='utf8'));out=[]
for row in records['results']:
    if row['historical_counts_reproduced']:continue
    source=next(x for x in json.loads((D/'RESULT.json').read_text(encoding='utf8'))['differing_records']if x['film']==row['film']and x['asset_id']==row['asset_id']);gid=source['graph_id'];g=E.load_graph(O/'graphs'/(gid+'.npz'));ref=E.load_graph(O/'references'/(row['film']+'.npz'));s=E.read_json_gz(O/'graph_reports'/(gid+'.json.gz'))
    with np.load(O/'visibility'/(gid+'.npz'),allow_pickle=False)as z:v={k:z[k].copy()for k in z.files}
    result=E.coupled_contrast(g,g,ref,s,s,v,v,O/'frame_cache');assert result['status']=='COMPLETE';w=result['whole_map_endpoint_witnesses']['before_TP_maximum'];m={int(q):p for q,p in s['canonical_map'].items()}
    for side,t,index in w['frame_map_choices']:
        if side!=0:continue
        f=E.read_json_gz(O/'frame_cache'/s['frame_locators'][str(t)])
        for q in f['reference_ids']:m.pop(q,None)
        m.update(f['worlds'][index])
    inv={p:q for q,p in m.items()};re=set(map(tuple,ref.edges.tolist()));ro={a for a,b in re};ri={b for a,b in re};pairs=set(map(tuple,g.edges.tolist()));tp=sum((m.get(a),m.get(b))in pairs for a,b in re);fp=sum((inv.get(a),inv.get(b))not in re and(inv.get(a)in ro or inv.get(b)in ri)for a,b in pairs);counts=[tp,fp,len(re)-tp]
    out.append({'asset_id':row['asset_id'],'film':row['film'],'graph_id':gid,'historical_counts':row['historical_counts'],'exact_family_endpoint_counts':counts,'historical_counts_supported_by_complete_map':counts==row['historical_counts'],'whole_map_choices':w['frame_map_choices'],'does_not_identify_original_canonical_tie_break':True})
(D/'LEGACY_TIE_COMPATIBILITY.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8');print('compatible whole-map counts',sum(x['historical_counts_supported_by_complete_map']for x in out),'/',len(out))

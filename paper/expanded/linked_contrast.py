"""Exact scalar contrasts with declared equality of identical matching inputs."""
from collections import defaultdict
from itertools import product
import math
import numpy as np
import audit_engine as E

METRICS=['before_TP','after_TP','gains','losses','net']
def signature(world):return tuple(sorted((int(k),int(v))for k,v in world.items()))

def classify_links(graphs,reference,frames):
    records=[]
    for t in sorted(frames[0]):
        a,b=[E.framed(g,t)for g in graphs];fa,fb=frames[0][t],frames[1][t]
        # Object identity determines rows; storage permutation is not new evidence.
        a,b=[E.Graph(g.ids[np.argsort(g.ids)],g.coords[np.argsort(g.ids)],g.edges,g.unit)for g in [a,b]]
        if a.unit!=b.unit or a.unit!=reference.unit:reason='UNIT_MISMATCH'
        elif not np.array_equal(a.ids,b.ids):reason='PREDICTED_NODE_IDENTITIES_DIFFER'
        elif not np.array_equal(a.coords,b.coords):reason='PREDICTED_COORDINATES_DIFFER'
        elif fa['status']!='COMPLETE'or fb['status']!='COMPLETE':reason='FAMILY_INCOMPLETE'
        elif {signature(w)for w in fa['worlds']}!={signature(w)for w in fb['worlds']}:reason='IDENTICAL_INPUT_FAMILY_MISMATCH'
        else:reason='LINKED_IDENTICAL_MATCHING_INPUT'
        records.append({'frame':int(t),'status':reason,'before_nodes':len(a.ids),'after_nodes':len(b.ids),'before_family':len(fa.get('worlds',[])),'after_family':len(fb.get('worlds',[]))})
    return records

def linked_contrast(graphs,reference,summaries,visibility,frames,cap=1048576,enable_links=True):
    links=classify_links(graphs,reference,frames)
    if any(x['status']=='IDENTICAL_INPUT_FAMILY_MISMATCH'for x in links):return {'status':'WITHHELD_DOMAIN_INCONSISTENCY','bounds':None,'linkage':links}
    incomplete=[{'side':side,'frame':int(t),'status':f.get('status','MISSING_STATUS')}for side,fs in enumerate(frames)for t,f in fs.items()if f.get('status')!='COMPLETE']
    if incomplete:return {'status':'WITHHELD_FRAME','bounds':None,'linkage':links,'incomplete_frames':incomplete}
    if any(np.any(v['minimum']<0)for v in visibility):return {'status':'WITHHELD_FRAME','bounds':None,'linkage':links}
    linked={x['frame']for x in links if x['status']=='LINKED_IDENTICAL_MATCHING_INPUT'}if enable_links else set()
    representative=lambda side,t:(0,t)if t in linked else(side,t)
    pairs=[set(map(tuple,g.edges.tolist()))for g in graphs];edges=[tuple(map(int,e))for e in reference.edges];times=dict(zip(map(int,reference.ids),map(int,reference.coords[:,0])))
    bases=[{int(q):p for q,p in s['canonical_map'].items()}for s in summaries]
    # Extend the common canonical map through all linked frames, even if inactive.
    for t in linked:
        for q in frames[1][t]['reference_ids']:bases[1].pop(q,None)
        bases[1].update(frames[0][t]['canonical'])
    def world(v,index):return frames[v[0]][v[1]]['worlds'][index]
    def visible(side,i,choice):
        if visibility[side]['minimum'][i]==visibility[side]['maximum'][i]:return int(visibility[side]['minimum'][i])
        def node(q):
            key=representative(side,times[q]);return world(key,choice[key]).get(q)if key in choice else bases[side].get(q)
        a,b=edges[i];return int((node(a),node(b))in pairs[side])
    fixed={k:0 for k in METRICS};factors={}
    for i,(a,b)in enumerate(edges):
        uncertain=[v['minimum'][i]!=v['maximum'][i]for v in visibility]
        if not any(uncertain):
            for k,v in E.contrast_features(visibility[0]['minimum'][i],visibility[1]['minimum'][i]).items():fixed[k]+=v
            continue
        variables=set()
        for side in range(2):
            if not uncertain[side]:continue
            for q in[a,b]:
                t=times[q]
                if len({w.get(q)for w in frames[side][t]['worlds']})>1:variables.add(representative(side,t))
        assert variables;factors[i]=variables
    parent={v:v for group in factors.values()for v in group}
    def find(v):
        while parent[v]!=v:parent[v]=parent[parent[v]];v=parent[v]
        return v
    for group in factors.values():
        vv=sorted(group)
        for v in vv[1:]:parent[find(v)]=find(vv[0])
    groups=defaultdict(list)
    for v in parent:groups[find(v)].append(v)
    components=[]
    for vv in sorted(groups.values()):
        vv=sorted(vv);iset=[i for i,fs in factors.items()if fs&set(vv)];count=math.prod(len(frames[s][t]['worlds'])for s,t in vv)
        if count>cap:return {'status':'WITHHELD_COMPONENT_CAP','required':count,'cap':cap,'bounds':None,'linkage':links,'affected_reference_edge_indices':iset}
        lo=hi=None;lw={};hw={}
        for indexes in product(*(range(len(frames[s][t]['worlds']))for s,t in vv)):
            choice=dict(zip(vv,indexes));values={m:0 for m in METRICS}
            for i in iset:
                for m,v in E.contrast_features(visible(0,i,choice),visible(1,i,choice)).items():values[m]+=v
            if lo is None:lo=dict(values);hi=dict(values);lw={m:list(indexes)for m in METRICS};hw=dict(lw)
            else:
                for m,v in values.items():
                    if v<lo[m]:lo[m]=v;lw[m]=list(indexes)
                    if v>hi[m]:hi[m]=v;hw[m]=list(indexes)
        components.append({'variables':vv,'reference_edge_indices':iset,'configurations':count,'minimum':lo,'maximum':hi,'minimum_witness':lw,'maximum_witness':hw})
    bounds={m:{s:fixed[m]+sum(c[s][m]for c in components)for s in ['minimum','maximum']}for m in METRICS}
    lookup={(side,t):{signature(w):i for i,w in enumerate(f['worlds'])}for side in range(2)for t,f in frames[side].items()};witnesses={}
    for m in METRICS:
        for bound_side in ['minimum','maximum']:
            choice={tuple(v):i for c in components for v,i in zip(c['variables'],c[bound_side+'_witness'][m])};maps=[{},{}];selections=[]
            for side in range(2):
                for t,f in frames[side].items():
                    rep=representative(side,t);rf=frames[rep[0]][t];ix=choice.get(rep,rf['canonical_index']);w=world(rep,ix);original_index=lookup[(side,t)][signature(w)];maps[side].update(w)
                    if original_index!=f['canonical_index']or t in linked:selections.append([side,t,original_index])
            for t in linked:
                ids=frames[0][t]['reference_ids'];assert all(maps[0].get(q)==maps[1].get(q)for q in ids)
            # Replay all primitive relations, including those factored as constants.
            a=np.array([(maps[0].get(x),maps[0].get(y))in pairs[0]for x,y in edges],bool);b=np.array([(maps[1].get(x),maps[1].get(y))in pairs[1]for x,y in edges],bool)
            values={'before_TP':int(a.sum()),'after_TP':int(b.sum()),'gains':int((~a&b).sum()),'losses':int((a&~b).sum()),'net':int(b.sum())-int(a.sum())}
            assert values[m]==bounds[m][bound_side],(m,bound_side,values,bounds)
            witnesses[m+'_'+bound_side]={'frame_map_choices':selections,'values':values,'all_other_frames':'canonical full-family members'}
    return {'status':'COMPLETE','bounds':bounds,'linkage':links,'linked_frames':sorted(linked),'fixed_contributions':fixed,'components':components,'whole_map_endpoint_witnesses':witnesses,'simultaneous_extrema_vector_certified':False,'proof':'Equality merges identical matching-input frame variables. Disjoint components partition all nonconstant relation factors; each scalar endpoint extends to admissible full maps satisfying every declared equality.'}

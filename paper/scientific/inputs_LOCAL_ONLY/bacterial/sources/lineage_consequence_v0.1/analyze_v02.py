"""Retrospective downstream requirements on independently reconstructed identities."""
from pathlib import Path
import collections, datetime, hashlib, io, json, traceback, zipfile
import numpy as np

P=Path(__file__).resolve().parent;A=P.parent;R=A.parent
O=P/'results_v0.2';ARMS=('baseline','max_area','all_components')
def sha(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''):h.update(b)
    return h.hexdigest()
def load(p):return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def write(p,v):
    with p.open('x',encoding='utf-8') as f:json.dump(v,f,indent=2,allow_nan=False)
def require(b,m):
    if not b:raise ValueError(m)
def edge(r):
    t,i=divmod(r['reference_edge'][0],100000);u,j=divmod(r['reference_edge'][1],100000)
    require(t==0 and u==1 and type(r['current_frame']) is int and r['current_frame']>=1 and r['kind'] in ('division','continuation'),'Local-window reference identity/time/type')
    return r['current_frame']-1,i,r['current_frame'],j,int(r['kind']=='division')
def complete(es,visibility):return set(es)<=visibility
def compare(rows,arm):
    gained=[r['identity'] for r in rows if r['recovered'][arm] and not r['recovered']['baseline']]
    lost=[r['identity'] for r in rows if r['recovered']['baseline'] and not r['recovered'][arm]]
    return {'gains':gained,'losses':lost,'gain_count':len(gained),'loss_count':len(lost),
        'net':len(gained)-len(lost),'both_gain_loss':bool(gained and lost)}

def main():
    O.mkdir(exist_ok=False)
    cfg=load(A/'reproduction_LOCAL_ONLY_v0.1/external_full/RESOURCE_MANIFEST.json')
    zpath=Path(cfg['archive_path']);require(sha(zpath)==cfg['archive_sha256'],'Reference archive bytes')
    pins={str(zpath):sha(zpath),str(P/'PROTOCOL.md'):sha(P/'PROTOCOL.md'),str(Path(__file__)):sha(__file__)}
    films=[f'{i:02d}' for i in range(1,30)]
    for film in films:
        for p in [A/f'external_natural_support_actual_v0.1/{film}_edge_records.jsonl',
            A/f'external_full_integer_actual_v0.1/{film}_results.json']:
            pins[str(p)]=sha(p)
    write(O/'BEFORE_NEW_ENDPOINTS.json',{'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'input_sha256':pins,'retrospective_secondary_endpoints':True,'new_biological_N':0,
        'all29_included':True,'protocol_sha256':sha(P/'PROTOCOL.md')})
    all_events=[];all_cycles=[];all_exclusions=[];movie_rows=[];domains={}
    with zipfile.ZipFile(zpath) as z:
        for film in films:
            records=[json.loads(x) for x in (A/f'external_natural_support_actual_v0.1/{film}_edge_records.jsonl').read_text(encoding='utf-8').splitlines()]
            by={edge(r):r for r in records};require(len(by)==len(records),'Duplicate reference edge')
            name=f'CTC/test/{film}_GT/TRA/man_track.txt';content=z.read(name)
            rows=np.loadtxt(io.BytesIO(content),dtype=int,ndmin=2)
            tracks={int(i):(int(s),int(e),int(p)) for i,s,e,p in rows}
            require(len(tracks)==len(rows),'Duplicate reference lineage track')
            expected=set();children=collections.defaultdict(list)
            for i,(s,e,parent) in tracks.items():
                require(0<=s<=e and i>0,'Declared track interval')
                expected.update((t,i,t+1,i,0) for t in range(s,e))
                if parent:
                    require(parent in tracks and s>0 and tracks[parent][1]==s-1,'Unresolved parent boundary')
                    expected.add((s-1,parent,s,i,1));children[parent].append(i)
            require(expected==set(by),'Declared full interval/parent relation inventory mismatch '+film)
            require(all(not r['ambiguous_visibility'] and not r['ambiguous_correspondence'] for r in records),'Determinate typed bounds required')
            baseline={e for e,r in by.items() if r['visibility'][3]==1}
            untyped={e for e,r in by.items() if r['untyped_bounds'][3]==[True,True]}
            require(all(r['untyped_bounds'][3][0]==r['untyped_bounds'][3][1] for r in records),'Determinate untyped bounds required')
            require(baseline<=untyped,'Typed subset of raw-pair visibility')
            score=load(A/f'external_full_integer_actual_v0.1/{film}_results.json')
            visible={'baseline':baseline}
            for arm in ARMS[1:]:
                pair=next(r for r in score['paired'] if r['arm']==arm)
                gain={tuple(x) for x in pair['gain_edges']};loss={tuple(x) for x in pair['loss_edges']}
                require(gain<=expected-baseline and loss<=baseline and not gain&loss,'Paired identity membership')
                visible[arm]=(baseline-loss)|gain
            for arm in ARMS:
                row=next(r for r in score['rows'] if r['arm']==arm)
                require(len(visible[arm])==row['typed_TP'] and len(expected)==row['reference_edges'],'Independent scorer identity/count bridge')
            domains[film]={'reference_relations':len(expected),'reference_tracks':len(tracks),
                'typed_visible_counts':{a:len(v) for a,v in visible.items()},
                'untyped_baseline_visible':len(untyped),'reference_lineage_text_sha256':hashlib.sha256(content).hexdigest()}
            events=[];cycles=[];exclusions=[];event_by_mother={}
            for mother,kids in sorted(children.items()):
                start,end,parent=tracks[mother]
                if len(kids)!=2 or len({tracks[k][0] for k in kids})!=1:
                    exclusions.append({'film':film,'track':mother,'endpoint':'division_event','reason':'nonbinary_or_nonsynchronous_children','children':sorted(kids)})
                    continue
                ds=tracks[kids[0]][0];es=sorted((end,mother,ds,k,1) for k in kids)
                require(set(es)<=expected and ds==end+1,'Observed binary division')
                r={'film':film,'identity':[film,end,mother],'mother':mother,'daughters':sorted(kids),'frame':ds,
                    'required_edges':[list(e) for e in es],
                    'recovered':{a:complete(es,visible[a]) for a in ARMS},
                    'visible_daughters':{a:sum(e in visible[a] for e in es) for a in ARMS},
                    'untyped_baseline_recovered':complete(es,untyped)}
                events.append(r);event_by_mother[mother]=r
            for i,(s,e,parent) in sorted(tracks.items()):
                reasons=[]
                if not parent:reasons.append('no_observed_parent_birth_edge')
                if i not in event_by_mother:reasons.append('no_observed_complete_binary_outgoing_event')
                if reasons:
                    exclusions.append({'film':film,'track':i,'endpoint':'birth_to_division_chain','reasons':reasons,'start':s,'end':e,'parent':parent});continue
                incoming=(s-1,parent,s,i,1)
                cont={(t,i,t+1,i,0) for t in range(s,e)}
                outgoing={tuple(x) for x in event_by_mother[i]['required_edges']}
                es={incoming}|cont|outgoing;require(es<=expected,'Complete chain interval')
                r={'film':film,'identity':[film,i],'track':i,'start':s,'end':e,
                    'declared_frame_span':e-s+1,'required_edges':[list(x) for x in sorted(es)],
                    'continuation_edge_count':len(cont),'recovered':{a:complete(es,visible[a]) for a in ARMS},
                    'untyped_baseline_recovered':complete(es,untyped),
                    'failure_domains':{a:{'birth':incoming not in visible[a],
                        'continuation':len(cont-visible[a]),'outgoing_daughters':len(outgoing-visible[a])} for a in ARMS}}
                cycles.append(r)
            counts={'film':film,'reference_tracks':len(tracks),'division_events':len(events),
                'birth_to_division_chains':len(cycles),
                'event_recovered':{a:sum(r['recovered'][a] for r in events) for a in ARMS},
                'chain_recovered':{a:sum(r['recovered'][a] for r in cycles) for a in ARMS},
                'untyped_event_recovered':sum(r['untyped_baseline_recovered'] for r in events),
                'untyped_chain_recovered':sum(r['untyped_baseline_recovered'] for r in cycles),
                'event_contrasts':{a:compare(events,a) for a in ARMS[1:]},
                'chain_contrasts':{a:compare(cycles,a) for a in ARMS[1:]}}
            write(O/(film+'_RECORDS.json'),{'division_events':events,'birth_to_division_chains':cycles,
                'excluded_reference_tracks':exclusions,'counts':counts,'reference_domain':domains[film]})
            all_events.extend(events);all_cycles.extend(cycles);all_exclusions.extend(exclusions);movie_rows.append(counts)
            print('LINEAGE_CONSEQUENCE',film,len(events),len(cycles),counts['event_recovered'],counts['chain_recovered'],flush=True)
    def pooled(rows):
        return {'denominator':len(rows),'recovered':{a:sum(r['recovered'][a] for r in rows) for a in ARMS},
            'untyped_baseline_recovered':sum(r['untyped_baseline_recovered'] for r in rows),
            'untyped_complete_but_typed_incomplete_baseline':[r['identity'] for r in rows if r['untyped_baseline_recovered'] and not r['recovered']['baseline']],
            'contrasts':{a:compare(rows,a) for a in ARMS[1:]}}
    result={'UTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'status':'ACTUAL_ALL29_RETROSPECTIVE_LINEAGE_CONSEQUENCE_COMPLETE',
        'division_events':pooled(all_events),'birth_to_division_chains':pooled(all_cycles),
        'movies':movie_rows,'reference_domains':domains,'exclusions':len(all_exclusions),
        'new_biological_N':0,'SF_M1':'MAJOR_OPEN_PENDING_VALUE_ASSESSMENT',
        'scope':'Secondary exact-reference typed requirements from already independently reconstructed identities; not official BC/CT/CCA, new metric, estimated cycle distribution, population inference, intervention selection benefit or framework superiority.'}
    write(O/'RESULT.json',result)
    print(json.dumps({'status':result['status'],'events':{k:v for k,v in result['division_events'].items() if k not in ['contrasts','untyped_complete_but_typed_incomplete_baseline']},'chains':{k:v for k,v in result['birth_to_division_chains'].items() if k not in ['contrasts','untyped_complete_but_typed_incomplete_baseline']}}))

if __name__=='__main__':
    try:main()
    except BaseException:
        if O.exists():write(O/'FAILED.json',{'status':'WITHHELD','traceback':traceback.format_exc()})
        raise

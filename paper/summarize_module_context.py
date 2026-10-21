"""Reaggregate the retained deletion and cumulative-addition experiment."""
import argparse,csv,json
from pathlib import Path
from collections import defaultdict

ORDER=['motion_relink','single_parent','gap','gap2','safe_div','div_filter','prune','short_track','linefit','v72','v74']

def run(source,output):
    rows=list(csv.DictReader(Path(source).open(encoding='utf-8-sig')))
    films=sorted({r['dataset'] for r in rows}); by={(r['dataset'],r['variant']):r for r in rows}
    if len(by)!=len(rows):raise ValueError('Duplicate movie-condition identity')
    enabled=[];same_counts=[]
    for film in films:
        full=by[film,'full'];previous=by[film,'raw']
        for index,module in enumerate(ORDER):
            deletion=by[film,'no_'+module]
            addition=by[film,'fwd_'+'+'.join(ORDER[:index+1])]
            for context,before,after in [('full_background',deletion,full),('cumulative_sequence',previous,addition)]:
                enabled.append({'movie':film,'module':module,'context':context,'before':before['variant'],'after':after['variant'],**{f'delta_{k}':int(after[k])-int(before[k]) for k in ['edge_tp','edge_fp','n_nodes','n_edges']}})
            previous=addition
        for r in [x for x in rows if x['dataset']==film and x['variant'] not in ['raw','full']]:
            if all(r[k]==full[k] for k in ['edge_tp','edge_fp']) and any(r[k]!=full[k] for k in ['n_nodes','n_edges']):
                same_counts.append({'movie':film,'variant':r['variant'],'TP':int(r['edge_tp']),'FP':int(r['edge_fp']),'nodes':int(r['n_nodes']),'edges':int(r['n_edges']),'full_nodes':int(full['n_nodes']),'full_edges':int(full['n_edges'])})
    pooled=[]
    for module in ORDER:
        for context in ['full_background','cumulative_sequence']:
            subset=[r for r in enabled if r['module']==module and r['context']==context]
            pooled.append({'module':module,'context':context,**{k:sum(r[k] for r in subset) for k in ['delta_edge_tp','delta_edge_fp','delta_n_nodes','delta_n_edges']}})
    result={'input_rows':len(rows),'movies':films,'conditions_per_movie':[sum(r['dataset']==f for r in rows) for f in films],'enabled_direction':'full minus deletion; cumulative step minus preceding step','pooled':pooled,'per_movie':enabled,'same_TP_FP_different_node_or_edge_count':same_counts,'nonbaseline_denominator':len(rows)-2*len(films),'scope':'Historical conditional counts; differing graph size proves differing structure, not which relation identity changed. This is not a replay of the old producer.'}
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2),encoding='utf8')
    print('same counts / different size',len(same_counts),'/',result['nonbaseline_denominator'])
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--input',required=True);p.add_argument('--output',required=True);a=p.parse_args();run(a.input,a.output)

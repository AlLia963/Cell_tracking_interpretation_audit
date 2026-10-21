"""Write metadata sidecars; producer files, counts and negatives remain untouched."""
from pathlib import Path
import argparse, hashlib, json

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--records',required=True,type=Path);ap.add_argument('--output',required=True,type=Path);a=ap.parse_args()
    files=[];total=0
    for p in sorted(a.records.rglob('*')):
        if not p.is_file() or p.suffix not in {'.json','.jsonl'}:continue
        try:
            if p.suffix=='.jsonl':objects=[json.loads(x) for x in p.read_text(encoding='utf-8-sig').splitlines() if x.strip()]
            else:objects=[json.loads(p.read_text(encoding='utf-8-sig'))]
        except (ValueError,UnicodeError):continue
        entries=[]
        def walk(obj,location='$'):
            if isinstance(obj,dict):
                # Historical structural names occur in both paths and forks.
                path_scope=obj.get('kind')=='three_node_path' or ':three_node_path:' in str(obj.get('query_id','')) or 'path_records' in location or any(k.startswith('path_') and 'structural' in k for k in obj)
                for key,value in obj.items():
                    here=location+'.'+key
                    if (('structural_consistency' in key or (key.startswith('path_') and 'structural' in key)) and (path_scope or key.startswith('path_'))) or (path_scope and key=='readout' and value=='structural_consistency'):
                        entries.append({'json_location':here,'legacy_field_name':key,
                            'query_name':'selected_path_exclusivity','original_value_retained':True})
                    walk(value,here)
            elif isinstance(obj,list):
                for i,x in enumerate(obj):walk(x,location+'['+str(i)+']')
        for i,obj in enumerate(objects):walk(obj,'$' if p.suffix=='.json' else 'line['+str(i+1)+']')
        if entries:
            with p.open('rb')as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
            total+=len(entries);files.append({'record':p.relative_to(a.records).as_posix(),'sha256':digest,'metadata':entries})
    with a.output.open('x',encoding='utf-8')as f:json.dump({'query_name':'selected_path_exclusivity',
        'predicate':'out(a)={b}; out(b)={c}; in(b)={a}; in(c)={b}',
        'not_checked':['in(a)','out(c)'],'scope':'selected three-node path exclusivity; no biological error label',
        'sidecar_only':True,'original_counts_histories_categories_and_negative_results_preserved':True,
        'original_record_files_unchanged':True,'annotation_count':total,'files':files},f,ensure_ascii=False,indent=2)
    print(json.dumps({'annotated_field_instances':total,'source_files':len(files),'query_name':'selected_path_exclusivity'}))

if __name__=='__main__':main()

from pathlib import Path
import csv, hashlib, json, re, subprocess, sys
import pymupdf
from PIL import Image, ImageDraw

R=Path(__file__).resolve().parents[1];S=R/'03_新稿';C=R/'02_采用与成本补证';Q=R/'04_构建与核验'
sha=lambda p:hashlib.sha256(Path(p).read_bytes()).hexdigest()
repo=Path(r'G:\kaggle论文化\论文工作区\GitHub发布\2026-10-07\stage-resolved-tracking-audit')
contract=json.loads((repo/'outputs/paper_20261010/analyst-path/measurement/INPUT_AND_QUERY_CONTRACT.json').read_text(encoding='utf8'))
argv=[r'C:\Users\24408\AppData\Local\Programs\Python\Python313\python.exe',str(repo/'paper/scientific/extras/analyst/audit_path_statement.py'),'--reference',contract['reference']['path'],'--prediction',contract['prediction']['path'],'--unit','pixel','--gate-um','7','--path',*map(str,contract['reference_path']),'--proposed-value','1','--query-cap','1','--output',str(C/'actual_frontend_query_cap_one')]
cap_record=json.loads((C/'ACTUAL_FRONTEND_CAP_RUN.json').read_text(encoding='utf8'))
report=json.loads((C/'actual_frontend_query_cap_one/REPORT.json').read_text(encoding='utf8'))
assert cap_record['returncode']==0 and report['status']=='WITHHELD_QUERY_CAP' and report['joint_configurations']==2
assert sha(C/'actual_frontend_query_cap_one/REPORT.json')==cap_record['report_sha256']

m=(S/'manuscript_v1.1.md').read_text(encoding='utf8');s=(S/'supplement_v1.1.md').read_text(encoding='utf8');d=(S/'SourceData_v1.1.md').read_text(encoding='utf8')
assert list(map(int,re.findall(r'^## D(\d+)(?:\.|\s|$)',d,re.M)))==list(range(1,51))
refs=list(map(int,re.findall(r'^(\d+)\. ',m.split('## References')[1],re.M)));assert refs==list(range(1,28))
for t in (m,s):
    assert '{{' not in t and '}}' not in t
    assert 'REVIEW VERDICT: Accept' not in t
for val in ('2.36 ms','15.10 ms','1.17 ms','0.038 ms','0.040 ms','88.17–88.45 MiB','86.39–86.55 MiB'):assert val in m,val
for val in ('71 determinate','135 determinate','three ambiguous','1,522/1,522/1,520','760/771/2,052/2,048','29,362/1,731/2,004','29,359/1,734/2,012'):assert val in m,val
pins=json.loads((R/'01_意见证据核对/SOURCE_PINS.json').read_text(encoding='utf8'))
for p in pins['source_records']:assert sha(p['path'])==p['sha256'],p['path']

# Preserve the old map; add only the three new data entries in the new directory.
with (repo/'docs/ARTICLE_PROGRAM_MAP.csv').open(encoding='utf-8-sig',newline='') as f:reader=csv.DictReader(f);fields=reader.fieldnames;rows=list(reader)
for ident,title,location,outputs,scope in [('D48','Actual D47 instrumented costs','Methods2.6;Results3.1;SI S7.6;TableS11','COST_AND_ADOPTION_SUMMARY.json;component_cost_v02/STRONG_COMPONENT_BASELINE_COST.json','3 fresh-process timing repeats per implementation; not biological N'),('D49','Completeness responsibility probes','Methods2.2;SI S1.6;TableS10','run_01..03/RESULT.json;actual_frontend_query_cap_one/REPORT.json','Actual saved-graph omission plus replay-index and actual frontend cap check'),('D50','Same-task adoption decisions','Results3.1;Discussion','SourceData_v1.1.md D50','Joins existing D04/D08/D43/D47 and new D48/D49; no new cohort')]:
    row={k:'' for k in fields};row.update(source_data=ident,title=title,article_location=location,route='v1.1-local-extension',programs='02_采用与成本补证/measure_adoption_cost.py;measure_component_baseline_v02.py;04_构建与核验/final_checks.py',inputs='Existing D47 NPZ and source; frozen protocol; original D01–D47 records',outputs=outputs,unit=scope,kind='Instrumentation / evidence integration',limitation='No accuracy, general speed or human-effort superiority claim; absolute local paths explicit',local_execution='Completed and compared; old cohort not rerun');rows.append(row)
with (S/'ARTICLE_PROGRAM_MAP_v1.1.csv').open('x',encoding='utf-8-sig',newline='') as f:w=csv.DictWriter(f,fields);w.writeheader();w.writerows(rows)

metadata=json.loads((S/'Word/native_render/NATIVE_RENDER.json').read_text(encoding='utf-8-sig'))
native_splits=[]
for doc in metadata['documents']:
    for ti,table in enumerate(doc['native_tables']):
        for ri,row in enumerate(table['row_pages']):
            if row['start_page']!=row['end_page']:native_splits.append((doc['name'],ti,ri,row['start_page'],row['end_page']))
assert not native_splits,native_splits
QA=Q/'page_QC';QA.mkdir(exist_ok=False);results=[]
for di,doc in enumerate(metadata['documents']):
    pdf=pymupdf.open(doc['pdf']);pages=[];renderdir=QA/f'document_{di+1}';renderdir.mkdir()
    violations=[]
    for i,page in enumerate(pdf):
        text=page.get_text();assert len(text.strip())>25,(di,i,'near-empty')
        for block in page.get_text('dict')['blocks']:
            for line in block.get('lines',[]):
                for span in line['spans']:
                    x0,y0,x1,y1=span['bbox']
                    if x0<-.5 or y0<-.5 or x1>page.rect.width+.5 or y1>page.rect.height+.5:violations.append({'page':i+1,'text':span['text'],'bbox':span['bbox']})
                    assert '\ufffd' not in span['text'],(i,span['text'])
        png=renderdir/f'page-{i+1:02}.png';page.get_pixmap(matrix=pymupdf.Matrix(1.65,1.65),alpha=False).save(png);pages.append(png)
    contacts=[]
    for offset in range(0,len(pages),4):
        ims=[Image.open(p).convert('RGB') for p in pages[offset:offset+4]];w=max(im.width for im in ims);h=max(im.height for im in ims)
        canvas=Image.new('RGB',(2*w,2*(h+28)),(222,222,222));draw=ImageDraw.Draw(canvas)
        for j,im in enumerate(ims):
            x=(j%2)*w;y=(j//2)*(h+28);draw.text((x+10,y+5),f'Document {di+1} page {offset+j+1}',fill='black');canvas.paste(im,(x,y+28))
        p=QA/f'document_{di+1}_pages_{offset+1:02}-{min(offset+4,len(pages)):02}.png';canvas.save(p);contacts.append(str(p))
    assert not violations,violations
    results.append({'document':doc['name'],'pages':len(pdf),'native_row_splits':0,'outside_page_text_spans':violations,'contacts':contacts,'visual_inspection_pending':True})
with (Q/'TEXT_NUMERIC_AND_LAYOUT_CHECKS.json').open('x',encoding='utf8') as f:json.dump({'source_data_continuous_D01_D50':True,'references_continuous_1_27':True,'selected_preserved_and_new_numeric_claims_checked':True,'old_sources_current_hashes_match':True,'actual_frontend_cap_withhold':True,'documents':results,'not_a_fresh_independent_manuscript_review':True},f,ensure_ascii=False,indent=2)
print(json.dumps(results,ensure_ascii=False))

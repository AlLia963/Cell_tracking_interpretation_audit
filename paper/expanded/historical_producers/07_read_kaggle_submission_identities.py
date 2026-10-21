"""Read the author's existing competition submissions; never create jobs/submissions."""
from pathlib import Path
import os,json,datetime
R=Path('D:/1013工作大修');O=R/'01_输入清册'
os.environ['KAGGLE_CONFIG_DIR']='C:/Users/24408/Downloads'
from kaggle.api.kaggle_api_extended import KaggleApi
from kagglesdk.competitions.types.competition_api_service import ApiListSubmissionsRequest
api=KaggleApi();api.authenticate();rows=[];seen=set();pages=[]
def clean(x):
    if x is None or isinstance(x,(str,int,float,bool)):return x
    if isinstance(x,(datetime.datetime,datetime.date)):return x.isoformat()
    if isinstance(x,list):return [clean(y)for y in x]
    if isinstance(x,dict):return {k:clean(v)for k,v in x.items()}
    if hasattr(x,'to_dict'):return clean(x.to_dict())
    if hasattr(x,'__dict__'):return {k:clean(v)for k,v in vars(x).items()if not k.startswith('_')}
    return str(x)
try:
    token=''
    for page in range(1,11):
        with api.build_kaggle_client()as client:
            request=ApiListSubmissionsRequest();request.competition_name='biohub-cell-tracking-during-development';request.page_size=100;request.page_token=token
            response=client.competitions.competition_api_client.list_submissions(request)
            result=response.submissions;next_token=response.next_page_token
        data=[clean(x)for x in result or []];pages.append({'page':page,'records':len(data)})
        if not data:break
        fresh=0
        for row in data:
            key=json.dumps(row,sort_keys=True)
            if key not in seen:seen.add(key);rows.append(row);fresh+=1
        (O/'KAGGLE_SUBMISSIONS_READONLY.json').write_text(json.dumps({'records':rows,'pages':pages,'status':'IN_PROGRESS'},ensure_ascii=False,indent=2),encoding='utf8')
        print('READ_ONLY_SUBMISSION_PAGE',page,len(data),'new',fresh,flush=True)
        if not fresh or not next_token:break
        token=next_token
    out={'status':'COMPLETED_READ_ONLY','records':rows,'pages':pages,'record_count':len(rows),'no_jobs_or_submissions_created':True,'source':'Authenticated existing competition submission list; account coverage only'}
except Exception as e:
    out={'status':'READ_FAILED_OR_PARTIAL','error_type':type(e).__name__,'records':rows,'pages':pages,'record_count':len(rows),'no_jobs_or_submissions_created':True,'error_details_suppressed_to_avoid_tokens_or_signed_urls':True}
(O/'KAGGLE_SUBMISSIONS_READONLY.json').write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'status':out['status'],'records':len(rows),'keys':list(rows[0])if rows else[]},ensure_ascii=False))

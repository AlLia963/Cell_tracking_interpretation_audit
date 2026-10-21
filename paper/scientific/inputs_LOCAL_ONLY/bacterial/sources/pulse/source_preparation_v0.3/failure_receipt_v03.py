"""Durable fail-stop receipts, including preflight; no inference or GT imports."""
import hashlib,json,traceback
from pathlib import Path
def persist_failure(out,video,predictor,error):
    out=Path(out);folder=out/'native'/video
    histories=getattr(predictor,'_pulse_history',[]) if predictor is not None else []
    inventory=folder/'direct_trace/inventory.json'
    last=json.loads(inventory.read_text(encoding='utf-8')) if inventory.exists() else []
    partial={str(f.relative_to(folder)):hashlib.sha256(f.read_bytes()).hexdigest() for f in folder.rglob('*') if f.is_file()} if folder.exists() else {}
    receipt={'traceback':error,'pulse_history':histories,'last_successful_capture':last[-1] if last else None,'last_completed_model_output_record':next((r for r in reversed(last) if r.get('kind')=='raw_model_output'),None),'model_output_completion_scope':'Only written raw output capture record; not consumer/model/film completion inferred from finally' ,'direct_inventory':last,'partial_file_hashes':partial,'fail_stop':True}
    payload=json.dumps(receipt,indent=2)
    (out/(video+'_failure_receipt.json')).write_text(payload,encoding='utf-8')
    (out/(video+'_pulse_history.json')).write_text(json.dumps(histories,indent=2),encoding='utf-8')
    return receipt
def run_durable(destination,intended,body,binding=None):
    out=Path(destination);out.parent.mkdir(exist_ok=True);out.mkdir(exist_ok=False)
    initial={'status':'pending','intended_videos':intended,'execution_binding':binding,'all_video_reports':[{'video':v,'status':'pending'} for v in intended]}
    (out/'manifest.json').write_text(json.dumps(initial,indent=2),encoding='utf-8')
    try:return body()
    except BaseException:
        error=traceback.format_exc();reports=[]
        for v in intended:
            path=out/(v+'_execution_report.json')
            reports.append(json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'video':v,'status':'not-executed-after-fail-stop'})
        partial={str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest() for f in out.rglob('*') if f.is_file() and f.name not in ('manifest.json','top_level_failure.json')}
        failure={'status':'failed-or-partial-fail-stop','traceback':error,'intended_videos':intended,'execution_binding':binding,'all_video_reports':reports,'partial_hashes':partial}
        payload=json.dumps(failure,indent=2)
        (out/'top_level_failure.json').write_text(payload,encoding='utf-8')
        (out/'manifest.json').write_text(payload,encoding='utf-8')
        raise

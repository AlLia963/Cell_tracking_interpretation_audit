import sys
sys.dont_write_bytecode = True
import ast, hashlib, importlib.util, json, traceback
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'S3_allocation_trace_v0.1'
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()

def main():
    OUT.mkdir(exist_ok=False)
    spec = importlib.util.spec_from_file_location('sensitivity', ROOT / 'real_S3_policy_sensitivity_v0.1' / 'run_sensitivity.py')
    module = importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    ns, env = module.producer_namespace()
    function = next(n for n in ast.parse(module.SOURCE.read_text(encoding='utf-8-sig')).body if isinstance(n, ast.FunctionDef) and n.name == 'add_safe_divisions_postlink')
    class Observer(ast.NodeTransformer):
        hits = 0
        def visit_Expr(self, node):
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Attribute) and ast.unparse(node.value.func) == 'proposals.append':
                self.hits += 1
                extra = ast.parse("_TRACE.append(dict(frame=int(t), score=float(score), source=int(source_id), target=int(candidate_id), parent_distance=float(parent_dist), sister_distance=float(sister_dist), frame_cap=int(frame_cap), global_cap=int(global_cap)))").body[0]
                return [node, extra]
            return self.generic_visit(node)
    observer = Observer(); function = observer.visit(function); assert observer.hits == 1
    ast.fix_missing_locations(function)
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(module.SOURCE), 'exec'), ns)
    ns['deepcenter_accept_repair_point'] = lambda *args: True
    rows = []; hashes = {}
    for film in sorted(p for p in module.GRAPHS.iterdir() if p.is_dir()):
        paths = [film / 'S2_gap_closing.npz', film / 'S3_safe_divisions.npz']
        nodes, edges = module.load_graph(paths[0]); nodes3, edges3 = module.load_graph(paths[1]); assert nodes == nodes3
        hashes.update({str(p):digest(p) for p in paths})
        old = {(e['source_id'],e['target_id']) for e in edges}
        actual = {(e['source_id'],e['target_id']) for e in edges3} - old
        ns['_TRACE'] = []
        result = ns['add_safe_divisions_postlink'](nodes, edges, defaultdict(int), dataset=film.name)
        winners = {(e['source_id'], e['target_id']) for e in result} - old
        trace = ns['_TRACE']; by_frame = defaultdict(list)
        for p in trace: by_frame[p['frame']].append(p)
        selected = set(); used_source = set(); used_target = set(); allocation = []
        for frame in sorted(by_frame):
            count = 0
            for p in sorted(by_frame[frame], key=lambda x:x['score']):
                pair = (p['source'],p['target'])
                if len(selected) >= p['global_cap']: reason = 'global_cap'
                elif count >= p['frame_cap']: reason = 'frame_cap'
                elif p['target'] in used_target: reason = 'target_used'
                elif p['source'] in used_source: reason = 'source_used'
                else:
                    reason = 'accepted'; selected.add(pair); used_source.add(p['source']); used_target.add(p['target']); count += 1
                allocation.append({**p,'allocation':reason,'historical_addition':pair in actual})
        assert selected == winners, (film.name, selected ^ winners)
        domain = {(p['source'],p['target']) for p in trace}
        absent = actual - winners
        displaced = [p for p in allocation if (p['source'],p['target']) in absent]
        rows.append(dict(film=film.name,historical_added=len(actual),accept_all_added=len(winners),proposal_count=len(trace),historical_outside_proposal_domain=sorted(actual-domain),historical_absent_accept_all=sorted(absent),displaced=displaced,allocation=allocation))
        print(film.name, 'outside_domain',len(actual-domain),'displaced',len(displaced),flush=True)
    payload = dict(rows=rows,source_sha256=digest(module.SOURCE),instrumented_script_sha256=digest(Path(__file__)),protocol_sha256=digest(ROOT/'S3_allocation_trace_protocol_v0.1.md'),input_hashes=hashes,scope='Accept-all graph allocation audit; historical image veto is not reconstructed')
    (OUT/'report.json').write_text(json.dumps(payload,indent=2),encoding='utf-8')

if __name__ == '__main__':
    try: main()
    except Exception:
        if OUT.exists(): (OUT/'failure.json').write_text(json.dumps({'traceback':traceback.format_exc()}),encoding='utf-8')
        raise

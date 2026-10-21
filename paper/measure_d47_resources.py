"""Explicit-root adapter for the retained v1.1 D47 timing snapshots.

Historical timing values are not regression targets. The old probe fields in
these snapshots are weaker than v1.2's actual API probes; see probe_contracts.py.
"""
from pathlib import Path
import argparse, importlib.util, json, shutil, statistics, subprocess, sys

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--task',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--child',type=int);p.add_argument('--route',choices=('framework','component'))
    a=p.parse_args();root=Path(__file__).resolve().parents[1];out=a.output.resolve()
    snapshots=root/'paper/resources_v1_1'
    if a.child:
        spec=importlib.util.spec_from_file_location('measure_adoption_cost',snapshots/'measure_adoption_cost.py')
        module=importlib.util.module_from_spec(spec);sys.modules['measure_adoption_cost']=module;spec.loader.exec_module(module)
        module.HERE=out;module.REPO=root;module.OLD=a.task.resolve()
        module.SOURCE=root/'paper/scientific/extras/analyst/constructor/reconstruct.py'
        module.FACTOR=root/'paper/scientific/extensions/operating_envelope/factor_frames.py'
        if a.route=='framework':module.child(a.child)
        else:
            spec=importlib.util.spec_from_file_location('component_cost_snapshot',snapshots/'measure_component_baseline_v02.py')
            component=importlib.util.module_from_spec(spec);spec.loader.exec_module(component)
            component.OUT=out/'component_cost_v02';component.OUT.mkdir(exist_ok=True)
            component.P=root/'paper/scientific/extensions/natural/literal_constrained_baseline_v03.py'
            component.run(a.child)
        return
    out.mkdir(parents=True,exist_ok=False);shutil.copy2(snapshots/'PROTOCOL.md',out/'PROTOCOL.md')
    for route in ('framework','component'):
        for repeat in (1,2,3):
            command=[sys.executable,'-X','utf8',str(Path(__file__).resolve()),'--task',str(a.task.resolve()),'--output',str(out),'--child',str(repeat),'--route',route]
            proc=subprocess.run(command,capture_output=True,text=True,encoding='utf8')
            with (out/f'PROCESS_{route}_{repeat}.json').open('x',encoding='utf8') as f:json.dump({'command':command,'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr},f,indent=2)
            if proc.returncode:raise RuntimeError(proc.stderr)
    framework=[json.loads((out/f'run_{i:02}/RESULT.json').read_text(encoding='utf8')) for i in (1,2,3)]
    component=[json.loads((out/f'component_cost_v02/component_run_{i:02}/RESULT_BEFORE_COMPARISON.json').read_text(encoding='utf8')) for i in (1,2,3)]
    result={'framework_phase_median_ms':{k:statistics.median(x['phases'][k]['wall_seconds'] for x in framework)*1000 for k in framework[0]['phases']},'component_median_ms':{k.removesuffix('_seconds'):statistics.median(x[k] for x in component)*1000 for k in ('construction_three_frames_seconds','query_seconds','whole_film_pair_index_seconds')},'legacy_probe_fields_not_actual_API_evidence':True,'actual_interface_probe_command':'paper/probe_contracts.py','not_expected_to_equal_historical_timings':True}
    with (out/'SUMMARY.json').open('x',encoding='utf8') as f:json.dump(result,f,indent=2)
if __name__=='__main__':main()

"""Run a unified LOCAL ONLY source package and compare complete known results.

This orchestration is a new local reproduction wrapper, not new scientific N,
independent blind validation, a software licence or a public deposit.
"""
from pathlib import Path
import argparse
import collections
import datetime
import hashlib
import importlib.metadata
import importlib.util
import itertools
import json
import os
import platform
import subprocess
import sys
import time
import traceback

HERE = Path(__file__).resolve().parent


def utc():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def pin(path):
    with path.open('rb') as f:
        digest = hashlib.file_digest(f, 'sha256').hexdigest()
    return {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest}


def save(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(obj, f, ensure_ascii=False, indent=2); f.write('\n')


def read(path):
    return json.loads(path.read_text(encoding='utf-8-sig'))


def module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def diff(left, right, path='$', found=None):
    """Full recursive comparison; every differing field is retained."""
    found = [] if found is None else found
    if type(left) is not type(right):
        found.append({'path': path, 'reason': 'type', 'expected': type(left).__name__, 'actual': type(right).__name__})
    elif isinstance(left, dict):
        for key in sorted(set(left) | set(right)):
            if key not in left or key not in right:
                found.append({'path': path + '.' + key, 'reason': 'key', 'in_expected': key in left, 'in_actual': key in right})
            else:
                diff(left[key], right[key], path + '.' + key, found)
    elif isinstance(left, list):
        if len(left) != len(right):
            found.append({'path': path, 'reason': 'length', 'expected': len(left), 'actual': len(right)})
        for index, (a, b) in enumerate(zip(left, right)):
            diff(a, b, path + '[' + str(index) + ']', found)
    elif left != right:
        found.append({'path': path, 'reason': 'value', 'expected': left, 'actual': right})
    return found


def typed_science(result):
    # Exact, top-level provenance exclusions; no science fields are removed.
    return {k: v for k, v in result.items() if k not in {'input_path', 'time_seconds'}}


def typed_categories(result, data, core):
    if result['status'] != 'COMPLETE_CONSTRUCTED_TYPED_BINARY_REPORT':
        return {'status': result['status'], 'readout': None}
    mother = data['focal_mother']
    children = sorted(e['target'] for e in data['reference_edges']
                      if e['source'] == mother and e['type'] == 'division_daughter')
    query = [mother] + children
    rows = []
    for index, report in enumerate(result['whole_map_reports']):
        values = []
        for mapping, stage in zip(report['stage_maps'], data['stages']):
            outgoing = collections.defaultdict(set); incoming = collections.defaultdict(set)
            for edge in stage['edges']:
                outgoing[edge['source']].add(edge['target']); incoming[edge['target']].add(edge['source'])
            values.append(core.local_graph_query_value('binary_fork',
                          [mapping[str(q)] for q in query], outgoing, incoming))
        r = ''.join(str(v[0]) for v in values)
        c = ''.join(str(v[1]) for v in values)
        features = report['features']
        event = ''.join(str(features['complete_binary_event_' + str(s)]) for s in range(2))
        context = ''.join(str(features['incoming_and_complete_event_' + str(s)]) for s in range(2))
        rows.append({'whole_map_witness_index': index, 'stage_maps': report['stage_maps'],
                     'raw_relation_histories': report['raw_histories'],
                     'typed_relation_histories': report['typed_histories'],
                     'raw_relation_categories': [core.final_category(h) for h in report['raw_histories']],
                     'typed_relation_categories': [core.final_category(h) for h in report['typed_histories']],
                     'fork_pair_recovery_history': r, 'fork_structural_consistency_history': c,
                     'fork_pair_recovery_category': core.final_category(r),
                     'fork_structural_consistency_category': core.final_category(c),
                     'complete_binary_event_history': event, 'complete_binary_event_category': core.final_category(event),
                     'incoming_and_complete_event_history': context,
                     'incoming_and_complete_event_category': core.final_category(context),
                     'attainable_scalar_vector': features})
    interior = {}
    for name, scalar in result['separate_scalar_reports'].items():
        allowed = scalar['values']
        interior[name] = {'minimum': scalar['minimum'], 'maximum': scalar['maximum'],
                         'exact_attainable_values': allowed,
                         'attainable_interior_values': [v for v in allowed if scalar['minimum'] < v < scalar['maximum']],
                         'integer_interior_values_without_a_whole_map_witness': [v for v in range(scalar['minimum'] + 1, scalar['maximum']) if v not in allowed],
                         'minimum_witness': rows[scalar['minimum_witness_index']],
                         'maximum_witness': rows[scalar['maximum_witness_index']]}
    return {'status': 'COMPLETE_DERIVED_CATEGORIES_AND_INTERIOR_FEASIBILITY',
            'convention': result['convention'], 'complete_whole_map_rows': rows,
            'scalar_feasibility': interior,
            'full_vectors_are_exactly_the_saved_whole_map_rows': True,
            'scalar_endpoint_vector_or_interval_is_not_an_existence_certificate': True,
            'scope': 'Derived from literal constructed maps and the unchanged local core; types supplied by input; no new biology or blind validation.'}


def predicate_cases(core):
    tests = []
    cases = [
        ('path_four_set_exclusive', [(1, 2), (2, 3)], 'three_node_path', [1, 2, 3], [1, 1]),
        ('path_first_incoming_allowed', [(0, 1), (1, 2), (2, 3)], 'three_node_path', [1, 2, 3], [1, 1]),
        ('path_last_outgoing_allowed', [(1, 2), (2, 3), (3, 4)], 'three_node_path', [1, 2, 3], [1, 1]),
        ('path_legal_sister_branch_breaks_exclusivity', [(1, 2), (1, 9), (2, 3)], 'three_node_path', [1, 2, 3], [1, 0]),
        ('same_legal_sister_branch_is_complete_fork', [(1, 2), (1, 9), (2, 3)], 'binary_fork', [1, 2, 9], [1, 1]),
        ('path_middle_outgoing_extra', [(1, 2), (2, 3), (2, 9)], 'three_node_path', [1, 2, 3], [1, 0]),
        ('path_middle_incoming_extra', [(1, 2), (8, 2), (2, 3)], 'three_node_path', [1, 2, 3], [1, 0]),
        ('path_last_incoming_extra', [(1, 2), (2, 3), (8, 3)], 'three_node_path', [1, 2, 3], [1, 0]),
        ('path_missing_pair', [(1, 2)], 'three_node_path', [1, 2, 3], [0, 0]),
        ('path_unmatched_middle', [(1, 2), (2, 3)], 'three_node_path', [1, None, 3], [0, 0]),
    ]
    for name, edges, kind, nodes, expected in cases:
        outgoing = collections.defaultdict(set); incoming = collections.defaultdict(set)
        for a, b in edges:
            outgoing[a].add(b); incoming[b].add(a)
        actual = core.local_graph_query_value(kind, nodes, outgoing, incoming)
        assert list(actual[:2]) == expected, (name, actual, expected)
        tests.append({'case': name, 'edges': edges, 'kind': kind, 'mapped_nodes': nodes,
                      'actual_pair_recovery': actual[0], 'actual_structural_consistency': actual[1],
                      'incident_edge_bits': actual[2], 'expected_pair_and_structural': expected, 'pass': True})
    return {'cases': tests, 'all_pass': True,
            'path_c_checks': ['out(a)={b}', 'out(b)={c}', 'in(b)={a}', 'in(c)={b}'],
            'path_c_does_not_check': ['in(a)', 'out(c)'],
            'interpretation': 'A legitimate sister branch can have pair recovery 1 and path exclusivity c=0. This is not a claim of biological error.'}


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--archive', required=True, type=Path)
    ap.add_argument('--output', required=True, type=Path)
    args = ap.parse_args(); out = args.output.resolve(); archive = args.archive.resolve()
    if out.exists(): raise FileExistsError('Absent output required: ' + str(out))
    out.mkdir(parents=True)
    start = time.monotonic(); calls = []
    env = os.environ.copy()
    for key in ['PYTHONPATH', 'PYTHONHOME']:
        env.pop(key, None)
    env['PYTHONNOUSERSITE'] = '1'; env['PYTHONDONTWRITEBYTECODE'] = '1'; env['PYTHONUTF8'] = '1'
    packages = ['numpy', 'scipy', 'scikit-image', 'tifffile', 'imagecodecs', 'psutil', 'opencv-python-headless']
    dependencies = {'python': sys.version, 'executable': sys.executable, 'platform': platform.platform(),
                    'packages': {name: importlib.metadata.version(name) for name in packages},
                    'same_host_existing_interpreter': True, 'clean_machine_claim': False,
                    'external_dependency_distributions_not_bundled': True}
    save(out/'DEPENDENCIES_ACTUAL.json', dependencies)
    save(out/'RUN_START.json', {'utc': utc(), 'argv': sys.argv, 'cwd': str(Path.cwd()),
                              'archive': pin(archive), 'prior_results_known': True, 'new_biological_N': 0})
    source_files = [p for base in ['sources', 'inputs', 'inputs_LOCAL_ONLY', 'extensions', 'notices', 'expected']
                    for p in sorted((HERE/base).rglob('*')) if p.is_file()]
    source_files += sorted(HERE.glob('*.py'))
    save(out/'INPUT_SOURCE_EXPECTED_MANIFEST.json', {'files': [pin(p) for p in source_files],
         'expected_file_bytes_hashed_before_execution': True,
         'expected_semantic_results_compared_after_each_source_execution': True,
         'scientific_producers_never_consume_expected_targets': True})

    def call(name, script, arguments, expected_exit=0):
        argv = [sys.executable, '-B', '-X', 'utf8', str(script), *map(str, arguments)]
        began = utc(); timer = time.monotonic()
        result = subprocess.run(argv, cwd=HERE, env=env, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True, encoding='utf-8')
        record = {'name': name, 'utc_start': began, 'argv': argv, 'cwd': str(HERE),
                  'elapsed_seconds': time.monotonic()-timer, 'exit_code': result.returncode,
                  'expected_exit': expected_exit, 'stdout': result.stdout, 'stderr': result.stderr,
                  'script': pin(script), 'expected_refusal': expected_exit != 0}
        save(out/'commands'/(name+'.json'), record); calls.append(record)
        print(json.dumps({'command': name, 'exit_code': result.returncode, 'elapsed_seconds': record['elapsed_seconds']}, ensure_ascii=False), flush=True)
        if result.returncode != expected_exit:
            raise RuntimeError('Unexpected process result; logs and partial output retained: ' + name)
        return result

    try:
        # Start with the full public raw-ZIP route. It freezes raw-only outputs
        # before decoding curated reference arrays; its sources remain unchanged.
        public_out = out/'public'
        call('public_epithelial', HERE/'sources/public/replay.py',
             ['--archive', archive, '--output', public_out])
        import numpy as np
        import tifffile
        public_comparison = {'arrays': [], 'graphs': [], 'complete_result_objects': []}
        for expected in sorted((HERE/'expected/public/raw_stages').glob('movie*/*')):
            actual = public_out/'raw_stages'/expected.relative_to(HERE/'expected/public/raw_stages')
            item = {'expected': pin(expected), 'actual': pin(actual), 'byte_equal': pin(expected)['sha256'] == pin(actual)['sha256']}
            if expected.suffix == '.tif':
                left, right = tifffile.imread(expected), tifffile.imread(actual)
                item.update(array_equal=bool(np.array_equal(left, right)), shape=list(right.shape), dtype=str(right.dtype))
                assert item['array_equal'] and left.dtype == right.dtype
                public_comparison['arrays'].append(item)
            else:
                item['differences'] = diff(read(expected), read(actual))
                assert not item['differences']
                public_comparison['graphs'].append(item)
        results = []
        for expected in sorted((HERE/'expected/public/reference_measurement').glob('movie*_complete_result.json')):
            actual = public_out/'reference_measurement'/expected.name
            differences = diff(read(expected), read(actual)); assert not differences
            record = read(actual); results.append(record)
            public_comparison['complete_result_objects'].append({'expected': pin(expected), 'actual': pin(actual), 'differences': differences,
                'movie': record['movie'], 'status': record['status'], 'relation_records': len(record.get('edge_records') or []),
                'path_records': len(record.get('path_records') or [])})
        public_comparison.update(status='FULL_ARRAY_GRAPH_AND_RESULT_OBJECT_COMPARISON_PASS',
             array_count=len(public_comparison['arrays']), graph_count=len(public_comparison['graphs']),
             result_object_count=len(results), relation_count=sum(len(r.get('edge_records') or []) for r in results),
             path_count=sum(len(r.get('path_records') or []) for r in results),
             movie4_ineligible=results[3]['status']=='INELIGIBLE_SINGLE_IMAGE_NOT_TRACKING',
             movie4_S2_object_cap_retained=read(public_out/'raw_stages/movie4/S2_graph.json')['status']=='WITHHELD_OBJECT_CAP')
        assert (public_comparison['array_count'], public_comparison['graph_count'], len(results),
                public_comparison['relation_count'], public_comparison['path_count']) == (16, 16, 4, 6427, 5963)
        save(out/'PUBLIC_COMPLETE_COMPARISON.json', public_comparison)

        primitive = HERE/'sources/primitive'; primitive_comparisons = []
        cases = [('constructed', 'CONSTRUCTED_VARIABLE_VIEWS.json', 0), ('frame_cap', 'FRAME_CAP_REFUSAL.json', 0),
                 ('component_cap', 'COMPONENT_CAP_REFUSAL.json', 0), ('query_cap', 'QUERY_CAP_REFUSAL.json', 0),
                 ('invalid_unit', 'INVALID_UNIT_DOMAIN.json', 1)]
        for name, manifest, exit_code in cases:
            actual_out = out/'primitive'/name
            call('primitive_'+name, primitive/'workflow.py',
                 ['--manifest', HERE/'inputs/primitive'/manifest, '--input-root', HERE/'inputs/primitive/constructed_inputs', '--output', actual_out], exit_code)
            rows = []
            for expected in sorted((HERE/'expected/primitive'/name).iterdir()):
                actual = actual_out/expected.name
                same = expected.read_bytes() == actual.read_bytes()
                assert same, expected.name
                rows.append({'expected': pin(expected), 'actual': pin(actual), 'byte_equal': same})
            reports = [json.loads(line) for line in (actual_out/'REPORTS.jsonl').read_text(encoding='utf-8').splitlines()]
            comparison = {'case': name, 'full_result_files': rows, 'all_scientific_bytes_equal': True,
                          'reports': len(reports), 'statuses': dict(collections.Counter(r['status'] for r in reports))}
            if name == 'invalid_unit':
                failure = read(actual_out/'RUN_FAILURE.json')
                assert failure['error_type'] == 'ValueError' and failure['error'] == 'Graph unit differs from manifest'
                assert not reports and not (actual_out/'RUN_COMPLETE.json').exists()
                comparison['expected_refusal'] = {'error_type': failure['error_type'], 'error': failure['error'], 'no_complete_report': True}
            else:
                comparison['execution_counts'] = read(actual_out/'RUN_COMPLETE.json')['counts']
            primitive_comparisons.append(comparison)
        save(out/'PRIMITIVE_COMPLETE_COMPARISON.json', {'status': 'ALL_COMPLETE_SCIENTIFIC_BYTES_AND_EXPECTED_REFUSALS_PASS', 'cases': primitive_comparisons})

        core = module('candidate_local_graph_core', primitive/'local_graph_core.py')
        save(out/'PATH_AND_FORK_PREDICATE_BOUNDARIES.json', predicate_cases(core))
        typed = HERE/'sources/typed'; typed_comparisons = []
        typed_calls = []
        for source in sorted((HERE/'inputs/typed').glob('*.json')):
            for convention in ['per_view_product', 'same_map_identical_snapshots']:
                typed_calls.append((source, convention, 64, 64, source.stem+'__'+convention))
            if 'ambiguous' in source.stem:
                typed_calls.extend([(source, 'per_view_product', 1, 64, source.stem+'__frame_cap1'),
                                    (source, 'per_view_product', 64, 1, source.stem+'__joint_cap1')])
        for source, convention, frame_cap, joint_cap, name in typed_calls:
            actual_out = out/'typed'/name
            call('typed_'+name, typed/'evaluate_typed_binary.py', ['--input', source, '--output', actual_out,
                 '--convention', convention, '--frame-cap', frame_cap, '--joint-cap', joint_cap])
            actual = read(actual_out/'RESULT.json'); expected_path = HERE/'expected/typed'/name/'RESULT.json'; expected = read(expected_path)
            differences = diff(typed_science(expected), typed_science(actual)); assert not differences, differences
            row = {'case': name, 'expected': pin(expected_path), 'actual': pin(actual_out/'RESULT.json'),
                   'status': actual['status'], 'full_scientific_object_differences': differences,
                   'exact_top_level_provenance_exclusions': ['input_path','time_seconds'],
                   'whole_map_count': actual.get('whole_map_count')}
            if actual['status'] == 'COMPLETE_CONSTRUCTED_TYPED_BINARY_REPORT':
                derived = typed_categories(actual, read(source), core)
                # Complete derived readout is compared too, using the old full maps.
                expected_derived = typed_categories(expected, read(source), core)
                assert not diff(expected_derived, derived)
                save(actual_out/'CATEGORIES_AND_INTERIOR_FEASIBILITY.json', derived)
                row['all_derived_categories_and_interiors_equal'] = True
                row['interior_gap_features'] = {k:v['integer_interior_values_without_a_whole_map_witness'] for k,v in derived['scalar_feasibility'].items() if v['integer_interior_values_without_a_whole_map_witness']}
            else:
                assert actual['readout'] is None and actual['no_truncated_report'] is True
                row['refusal_does_not_emit_truncated_readout'] = True
            typed_comparisons.append(row)
        save(out/'TYPED_COMPLETE_COMPARISON.json', {'status': 'ALL_12_COMPLETE_MAP_HISTORY_SCALAR_CATEGORY_INTERIOR_AND_REFUSAL_OBJECTS_PASS',
             'calls': typed_comparisons, 'statuses': dict(collections.Counter(r['status'] for r in typed_comparisons))})

        # The supplied-family CLI is a separate caller-asserted route. It does
        # not inherit the primitive constructor's optimal/completeness proof.
        portable = HERE/'inputs/supplied_family'
        for command in ['family-history', 'coupled-bounds']:
            call('supplied_'+command, HERE/'run_supplied_family.py', [command,
                 '--reference', portable/'coordinate_reference.json', '--stage', portable/'coordinate_stage_0.json',
                 '--stage', portable/'coordinate_stage_1.json', '--families', portable/'coordinate_families.json',
                 '--output', out/'supplied_family'/(command+'.json')])
        supplied_comparisons = []
        for command in ['family-history', 'coupled-bounds']:
            expected_path = HERE/'expected/supplied_family'/(command+'.json')
            actual_path = out/'supplied_family'/(command+'.json')
            actual_science = {k:v for k,v in read(actual_path).items() if k != 'input_receipts'}
            legacy_actual = json.loads(json.dumps(actual_science))
            added_paths = []
            if command == 'coupled-bounds':
                # Backward compatibility uses an exact whitelist of genuinely new
                # fields. The COMPLETE new object is compared separately below.
                assert legacy_actual['result']['whole_map_endpoint_witness_indices_emitted_and_replayed'] is True
                del legacy_actual['result']['whole_map_endpoint_witness_indices_emitted_and_replayed']
                added_paths.append('$.result.whole_map_endpoint_witness_indices_emitted_and_replayed')
                for field, bound in legacy_actual['result']['scalar_bounds'].items():
                    for side in ['minimum','maximum']:
                        added_paths.append('$.result.scalar_bounds.'+field+'.'+side+'_witness')
                        del bound[side+'_witness']
            differences = diff(read(expected_path), legacy_actual)
            assert not differences, differences
            supplied_comparisons.append({'command': command, 'expected': pin(expected_path),
                'actual': pin(actual_path), 'all_legacy_scientific_fields_differences': differences,
                'new_witness_fields_excluded_from_legacy_compatibility_only': added_paths,
                'exact_top_level_provenance_exclusions': ['input_receipts']})
            if command == 'coupled-bounds':
                generated = HERE/'expected/supplied_family_witness_generated/coupled-bounds.json'
                target = {k:v for k,v in read(generated).items() if k != 'input_receipts'}
                full_differences = diff(target, actual_science)
                assert not full_differences, full_differences
                supplied_comparisons[-1].update(full_new_expected=pin(generated),
                    complete_new_scientific_object_differences=full_differences,
                    target_origin='EXPECTED_TARGET_ORIGIN.json: separately generated by the copied witness producer before this execution',
                    no_new_scientific_field_hidden_from_full_comparison=True)
        save(out/'SUPPLIED_FAMILY_COMPLETE_COMPARISON.json', {'status': 'LEGACY_SCALARS_AND_COMPLETE_NEW_WITNESS_OBJECTS_PASS',
             'results': supplied_comparisons})
        save(out/'SUPPLIED_FAMILY_BOUNDARY.json', {'commands': ['family-history', 'coupled-bounds'],
             'caller_completeness_assertion': read(portable/'coordinate_families.json')['completeness_asserted_by_user'],
             'constructor_optimality_completeness_guarantee': False,
             'input_and_both_full_outputs_retained': True, 'no_new_scientific_N': True})
        natural = HERE/'extensions/natural'
        natural_out = out/'natural'
        call('natural_complete_family_scalar_local', natural/'reproduce_natural.py',
             ['--input-root', HERE/'inputs_LOCAL_ONLY/natural/coordinate_all8', '--output', natural_out])
        natural_comparisons=[]
        known_natural=HERE/'inputs_LOCAL_ONLY/known_natural_outputs'
        for expected in sorted(known_natural.rglob('*')):
            if not expected.is_file(): continue
            actual=natural_out/expected.relative_to(known_natural)
            equal=expected.read_bytes()==actual.read_bytes()
            assert equal, 'Complete natural target differs: '+str(expected.relative_to(known_natural))
            natural_comparisons.append({'expected':pin(expected),'actual':pin(actual),'complete_scientific_bytes_equal':True})
        save(out/'NATURAL_COMPLETE_TARGET_COMPARISON.json',{'status':'ALL_FULL_NATURAL_FAMILY_LOCAL_DEFINITION_AND_DECISION_BYTES_EQUAL',
            'files':natural_comparisons,'comparison_after_scientific_production':True,'no_science_fields_excluded':True})
        call('natural_same_information_literal_constrained_baseline', natural/'literal_constrained_baseline_v03.py',
             ['--input-root', HERE/'inputs_LOCAL_ONLY/natural/coordinate_all8',
              '--compare-family', natural_out/'family/gate_07', '--output', out/'literal_constrained_baseline'])
        call('actual_whole_map_endpoint_membership_and_full_scalar_replay', HERE/'r1_witness_replay.py',
             ['--natural-family', natural_out/'family/gate_07',
              '--natural-input-root', HERE/'inputs_LOCAL_ONLY/natural/coordinate_all8',
              '--supplied-result', out/'supplied_family/coupled-bounds.json', '--output', out/'witness_replay'])
        operating=HERE/'extensions/operating_envelope'
        call('controlled_operating_envelope_27inputs_54comparisons', operating/'run_operating_envelope.py',
             ['--output', out/'operating_envelope'])
        call('controlled_operating_envelope_raw_literal_second_implementation', operating/'audit_from_raw.py',
             ['--input-run', out/'operating_envelope', '--output', out/'operating_envelope_raw_audit'])
        table=read(out/'operating_envelope/REPORT_TABLE.json')
        known_table=read(HERE/'expected/operating_envelope/REPORT_TABLE.json')
        timing_fields={'shared_frame_construction_seconds','additional_factor_certificate_seconds','query_assembly_seconds'}
        science=lambda rows:[{k:v for k,v in row.items() if k not in timing_fields} for row in rows]
        table_differences=diff(science(known_table),science(table))
        assert not table_differences,table_differences
        raw=read(out/'operating_envelope_raw_audit/AUDIT_COMPLETE.json')
        assert (raw['raw_frame_optimum_sets'],raw['reports_equal'],raw['whole_map_membership_and_history_replays'])==(270,4032,11760)
        input_diffs=[]
        for expected in sorted((HERE/'inputs/operating_envelope/constructed_inputs').rglob('*.npz')):
            actual=out/'operating_envelope/constructed_inputs'/expected.relative_to(HERE/'inputs/operating_envelope/constructed_inputs')
            with np.load(expected,allow_pickle=False)as left,np.load(actual,allow_pickle=False)as right:
                assert set(left.files)==set(right.files)
                assert all(left[k].dtype==right[k].dtype and np.array_equal(left[k],right[k]) for k in left.files)
            input_diffs.append({'expected':pin(expected),'actual':pin(actual),'all_arrays_dtype_units_equal':True})
        save(out/'OPERATING_ENVELOPE_COMPLETE_COMPARISON.json',{'status':'ALL54_COMPLETE_SCIENTIFIC_TABLE_ROWS_AND_RAW_LITERAL_REPLAYS_EQUAL',
            'full_table_differences':table_differences,'exact_timing_only_comparison_exclusions':sorted(timing_fields),
            'rows':54,'generated_input_array_comparisons':input_diffs,'raw_literal_audit':raw,
            'biological_N_added':0,'speed_advantage_claimed':False})
        call('bacterial_public_fixed_archive_and_identity_replay', HERE/'run_bacterial_packaged.py',
             ['--output', out/'bacterial'])
        call('normalize_selected_path_exclusivity_metadata', HERE/'normalize_query_metadata_r1.py',
             ['--records', out, '--output', out/'QUERY_NAME_SIDECAR.json'])
        save(out/'RUN_COMPLETE.json', {'utc': utc(), 'status': 'UNIFIED_R1_COMPLETE_SOURCE_ROUTES_AND_FULL_COMPARISONS_PASS',
             'elapsed_seconds': time.monotonic()-start, 'command_count': len(calls), 'new_biological_N': 0,
             'prior_results_known': True, 'blind_validation': False, 'public_release': False,
             'code_licence_granted_by_execution': False, 'copied_scientific_producers_unchanged': True,
             'portable_actual_whole_map_witness_extension_included': True,
             'restricted_inputs_and_entire_working_packet_local_only': True,
             'expected_refusals_are_retained_results': True})
    except Exception as error:
        save(out/'RUN_FAILURE.json', {'utc': utc(), 'error': repr(error), 'traceback': traceback.format_exc(),
                                     'partial_outputs_and_commands_preserved': True})
        raise
    finally:
        # Captures successful or failed complete output tree, excluding itself.
        save(out/'OUTPUT_MANIFEST.json', {'utc': utc(), 'self_excluded': True,
             'files': [{**pin(p), 'relative_path': p.relative_to(out).as_posix()} for p in sorted(out.rglob('*')) if p.is_file()]})
    print(json.dumps({'status': 'UNIFIED_R1_COMPLETE_SOURCE_ROUTES_AND_FULL_COMPARISONS_PASS', 'output': str(out)}, ensure_ascii=False))


if __name__ == '__main__':
    main()

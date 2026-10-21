"""Create deterministic algebraic coordinate controls, without study data."""
from pathlib import Path
import argparse, json
import numpy as np

def write(path, ids, coords, edges):
    np.savez_compressed(path, ids=np.array(ids,dtype=np.int64), coords=np.array(coords,dtype=np.float64),
                        edges=np.array(edges,dtype=np.int64).reshape(-1,2))

def generate(root):
    root = Path(root); root.mkdir(parents=True,exist_ok=False)
    shared = root/'shared_choice'; shared.mkdir()
    write(shared/'reference.npz',[1,2,3],[[0,0,0,0],[1,0,0,0],[2,0,0,0]],[[1,2],[2,3]])
    write(shared/'prediction.npz',[101,201,202,301],[[0,0,0,0],[1,0,0,-1],[1,0,0,1],[2,0,0,0]],[[101,201],[202,301]])
    unmatched = root/'unmatched'; unmatched.mkdir()
    write(unmatched/'reference.npz',[1,11,12,13,21],[[0,0,0,0],[1,0,0,0],[1,0,0,0],[1,0,0,3],[2,0,0,0]],[[1,11],[11,21]])
    write(unmatched/'prediction.npz',[100,101,102],[[0,0,0,0],[1,0,0,1],[2,0,0,0]],[[100,101],[101,102]])
    specification = {'schema':'review-constructed-inputs/1', 'unit':'um', 'gate_um':1.25,
        'examples':{'shared_choice':{'path':[1,2,3],'proposed_value':1,'attainable_values':[0], 'relaxation':[0,1], 'family_sizes':[1,2,1]},
                    'unmatched':{'path':[1,11,21],'proposed_value':1,'attainable_values':[0,1], 'relaxation':[0,1], 'family_sizes':[1,2,1]}},
        'study_data_included':False, 'purpose':'Software controls, including the S1 unmatched algebraic illustration; no biological experiment'}
    (root/'SPECIFICATION.json').write_text(json.dumps(specification,indent=2)+'\n',encoding='utf8')
    return specification

if __name__=='__main__':
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--output',type=Path,required=True)
    print(json.dumps(generate(ap.parse_args().output)))

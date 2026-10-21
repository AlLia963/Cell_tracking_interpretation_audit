"""Replay a saved natural query or pair from an explicitly supplied corpus root."""
from pathlib import Path
import argparse,json
from historical_producers import replay_record as replay
p=argparse.ArgumentParser(description=__doc__);p.add_argument('--corpus',type=Path,required=True);p.add_argument('--graph');p.add_argument('--kind',choices=['path','fork'],default='path');p.add_argument('--query-index',type=int,default=0);p.add_argument('--pair-witness');p.add_argument('--output',type=Path,required=True)
a=p.parse_args();replay.O=a.corpus.resolve()
if a.output.exists():raise FileExistsError('Use a new output file')
r=replay.replay_pair(a.pair_witness)if a.pair_witness else replay.replay_query(a.graph,a.kind,a.query_index)
a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(r,indent=2),encoding='utf8');print(r['status'])

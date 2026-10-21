"""Optional acquisition recipe: fetch a pinned public file and verify its bytes."""
from pathlib import Path
import argparse,hashlib,json,urllib.request

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--manifest',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args();m=json.loads(a.manifest.read_text(encoding='utf-8-sig'))
    target=a.output.resolve();partial=target.with_name(target.name+'.part')
    if target.exists() or partial.exists():raise FileExistsError('Both final and partial acquisition outputs must be absent')
    target.parent.mkdir(parents=True,exist_ok=True)
    with urllib.request.urlopen(m['download_url'])as response,partial.open('xb')as dest:
        while data:=response.read(1024*1024):dest.write(data)
    with partial.open('rb')as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
    if partial.stat().st_size!=m['archive_bytes'] or digest!=m['archive_sha256']:
        raise ValueError('Downloaded bytes do not match the pinned record; partial file retained')
    partial.rename(target)
    print(json.dumps({'path':str(target),'bytes':target.stat().st_size,'sha256':digest,'source':m['primary_record']}))

if __name__=='__main__':main()

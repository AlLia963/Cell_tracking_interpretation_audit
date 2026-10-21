"""Explicit opt-in acquisition recipe; not invoked by archive reproduction."""
from pathlib import Path
import argparse, hashlib, json, re, urllib.request, zipfile
from run_archive import sha, write, require
ASSETS=[('CTC.zip','https://zenodo.org/api/records/11237127/files/CTC.zip/content','280f4cacda12094b6eafaae772ce7ea25f8ad6093d2ec2b3d381504dbea70ed3',315362069),('author_source.tar.gz','https://gitlab.com/api/v4/projects/41560384/repository/archive.tar.gz?sha=f02fd86509960173e3fa997da6f429e394867387','15642e67bff2e08a2b6354de7480b368829e81c5a02baaef024d6f5bce1cd635',None),('checkpoint_moma.pth','https://zenodo.org/api/records/14509424/files/checkpoint_moma.pth/content','61dcc58d841fa55f1232f387c3b6b1c1f611c066ea34d5f5046cd7728f56b948',183394761)]
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',type=Path,required=True);ap.add_argument('--extract-raw',action='store_true');a=ap.parse_args();out=a.output.resolve();require(not out.exists(),'Output must be absent');out.mkdir(parents=True);records=[]
    for name,url,digest,size in ASSETS:
        p=out/name
        with urllib.request.urlopen(url,timeout=120) as response,p.open('xb') as dest:
            while True:
                b=response.read(4*1024*1024)
                if not b:break
                dest.write(b)
        require(sha(p)==digest and (size is None or p.stat().st_size==size),'Acquired asset bytes differ: '+name);records.append({'file':name,'url':url,'bytes':p.stat().st_size,'sha256':digest})
    if a.extract_raw:
        pins={}
        with zipfile.ZipFile(out/'CTC.zip') as z:
            for name in sorted(z.namelist()):
                match=re.fullmatch(r'CTC/test/(\d{2})/(t\d{3}\.tif)',name)
                if not match:continue
                film,filename=match.groups();raw=z.read(name);p=out/'raw_all29_v0.1'/film/filename;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(raw);pins[name]=hashlib.sha256(raw).hexdigest()
        require(len(pins)==5340,'Public raw cohort must have all5340 inputs');write(out/'raw_all29_manifest.json',{'input_sha256':pins,'archive_sha256':sha(out/'CTC.zip'),'reference_masks_extracted':False})
        p=out/'raw_input_v0.1/01/t000.tif';p.parent.mkdir(parents=True);p.write_bytes((out/'raw_all29_v0.1/01/t000.tif').read_bytes())
    write(out/'ACQUISITION_RECEIPT.json',{'records':records,'source_revision':'f02fd86509960173e3fa997da6f429e394867387','CTC_DOI':'10.5281/zenodo.11237127','metadata_license':'CC-BY-4.0 according to supplied original metadata; no author permission granted here','original_checkpoint_dataset_relationship':'supplied public author checkpoint; no historical training-isolation claim','local_only_working_extension':True})
if __name__=='__main__':main()

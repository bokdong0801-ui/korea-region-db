#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, time, urllib.error, urllib.request
from datetime import datetime, timezone
from pathlib import Path

URL='https://data.kric.go.kr/rips/dataset/download.file?type=filedata&id=32&operation=1'
DETAIL='https://data.kric.go.kr/rips/M_01_01/detail.do?id=32'

def sha256(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def download(max_attempts:int=5):
    last=None
    for attempt in range(1,max_attempts+1):
        try:
            req=urllib.request.Request(URL,headers={'User-Agent':'Mozilla/5.0 (compatible; korea-region-db/1.0)','Referer':DETAIL})
            with urllib.request.urlopen(req,timeout=120) as r:
                raw=r.read(); ctype=r.headers.get('content-type','')
            if len(raw)<10000:
                raise RuntimeError(f'KRiC download unexpectedly small: {len(raw)}')
            return raw,ctype,attempt
        except (urllib.error.URLError,urllib.error.HTTPError,TimeoutError,OSError,RuntimeError) as e:
            last=e
            if attempt==max_attempts: break
            time.sleep(min(2**(attempt-1),16))
    raise SystemExit(f'KRiC download failed after {max_attempts} attempts: {last}')

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--out-dir',type=Path,default=Path('data/raw/stations')); ap.add_argument('--snapshot-date',default='2026-06-30'); a=ap.parse_args()
    a.out_dir.mkdir(parents=True,exist_ok=True)
    raw,ctype,attempts=download()
    out=a.out_dir/f'kric_urban_stations_{a.snapshot_date}.xlsx'; out.write_bytes(raw)
    meta={'source_id':'kric_urban_station','detail_url':DETAIL,'download_url':URL,'snapshot_date':a.snapshot_date,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'download_attempts_used':attempts,'filename':out.name,'bytes':len(raw),'sha256':sha256(raw),'content_type':ctype}
    (a.out_dir/'kric_station_download_meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

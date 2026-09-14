#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, time, urllib.request, urllib.error, http.cookiejar
from datetime import datetime, timezone
from pathlib import Path

LANDING='https://www.vworld.kr/dtmk/dtmk_ntads_s002.do?svcCde=MK&dsId=30231'
DOWNLOAD='https://www.vworld.kr/dtmk/downloadResourceFile.do?ds_id=30231&fileNo=1'

def sha256(b:bytes)->str:return hashlib.sha256(b).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out-dir',type=Path,required=True);ap.add_argument('--snapshot-date',default='2026-09-14');a=ap.parse_args()
    a.out_dir.mkdir(parents=True,exist_ok=True)
    cj=http.cookiejar.CookieJar();opener=urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    headers={'User-Agent':'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 Chrome/152 Safari/537.36','Accept':'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8'}
    try:
        opener.open(urllib.request.Request(LANDING,headers=headers),timeout=90).read(4096)
    except Exception:
        pass
    raw=None;ctype='';attempt_used=0;last=None
    for attempt in range(1,6):
        attempt_used=attempt
        try:
            req=urllib.request.Request(DOWNLOAD,headers={**headers,'Referer':LANDING,'Accept':'application/zip,application/octet-stream,*/*'})
            with opener.open(req,timeout=120) as r:
                raw=r.read();ctype=r.headers.get('content-type','')
            if len(raw)<10000: raise RuntimeError(f'VWorld payload unexpectedly small: {len(raw)}')
            if not raw.startswith(b'PK'): raise RuntimeError(f'VWorld payload is not ZIP: {raw[:16]!r}')
            break
        except Exception as e:
            last=repr(e);raw=None
            if attempt<5:time.sleep(min(30,2**attempt))
    if raw is None:raise SystemExit(f'VWorld place-name download failed after {attempt_used} attempts: {last}')
    out=a.out_dir/'N3P_H0040000.zip';out.write_bytes(raw)
    meta={'source_id':'vworld_ngii_continuous_topographic_place_names','dataset_id':'30231','landing_url':LANDING,'download_url':DOWNLOAD,'snapshot_date':a.snapshot_date,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'filename':out.name,'bytes':len(raw),'sha256':sha256(raw),'content_type':ctype,'download_attempts_used':attempt_used,'license':'CC BY','origin_agency':'국토교통부 국토지리정보원'}
    (a.out_dir/'vworld_names_download_meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

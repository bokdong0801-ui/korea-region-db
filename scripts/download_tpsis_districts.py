#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

BASE='https://openapi.jigu.go.kr'
DETAIL=BASE+'/down/detail.do?table=BLS5_DSTRC_INFO'
LIST=BASE+'/api/list.json'
OPENAPI=BASE+'/openApi'
TABLE='BLS5_DSTRC_INFO'

def request(url:str,data:dict|None=None,timeout=120):
    body=urllib.parse.urlencode(data).encode() if data is not None else None
    req=urllib.request.Request(url,data=body,headers={'User-Agent':'Mozilla/5.0 (compatible; korea-region-db/1.0)','Referer':DETAIL})
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read(),dict(r.headers)

def sha(b:bytes):return hashlib.sha256(b).hexdigest()

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out-dir',type=Path,default=Path('data/raw/development'));a=ap.parse_args();a.out_dir.mkdir(parents=True,exist_ok=True)
    raw,_=request(LIST,{'tNm':TABLE,'table':TABLE,'ctprvn':'','ntfcDe':''}); payload=json.loads(raw.decode('utf-8'))
    rows=payload.get('list',[])
    cands=[r for r in rows if str(r.get('ctprvn'))=='00' and str(r.get('fileTy','')).lower()=='csv' and r.get('table')==TABLE]
    if not cands:raise SystemExit('TPSIS national CSV listing not found')
    cands.sort(key=lambda r:(str(r.get('dt','')),int(r.get('fileNo',0))),reverse=True);row=cands[0]
    params={'fileTy':'csv','stdrDe':str(row['dt']).replace('-',''),'ctprvn':'00','table':TABLE,'fileNo':str(row['fileNo'])}
    q=urllib.parse.urlencode(params)
    exist_url=OPENAPI+'/fileExist.json?'+q
    exist_raw,exist_headers=request(exist_url)
    try:exist_json=json.loads(exist_raw.decode('utf-8','replace'))
    except Exception:exist_json={'raw':exist_raw.decode('utf-8','replace')[:1000]}
    down_url=OPENAPI+'/down.do?'+q
    data,headers=request(down_url)
    ctype=headers.get('Content-Type',headers.get('content-type',''))
    disp=headers.get('Content-Disposition',headers.get('content-disposition',''))
    head=data[:200].lstrip().lower()
    if len(data)<500 or head.startswith(b'<!doctype html') or head.startswith(b'<html'):
        raise SystemExit(f'TPSIS direct public download failed/returned HTML: bytes={len(data)} type={ctype} head={data[:200]!r}')
    date=str(row.get('dt','')).replace('-','');out=a.out_dir/f'tpsis_district_info_{date}.csv';out.write_bytes(data)
    meta={'source_id':'tpsis_district_info','detail_url':DETAIL,'list_api':LIST,'download_url':down_url,'file_exist_url':exist_url,'listing_record':row,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'filename':out.name,'bytes':len(data),'sha256':sha(data),'content_type':ctype,'content_disposition':disp,'file_exist_response':exist_json,'usage_metadata_supplied':False,'policy_note':'Downloaded through public file endpoint without fabricating user/job/organization metadata.'}
    (a.out_dir/'tpsis_download_meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(meta,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

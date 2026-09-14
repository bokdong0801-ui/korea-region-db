#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, io, json, urllib.parse, urllib.request, zipfile
from datetime import datetime, timezone
from pathlib import Path

BASE='https://openapi.jigu.go.kr'; LIST=BASE+'/api/list.json'; OPENAPI=BASE+'/openApi'
TABLES=('BLS5_DSTRC_INFO','BLS5_DSTRC_LAND_HIST')

def request(url:str,data:dict|None=None,referer:str|None=None,timeout=120):
    body=urllib.parse.urlencode(data).encode() if data is not None else None
    req=urllib.request.Request(url,data=body,headers={'User-Agent':'Mozilla/5.0 (compatible; korea-region-db/1.0)','Referer':referer or BASE})
    with urllib.request.urlopen(req,timeout=timeout) as r:return r.read(),dict(r.headers)
def sha(b:bytes):return hashlib.sha256(b).hexdigest()

def fetch_table(table:str,out_dir:Path):
    detail=BASE+f'/down/detail.do?table={table}'
    raw,_=request(LIST,{'tNm':table,'table':table,'ctprvn':'','ntfcDe':''},detail);rows=json.loads(raw.decode('utf-8')).get('list',[])
    cands=[r for r in rows if str(r.get('ctprvn'))=='00' and str(r.get('fileTy','')).lower()=='csv' and r.get('table')==table]
    if not cands:raise SystemExit(f'TPSIS national CSV listing not found: {table}')
    cands.sort(key=lambda r:(str(r.get('dt','')),int(r.get('fileNo',0))),reverse=True);row=cands[0]
    params={'fileTy':'csv','stdrDe':str(row['dt']).replace('-',''),'ctprvn':'00','table':table,'fileNo':str(row['fileNo'])};q=urllib.parse.urlencode(params)
    exist_url=OPENAPI+'/fileExist.json?'+q; exist_raw,_=request(exist_url,referer=detail)
    try:exist_json=json.loads(exist_raw.decode('utf-8','replace'))
    except Exception:exist_json={'raw':exist_raw.decode('utf-8','replace')[:500]}
    down_url=OPENAPI+'/down.do?'+q;data,headers=request(down_url,referer=detail)
    if len(data)<500 or data[:200].lstrip().lower().startswith((b'<!doctype html',b'<html')):raise SystemExit(f'TPSIS download failed: {table} bytes={len(data)}')
    date=str(row.get('dt','')).replace('-','');zip_path=out_dir/f'{table}_{date}.zip';zip_path.write_bytes(data)
    extracted=[]
    if not zipfile.is_zipfile(io.BytesIO(data)):raise SystemExit(f'TPSIS expected ZIP response: {table} head={data[:20]!r}')
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for info in z.infolist():
            if info.is_dir():continue
            b=z.read(info); ext=Path(info.filename).suffix.lower(); name=f'{table}_{date}{ext or ".dat"}'; p=out_dir/name;p.write_bytes(b)
            extracted.append({'member':info.filename,'filename':p.name,'bytes':len(b),'sha256':sha(b)})
    return {'source_id':'tpsis_'+table.lower(),'detail_url':detail,'list_api':LIST,'download_url':down_url,'file_exist_url':exist_url,'listing_record':row,'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'zip_filename':zip_path.name,'zip_bytes':len(data),'zip_sha256':sha(data),'content_type':headers.get('Content-Type',headers.get('content-type','')),'content_disposition':headers.get('Content-Disposition',headers.get('content-disposition','')),'file_exist_response':exist_json,'extracted':extracted,'usage_metadata_supplied':False,'policy_note':'Public file endpoint used without fabricating user/job/organization metadata.'}

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--out-dir',type=Path,default=Path('data/raw/development'));a=ap.parse_args();a.out_dir.mkdir(parents=True,exist_ok=True)
    meta={'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),'tables':[fetch_table(t,a.out_dir) for t in TABLES]}
    (a.out_dir/'tpsis_download_meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(meta,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

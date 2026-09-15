#!/usr/bin/env python3
from __future__ import annotations

import argparse, json, os, time, urllib.parse, urllib.request
from datetime import datetime, timezone
from pathlib import Path

API='https://api.vworld.kr/req/data'
LAYER='LT_P_NSNMSSITENM'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--out-dir',type=Path,required=True)
    ap.add_argument('--bbox',default='126.7,37.3,127.3,37.8',help='EPSG:4326 minx,miny,maxx,maxy; schema probe only')
    ap.add_argument('--size',type=int,default=100)
    a=ap.parse_args(); a.out_dir.mkdir(parents=True,exist_ok=True)
    key=os.environ.get('VWORLD_API_KEY','').strip()
    if not key:
        status={'status':'CREDENTIAL_REQUIRED','required_secret':'VWORLD_API_KEY','source':'VWorld 2D Data API','layer':LAYER}
        (a.out_dir/'vworld_api_probe_status.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
        raise SystemExit('VWORLD_API_KEY is required; no credential is stored in repository code')
    params={
        'key':key,'service':'data','version':'2.0','request':'GetFeature','format':'json',
        'size':str(max(1,min(a.size,1000))),'page':'1','data':LAYER,
        'geometry':'true','attribute':'true','crs':'EPSG:4326','geomFilter':f'BOX({a.bbox})'
    }
    url=API+'?'+urllib.parse.urlencode(params)
    safe_url=API+'?'+urllib.parse.urlencode({**params,'key':'REDACTED'})
    raw=None; last=''
    for attempt in range(1,5):
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'korea-region-db/1.0','Accept':'application/json'})
            with urllib.request.urlopen(req,timeout=90) as r: raw=r.read()
            break
        except Exception as e:
            last=repr(e)
            if attempt<4: time.sleep(2**attempt)
    if raw is None: raise SystemExit(f'VWorld API probe failed: {last}')
    (a.out_dir/'vworld_national_names_probe_raw.json').write_bytes(raw)
    obj=json.loads(raw.decode('utf-8'))
    response=obj.get('response',{}) if isinstance(obj,dict) else {}
    status=response.get('status','')
    if status and status != 'OK':
        err=response.get('error') or {}
        raise SystemExit(f'VWorld API returned status={status} error={err}')
    result=response.get('result') or {}
    fc=result.get('featureCollection') or {}
    features=fc.get('features') or []
    keys=[]; examples={}
    geometry_types=[]
    for f in features:
        props=f.get('properties') or {}
        for k,v in props.items():
            if k not in keys: keys.append(k)
            if k not in examples and v not in (None,''): examples[k]=v
        gt=((f.get('geometry') or {}).get('type') or '')
        if gt and gt not in geometry_types: geometry_types.append(gt)
    schema={
        'status':'PASS','source':'VWorld 2D Data API','layer':LAYER,
        'request_url_redacted':safe_url,'bbox_epsg4326':a.bbox,
        'retrieved_at_utc':datetime.now(timezone.utc).isoformat(),
        'feature_count':len(features),'property_keys':sorted(keys),
        'property_examples':{k:examples[k] for k in sorted(examples)},
        'geometry_types':geometry_types,
        'response_status':status or 'UNKNOWN',
        'purpose':'Schema audit before nationwide NGII natural-toponym ingestion; no field mapping is guessed.'
    }
    (a.out_dir/'vworld_national_names_schema_report.json').write_text(json.dumps(schema,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(schema,ensure_ascii=False,indent=2))
    if not features: raise SystemExit('VWorld API returned zero features in probe bbox; change bbox before schema mapping')

if __name__=='__main__': main()

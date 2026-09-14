#!/usr/bin/env python3
from __future__ import annotations
import argparse,json,zipfile,tempfile
from pathlib import Path
import shapefile

def main():
    ap=argparse.ArgumentParser();ap.add_argument('zip_path',type=Path);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    a.out.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(a.zip_path) as z:z.extractall(td)
        shps=list(Path(td).rglob('*.shp'))
        if not shps:raise SystemExit('No SHP found')
        shp=shps[0]
        r=shapefile.Reader(str(shp),encoding='cp949',encodingErrors='replace')
        fields=[f[0] for f in r.fields[1:]]
        samples=[]
        for rec in r.iterRecords():
            samples.append({fields[i]:rec[i] for i in range(min(len(fields),len(rec)))})
            if len(samples)>=10:break
        report={'shp_member':shp.name,'record_count':len(r),'shape_type':r.shapeType,'fields':r.fields[1:],'sample_records':samples}
    a.out.write_text(json.dumps(report,ensure_ascii=False,indent=2,default=str),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2,default=str))
if __name__=='__main__':main()

#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,zipfile
from pathlib import Path
import shapefile
from pyproj import CRS

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--v4-places',type=Path,required=True);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args()
    legal=[]
    with a.v4_places.open(encoding='utf-8-sig',newline='') as f:
        for r in csv.DictReader(f):
            if r.get('place_id','').startswith('bjd:') and r.get('legal_status')=='CURRENT' and r.get('place_type') in ('LEGAL_DONG','LEGAL_RI'):
                legal.append(r)
            if len(legal)>=2:break
    if len(legal)<2:raise SystemExit('Need two current legal targets')
    stem=a.out.parent/'N3P_H0040000';stem.parent.mkdir(parents=True,exist_ok=True)
    w=shapefile.Writer(str(stem),shapeType=shapefile.POINT,encoding='cp949')
    for name,field_type,size in [('UFID','C',34),('NAME','C',100),('DIVI','C',6),('TYPE','C',6),('BJCD','C',10),('SCLS','C',8),('FMTA','C',9)]:
        w.field(name,field_type,size=size)
    w.point(126.98,37.57);w.record('TEST-VILLAGE-001','테스트마을','PNN001','PNT007',legal[0]['official_code'],'TEST','TEST')
    w.point(127.00,37.58);w.record('TEST-NATURAL-002','테스트들','PNN001','PNT004',legal[1]['official_code'],'TEST','TEST')
    w.close();stem.with_suffix('.prj').write_text(CRS.from_epsg(4326).to_wkt(),encoding='utf-8')
    with zipfile.ZipFile(a.out,'w',zipfile.ZIP_DEFLATED) as z:
        for ext in ('.shp','.shx','.dbf','.prj'):z.write(stem.with_suffix(ext),arcname=stem.name+ext)
    print(a.out)
if __name__=='__main__':main()

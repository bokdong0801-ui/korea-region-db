#!/usr/bin/env python3
from __future__ import annotations

import argparse,csv,json,tempfile,zipfile
from collections import Counter
from pathlib import Path
import shapefile
from pyproj import CRS,Transformer

DIVI_LABEL={'PNN000':'미분류','PNN001':'자연지명','PNN002':'행정지명','PNN003':'산업지명','PNN004':'환경지명','PNN005':'관광문화지명'}
TYPE_LABEL={'PNT000':'미분류','PNT001':'만','PNT002':'반도','PNT003':'평야','PNT004':'들','PNT005':'계곡','PNT006':'령','PNT007':'부락','PNT008':'행정명','PNT009':'법정명','PNT010':'단지','PNT011':'섬','PNT012':'바다','PNT013':'바위','PNT014':'항구','PNT015':'산업지명(단지)','PNT016':'환경지명(단지)','PNT017':'관광문화지명(단지)'}

def read_csv(p):
    with Path(p).open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write_csv(p,rows,fields):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def ptype(divi,t):
    if t=='PNT007':return 'VILLAGE'
    if t=='PNT008':return 'ADMIN_TOPONYM'
    if t=='PNT009':return 'LEGAL_TOPONYM'
    if divi=='PNN001':return 'NATURAL_TOPONYM'
    return 'TOPONYM'
def relation_type(t):return 'VILLAGE_IN' if t=='PNT007' else 'TOPONYM_IN'
def norm(v):return '' if v is None else str(v).strip()

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('source_zip',type=Path)
    ap.add_argument('--v4-places',type=Path,required=True,help='Audited base master places CSV; name retained for backward compatibility')
    ap.add_argument('--snapshot-date',default='2026-09-15')
    ap.add_argument('--out-dir',type=Path,required=True)
    ap.add_argument('--natural-only',action='store_true',help='Import only official NGII natural names (DIVI=PNN001); raw ZIP remains untouched')
    a=ap.parse_args();a.out_dir.mkdir(parents=True,exist_ok=True)
    base=read_csv(a.v4_places)
    legal={r['official_code']:r for r in base if r.get('place_id','').startswith('bjd:') and r.get('official_code')}
    places=[];rels=[];aliases=[];details=[];unmatched=[];invalid=[];seen=set();dup=0;raw_seen=0;excluded_non_natural=0
    with tempfile.TemporaryDirectory() as td:
        with zipfile.ZipFile(a.source_zip) as z:z.extractall(td)
        shps=list(Path(td).rglob('*.shp'))
        if not shps:raise SystemExit('No SHP in NGII source ZIP')
        shp=shps[0];prj=shp.with_suffix('.prj')
        reader=shapefile.Reader(str(shp),encoding='cp949',encodingErrors='replace')
        fields=[f[0].upper() for f in reader.fields[1:]]
        required={'UFID','NAME','DIVI','TYPE','BJCD'}
        missing=required-set(fields)
        if missing:raise SystemExit(f'Missing required NGII fields: {sorted(missing)}; got={fields}')
        transformer=None;source_crs=''
        if prj.exists() and prj.read_text(errors='ignore').strip():
            crs=CRS.from_wkt(prj.read_text(errors='ignore'));source_crs=crs.to_string();transformer=Transformer.from_crs(crs,CRS.from_epsg(4326),always_xy=True)
        idx={k:fields.index(k) for k in fields}
        for rec,shape in zip(reader.iterRecords(),reader.iterShapes()):
            raw_seen+=1
            row={k:norm(rec[i]) for k,i in idx.items()}
            ufid=row.get('UFID','');name=row.get('NAME','');divi=row.get('DIVI','');typ=row.get('TYPE','');bjcd=''.join(ch for ch in row.get('BJCD','') if ch.isdigit())
            if a.natural_only and divi!='PNN001':
                excluded_non_natural+=1
                continue
            if not ufid or not name:
                invalid.append({'ufid':ufid,'name':name,'bjcd':bjcd,'reason':'MISSING_UFID_OR_NAME'});continue
            if ufid in seen:dup+=1;continue
            seen.add(ufid)
            x=y=None
            if shape.points:
                x,y=shape.points[0]
                if transformer:x,y=transformer.transform(x,y)
                elif not (-180<=x<=180 and -90<=y<=90):raise SystemExit('PRJ missing and coordinates are not lon/lat')
            pid='toponym:ngii:'+ufid
            pt=ptype(divi,typ)
            places.append({'place_id':pid,'place_type':pt,'hierarchy_level':'TOPONYM','name_ko':name,'full_name_ko':name,'official_code':ufid,'parent_place_id':'','legal_status':'CURRENT','valid_from':'','valid_to':'','source_id':'ngii_vworld_h0040000','validity_source_id':'ngii_vworld_h0040000','source_snapshot_date':a.snapshot_date,'latitude':f'{y:.8f}' if y is not None else '','longitude':f'{x:.8f}' if x is not None else ''})
            aliases.append({'place_id':pid,'alias':name,'alias_type':'OFFICIAL_NAME','source_id':'ngii_vworld_h0040000'})
            target=legal.get(bjcd)
            if target:
                rels.append({'from_place_id':pid,'to_place_id':target['place_id'],'relation_type':relation_type(typ),'confidence':'1.0','legal_status':'CURRENT','valid_from':'','valid_to':'','source_id':'ngii_vworld_h0040000','source_snapshot_date':a.snapshot_date})
            else:
                unmatched.append({'place_id':pid,'ufid':ufid,'name_ko':name,'divi':divi,'type':typ,'bjcd':bjcd,'reason':'BJCD_NOT_FOUND_IN_BASE' if bjcd else 'MISSING_BJCD'})
            details.append({'place_id':pid,'ufid':ufid,'name_ko':name,'divi':divi,'divi_label':DIVI_LABEL.get(divi,''),'type':typ,'type_label':TYPE_LABEL.get(typ,''),'bjcd':bjcd,'scls':row.get('SCLS',''),'fmta':row.get('FMTA',''),'source_crs':source_crs,'source_id':'ngii_vworld_h0040000','source_snapshot_date':a.snapshot_date})
    pf=['place_id','place_type','hierarchy_level','name_ko','full_name_ko','official_code','parent_place_id','legal_status','valid_from','valid_to','source_id','validity_source_id','source_snapshot_date','latitude','longitude']
    rf=['from_place_id','to_place_id','relation_type','confidence','legal_status','valid_from','valid_to','source_id','source_snapshot_date'];af=['place_id','alias','alias_type','source_id']
    df=['place_id','ufid','name_ko','divi','divi_label','type','type_label','bjcd','scls','fmta','source_crs','source_id','source_snapshot_date'];uf=['place_id','ufid','name_ko','divi','type','bjcd','reason'];iv=['ufid','name','bjcd','reason']
    write_csv(a.out_dir/'places_toponym.csv',places,pf);write_csv(a.out_dir/'toponym_relations.csv',rels,rf);write_csv(a.out_dir/'toponym_aliases.csv',aliases,af);write_csv(a.out_dir/'toponym_details.csv',details,df);write_csv(a.out_dir/'toponym_unmatched_bjcd.csv',unmatched,uf);write_csv(a.out_dir/'toponym_invalid.csv',invalid,iv)
    pc=Counter(r['place_type'] for r in places);tc=Counter(r['type'] for r in details);dc=Counter(r['divi'] for r in details)
    report={'raw_records_seen':raw_seen,'source_records':len(details)+len(invalid)+dup,'selected_records':len(details)+len(invalid)+dup,'excluded_non_natural':excluded_non_natural,'natural_only':a.natural_only,'places':len(places),'relations':len(rels),'aliases':len(aliases),'unmatched_bjcd':len(unmatched),'invalid_records':len(invalid),'duplicate_ufid':dup,'villages':pc.get('VILLAGE',0),'natural_toponyms':pc.get('NATURAL_TOPONYM',0),'by_place_type':dict(sorted(pc.items())),'by_divi':dict(sorted(dc.items())),'by_type':dict(sorted(tc.items())),'exact_bjcd_match_rate':round(len(rels)/len(places),6) if places else 0,'policy':'Exact BJCD relation only; no name or proximity inference'}
    if a.natural_only and raw_seen != report['selected_records'] + excluded_non_natural:
        raise SystemExit(f'Natural-only accounting mismatch: {report}')
    (a.out_dir/'toponym_import_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

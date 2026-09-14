#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from pathlib import Path

def read(path):
    if not path.exists() or path.stat().st_size==0:return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--base-master',type=Path,required=True);ap.add_argument('--station-dir',type=Path);ap.add_argument('--development-dir',type=Path);ap.add_argument('--named-place-dir',type=Path);ap.add_argument('--out-dir',type=Path,required=True);a=ap.parse_args()
    places=read(a.base_master/'places_master.csv');rels=read(a.base_master/'relations_master.csv');aliases=read(a.base_master/'aliases_master.csv');history=read(a.base_master/'place_history.csv')
    details={}
    pfiles=[];rfiles=[];afiles=[]
    if a.station_dir:
        pfiles.append(a.station_dir/'places_station.csv');rfiles.append(a.station_dir/'station_relations.csv');afiles.append(a.station_dir/'station_aliases.csv');details['station_lines']=read(a.station_dir/'station_lines.csv')
    if a.development_dir:
        pfiles.append(a.development_dir/'places_development.csv');rfiles.append(a.development_dir/'development_relations.csv');afiles.append(a.development_dir/'development_aliases.csv');details['development_details']=read(a.development_dir/'development_details.csv')
    if a.named_place_dir:
        pfiles.append(a.named_place_dir/'places_named.csv');rfiles.append(a.named_place_dir/'named_relations.csv');afiles.append(a.named_place_dir/'named_aliases.csv')
    existing={r['place_id'] for r in places}; added=0
    for p in pfiles:
        for r in read(p):
            if r.get('place_id') and r['place_id'] not in existing:places.append(r);existing.add(r['place_id']);added+=1
    seen={(r.get('from_place_id'),r.get('to_place_id'),r.get('relation_type'),r.get('valid_from',''),r.get('valid_to','')) for r in rels};unresolved=[]
    for p in rfiles:
        for r in read(p):
            k=(r.get('from_place_id'),r.get('to_place_id'),r.get('relation_type'),r.get('valid_from',''),r.get('valid_to',''))
            if k in seen:continue
            if r.get('from_place_id') not in existing or r.get('to_place_id') not in existing:unresolved.append(r);continue
            rels.append(r);seen.add(k)
    aseen={(r.get('place_id'),r.get('alias'),r.get('alias_type')) for r in aliases}
    for p in afiles:
        for r in read(p):
            k=(r.get('place_id'),r.get('alias'),r.get('alias_type'))
            if r.get('place_id') in existing and r.get('alias') and k not in aseen:aliases.append(r);aseen.add(k)
    pf=['place_id','place_type','hierarchy_level','name_ko','full_name_ko','official_code','parent_place_id','legal_status','valid_from','valid_to','source_id','validity_source_id','source_snapshot_date','latitude','longitude']
    rf=['from_place_id','to_place_id','relation_type','confidence','legal_status','valid_from','valid_to','source_id','source_snapshot_date']
    af=['place_id','alias','alias_type','source_id']
    write(a.out_dir/'places_geo_master.csv',places,pf);write(a.out_dir/'relations_geo_master.csv',rels,rf);write(a.out_dir/'aliases_geo_master.csv',aliases,af);write(a.out_dir/'unresolved_geo_relations.csv',unresolved,rf)
    report={'base_places':len(read(a.base_master/'places_master.csv')),'places':len(places),'added_places':added,'relations':len(rels),'aliases':len(aliases),'history_events':len(history),'unresolved_geo_relations':len(unresolved),'detail_rows':{k:len(v) for k,v in details.items()}}
    (a.out_dir/'geo_master_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

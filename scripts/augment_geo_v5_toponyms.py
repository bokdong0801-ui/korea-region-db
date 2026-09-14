#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from pathlib import Path

def read(p):
    p=Path(p)
    if not p.exists() or p.stat().st_size==0:return []
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows,fields):
    p=Path(p);p.parent.mkdir(parents=True,exist_ok=True)
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def main():
    ap=argparse.ArgumentParser();ap.add_argument('--v4-dir',type=Path,required=True);ap.add_argument('--toponym-dir',type=Path,required=True);ap.add_argument('--out-dir',type=Path,required=True);a=ap.parse_args();a.out_dir.mkdir(parents=True,exist_ok=True)
    places=read(a.v4_dir/'places_geo_master.csv');rels=read(a.v4_dir/'relations_geo_master.csv');aliases=read(a.v4_dir/'aliases_geo_master.csv')
    base_places=len(places);base_rels=len(rels);base_aliases=len(aliases)
    np=read(a.toponym_dir/'places_toponym.csv');nr=read(a.toponym_dir/'toponym_relations.csv');na=read(a.toponym_dir/'toponym_aliases.csv')
    existing={r['place_id'] for r in places};added=0
    for r in np:
        if r['place_id'] not in existing:places.append(r);existing.add(r['place_id']);added+=1
    seen={(r.get('from_place_id'),r.get('to_place_id'),r.get('relation_type')) for r in rels};unresolved=[];added_rel=0
    for r in nr:
        k=(r.get('from_place_id'),r.get('to_place_id'),r.get('relation_type'))
        if k in seen:continue
        if r.get('from_place_id') not in existing or r.get('to_place_id') not in existing:unresolved.append(r);continue
        rels.append(r);seen.add(k);added_rel+=1
    aseen={(r.get('place_id'),r.get('alias'),r.get('alias_type')) for r in aliases};added_alias=0
    for r in na:
        k=(r.get('place_id'),r.get('alias'),r.get('alias_type'))
        if r.get('place_id') in existing and k not in aseen:aliases.append(r);aseen.add(k);added_alias+=1
    pf=['place_id','place_type','hierarchy_level','name_ko','full_name_ko','official_code','parent_place_id','legal_status','valid_from','valid_to','source_id','validity_source_id','source_snapshot_date','latitude','longitude'];rf=['from_place_id','to_place_id','relation_type','confidence','legal_status','valid_from','valid_to','source_id','source_snapshot_date'];af=['place_id','alias','alias_type','source_id']
    write(a.out_dir/'places_geo_master.csv',places,pf);write(a.out_dir/'relations_geo_master.csv',rels,rf);write(a.out_dir/'aliases_geo_master.csv',aliases,af);write(a.out_dir/'unresolved_geo_relations.csv',unresolved,rf)
    report={'base_v4_places':base_places,'places':len(places),'added_toponyms':added,'base_v4_relations':base_rels,'relations':len(rels),'added_toponym_relations':added_rel,'base_v4_aliases':base_aliases,'aliases':len(aliases),'added_toponym_aliases':added_alias,'unresolved_geo_relations':len(unresolved),'village_count':sum(r.get('place_type')=='VILLAGE' for r in places),'toponym_layer_count':sum(r.get('source_id')=='ngii_vworld_h0040000' for r in places)}
    (a.out_dir/'geo_master_v5_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

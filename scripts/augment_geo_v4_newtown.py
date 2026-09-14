#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json
from pathlib import Path

def read(path:Path):
    if not path.exists() or path.stat().st_size==0:return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def write(path:Path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--v3-geo-dir',type=Path,required=True)
    ap.add_argument('--newtown-dir',type=Path,required=True)
    ap.add_argument('--out-dir',type=Path,required=True)
    a=ap.parse_args()

    places=read(a.v3_geo_dir/'places_geo_master.csv')
    rels=read(a.v3_geo_dir/'relations_geo_master.csv')
    aliases=read(a.v3_geo_dir/'aliases_geo_master.csv')
    unresolved_v3=read(a.v3_geo_dir/'unresolved_geo_relations.csv')
    new_places=read(a.newtown_dir/'places_named.csv')
    new_rels=read(a.newtown_dir/'named_relations.csv')
    new_aliases=read(a.newtown_dir/'named_aliases.csv')

    if unresolved_v3:
        raise SystemExit(f'V3 contains unresolved relations: {len(unresolved_v3)}')
    if len(new_places)!=22 or len(new_rels)!=26:
        raise SystemExit(f'newtown overlay unexpected size: places={len(new_places)} relations={len(new_rels)}')

    existing={r['place_id'] for r in places}
    if any(r['place_id'] in existing for r in new_places):
        dup=[r['place_id'] for r in new_places if r['place_id'] in existing]
        raise SystemExit(f'duplicate newtown place ids: {dup}')

    target_ids=existing|{r['place_id'] for r in new_places}
    unresolved=[]
    for r in new_rels:
        if r.get('from_place_id') not in target_ids or r.get('to_place_id') not in target_ids:
            unresolved.append(r)
    if unresolved:
        raise SystemExit(f'newtown relations unresolved: {len(unresolved)}')

    places.extend(new_places)
    seen={(r.get('from_place_id'),r.get('to_place_id'),r.get('relation_type'),r.get('valid_from',''),r.get('valid_to','')) for r in rels}
    for r in new_rels:
        k=(r.get('from_place_id'),r.get('to_place_id'),r.get('relation_type'),r.get('valid_from',''),r.get('valid_to',''))
        if k not in seen: rels.append(r); seen.add(k)
    aseen={(r.get('place_id'),r.get('alias'),r.get('alias_type')) for r in aliases}
    for r in new_aliases:
        k=(r.get('place_id'),r.get('alias'),r.get('alias_type'))
        if k not in aseen: aliases.append(r); aseen.add(k)

    pf=['place_id','place_type','hierarchy_level','name_ko','full_name_ko','official_code','parent_place_id','legal_status','valid_from','valid_to','source_id','validity_source_id','source_snapshot_date','latitude','longitude']
    rf=['from_place_id','to_place_id','relation_type','confidence','legal_status','valid_from','valid_to','source_id','source_snapshot_date']
    af=['place_id','alias','alias_type','source_id']
    write(a.out_dir/'places_geo_master.csv',places,pf)
    write(a.out_dir/'relations_geo_master.csv',rels,rf)
    write(a.out_dir/'aliases_geo_master.csv',aliases,af)
    write(a.out_dir/'unresolved_geo_relations.csv',[],rf)

    report={
        'base_v3_places':len(places)-len(new_places),
        'places':len(places),'added_newtowns':len(new_places),
        'relations':len(rels),'added_newtown_relations':len(new_rels),
        'aliases':len(aliases),'unresolved_geo_relations':0,
        'newtown_count':sum(r.get('place_type')=='NEWTOWN' for r in places)
    }
    (a.out_dir/'geo_master_v4_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))

if __name__=='__main__':main()

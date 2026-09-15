#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,hashlib
from collections import defaultdict,Counter
from pathlib import Path

ADMIN_TYPES={
    'SIDO','SIGUNGU','LEGAL_EUP','LEGAL_MYEON','LEGAL_DONG','LEGAL_RI',
    'ADMIN_SIDO','ADMIN_SIGUNGU','ADMIN_EUP','ADMIN_MYEON','ADMIN_DONG'
}
VILLAGE_TYPES={'VILLAGE','RURAL_VILLAGE','RURAL_CENTER','RURAL_PLACE'}

def read_csv(path:Path):
    if not path.exists() or path.stat().st_size==0:return []
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def bucket(place_id:str,n:int=128)->int:
    h=5381
    for ch in place_id:
        h=((h<<5)+h)+ord(ch)
    return h%n

def category(t:str)->str:
    if t in ADMIN_TYPES:return 'ADMIN'
    if t=='STATION':return 'STATION'
    if t=='NEWTOWN':return 'NEWTOWN'
    if t in VILLAGE_TYPES:return 'VILLAGE'
    if t=='NATURAL_TOPONYM':return 'TOPONYM'
    if any(k in t for k in ('DISTRICT','DEVELOPMENT','HOUSING','INDUSTRIAL','ECONOMIC','INNOVATION','COMPLEX','SPECIAL_ZONE')):return 'DISTRICT'
    return 'OTHER'

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--geo-dir',type=Path,required=True)
    ap.add_argument('--site-dir',type=Path,required=True)
    ap.add_argument('--source-release',default='V4')
    a=ap.parse_args()
    places=read_csv(a.geo_dir/'places_geo_master.csv')
    rels=read_csv(a.geo_dir/'relations_geo_master.csv')
    aliases=read_csv(a.geo_dir/'aliases_geo_master.csv')
    unresolved=read_csv(a.geo_dir/'unresolved_geo_relations.csv')
    if unresolved: raise SystemExit(f'unresolved relations: {len(unresolved)}')
    if not places: raise SystemExit('empty places master')

    alias_map=defaultdict(list)
    for r in aliases:
        v=(r.get('alias') or '').strip()
        if v and v not in alias_map[r['place_id']]: alias_map[r['place_id']].append(v)

    basic={}
    index=[]
    counts=Counter(); type_counts=Counter()
    current=0
    for r in places:
        pid=r['place_id']; t=r.get('place_type','OTHER'); cat=category(t); counts[cat]+=1; type_counts[t]+=1
        if r.get('legal_status')=='CURRENT': current+=1
        item={
            'id':pid,'n':r.get('name_ko',''),'f':r.get('full_name_ko',''),'t':t,'g':cat,
            'p':r.get('parent_place_id',''),'c':r.get('official_code',''),'s':r.get('legal_status',''),
            'lat':r.get('latitude',''),'lon':r.get('longitude',''),'a':alias_map.get(pid,[]),'b':bucket(pid)
        }
        index.append(item); basic[pid]=item

    rel_by=defaultdict(list)
    for r in rels:
        f=r.get('from_place_id',''); t=r.get('to_place_id',''); rt=r.get('relation_type','')
        if f in basic and t in basic:
            rel_by[f].append({'d':'OUT','r':rt,'id':t,'n':basic[t]['n'],'t':basic[t]['t']})
            rel_by[t].append({'d':'IN','r':rt,'id':f,'n':basic[f]['n'],'t':basic[f]['t']})

    out=a.site_dir/'data'; detail_dir=out/'details'; detail_dir.mkdir(parents=True,exist_ok=True)
    (out/'search-index.json').write_text(json.dumps(index,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    buckets=defaultdict(dict)
    for pid,item in basic.items():
        buckets[item['b']][pid]={'place':item,'relations':rel_by.get(pid,[])}
    for b in range(128):
        (detail_dir/f'{b:03d}.json').write_text(json.dumps(buckets.get(b,{}),ensure_ascii=False,separators=(',',':')),encoding='utf-8')

    meta={
        'site_version':'region-search-v1','source_release':a.source_release,'places':len(places),'current_places':current,
        'relations':len(rels),'aliases':len(aliases),'unresolved_relations':0,'category_counts':dict(sorted(counts.items())),
        'place_type_counts':dict(sorted(type_counts.items())),
        'v5_toponym_ready':counts['VILLAGE']>0 or counts['TOPONYM']>0,
        'generated_files':130
    }
    (out/'meta.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
    manifest={'meta':meta,'sha256_search_index':hashlib.sha256((out/'search-index.json').read_bytes()).hexdigest()}
    (a.site_dir/'REGION_SEARCH_V1_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(meta,ensure_ascii=False,indent=2))

if __name__=='__main__': main()

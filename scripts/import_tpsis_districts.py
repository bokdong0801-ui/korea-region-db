#!/usr/bin/env python3
from __future__ import annotations
import argparse,csv,json,re
from collections import Counter,defaultdict
from pathlib import Path

ENC=('utf-8-sig','cp949','euc-kr','utf-8')
LAW_TYPES={
 'L01':('LAND_DEVELOPMENT_DISTRICT','LAND_DEVELOPMENT'),
 'L04':('URBAN_DEVELOPMENT_DISTRICT','URBAN_DEVELOPMENT'),
 'L23':('PUBLIC_HOUSING_DISTRICT','PUBLIC_HOUSING'),
 'L28':('PRIVATE_RENTAL_DISTRICT','PRIVATE_RENTAL'),
 'L05':('INDUSTRIAL_COMPLEX','INDUSTRIAL_COMPLEX'),
 'L29':('INDUSTRIAL_COMPLEX','INDUSTRIAL_COMPLEX_FAST_TRACK'),
 'L07':('FREE_ECONOMIC_ZONE','FREE_ECONOMIC_ZONE'),
 'L10':('INNOVATION_CITY_DISTRICT','INNOVATION_CITY'),
 'L12':('ENTERPRISE_CITY_DISTRICT','ENTERPRISE_CITY'),
 'L11':('HAPPY_CITY_DISTRICT','HAPPY_CITY'),
 'L22':('RND_SPECIAL_ZONE','RND_SPECIAL_ZONE'),
 'L08':('REGIONAL_DEVELOPMENT_DISTRICT','REGIONAL_DEVELOPMENT'),
 'L14':('RURAL_DEVELOPMENT_DISTRICT','RURAL_DEVELOPMENT'),
 'L25':('WATERFRONT_DISTRICT','WATERFRONT'),
 'L09':('PROVINCIAL_OFFICE_RELOCATION_DISTRICT','PROVINCIAL_OFFICE_RELOCATION'),
 'L21':('JEJU_SPECIAL_DISTRICT','JEJU_SPECIAL'),
 'L15':('COAST_INLAND_DEVELOPMENT_DISTRICT','COAST_INLAND_DEVELOPMENT'),
 'L30':('URBAN_CONVERGENCE_DISTRICT','URBAN_CONVERGENCE'),
}
CORE_CODES={'L01':'LAND_DEVELOPMENT','L04':'URBAN_DEVELOPMENT','L23':'PUBLIC_HOUSING'}

def read_cp949(path:Path):
    b=path.read_bytes()
    for enc in ENC:
        try:return list(csv.DictReader(b.decode(enc).splitlines())),enc
        except UnicodeDecodeError:pass
    raise UnicodeError(path)
def write(path,rows,fields):
    path.parent.mkdir(parents=True,exist_ok=True)
    with path.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(rows)
def digits(v):return re.sub(r'\D','',v or '')
def date8(v):
    x=digits(v);return f'{x[:4]}-{x[4:6]}-{x[6:8]}' if len(x)>=8 else ''
def numhist(v):
    try:return int(v)
    except:return -1

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--raw-dir',type=Path,required=True);ap.add_argument('--master-places',type=Path,required=True);ap.add_argument('--out-dir',type=Path,required=True);ap.add_argument('--snapshot-date',default='2026-08-31');a=ap.parse_args()
    info_path=max(a.raw_dir.glob('BLS5_DSTRC_INFO_*.csv'));hist_path=max(a.raw_dir.glob('BLS5_DSTRC_PROGRS_HIST_*.csv'))
    info,enc1=read_cp949(info_path);hist,enc2=read_cp949(hist_path)
    latest={}
    for r in hist:
        k=r.get('지구지정번호','');h=numhist(r.get('지구이력번호'))
        if k and (k not in latest or h>numhist(latest[k].get('지구이력번호'))):latest[k]=r
    with a.master_places.open(encoding='utf-8-sig',newline='') as f:master={r['place_id']:r for r in csv.DictReader(f)}
    places=[];details=[];aliases=[];rels=[];unmatched=[];by_type=Counter();by_law=Counter();core=Counter();no_hist=[]
    for r in info:
        no=(r.get('지구지정번호') or '').strip();name=(r.get('지구명') or '').strip()
        if not no or not name:continue
        pid=f'district:tpsis:{no}';h=latest.get(no,{})
        lc1=(h.get('법령코드1') or '').strip();ln1=(h.get('법령코드명1') or '').strip();lc2=(h.get('법령코드2') or '').strip();ln2=(h.get('법령코드명2') or '').strip()
        ptype,dtype=LAW_TYPES.get(lc1,('DEVELOPMENT_DISTRICT','OTHER_DEVELOPMENT'))
        core_type=CORE_CODES.get(lc1) or CORE_CODES.get(lc2) or ''
        by_type[dtype]+=1;by_law[(lc1,ln1)]+=1
        if core_type:core[core_type]+=1
        if not h:no_hist.append({'designation_no':no,'name':name})
        places.append({'place_id':pid,'place_type':ptype,'hierarchy_level':'','name_ko':name,'full_name_ko':name,'official_code':no,'parent_place_id':'','legal_status':'CURRENT','valid_from':date8(r.get('지구지정일자')),'valid_to':'','source_id':'tpsis_district_info','validity_source_id':'tpsis_district_info','source_snapshot_date':a.snapshot_date,'latitude':'','longitude':''})
        aliases.append({'place_id':pid,'alias':name,'alias_type':'OFFICIAL_DISTRICT_NAME','source_id':'tpsis_district_info'})
        if h.get('고시사업지구명') and h.get('고시사업지구명')!=name:aliases.append({'place_id':pid,'alias':h['고시사업지구명'],'alias_type':'NOTICE_DISTRICT_NAME','source_id':'tpsis_district_progress_history'})
        loc=digits(r.get('위치코드'))
        target=f'bjd:{loc}' if len(loc)==10 else ''
        if target and target in master:
            rels.append({'from_place_id':pid,'to_place_id':target,'relation_type':'DISTRICT_IN','confidence':'1.0000','source_id':'tpsis_district_info','valid_from':'','valid_to':''})
        else:unmatched.append({'place_id':pid,'designation_no':no,'name':name,'location_code':r.get('위치코드',''),'location_name':r.get('위치명','')})
        details.append({
          'place_id':pid,'designation_no':no,'development_type':dtype,'core_housing_development_type':core_type,
          'public_private_code':r.get('택지구분코드',''),'public_private_name':r.get('택지구분코드명',''),'location_code':loc,'location_name':r.get('위치명',''),
          'area_sqm':r.get('면적',''),'project_cost_krw':r.get('사업비',''),'land_cost_krw':r.get('용지비용',''),'construction_cost_krw':r.get('조성비용',''),'other_cost_krw':r.get('기타비용',''),
          'planned_population':r.get('계획인구수',''),'planned_households':r.get('건설호수',''),'project_period':r.get('사업시행기간',''),'project_start_date':date8(r.get('사업시행시작일자')),'project_end_date':date8(r.get('사업시행종료일자')),'planned_completion_date':date8(r.get('준공예정일자')),
          'designation_date':date8(r.get('지구지정일자')),'designation_change_date':date8(r.get('지구지정변경일자')),'development_plan_approval_date':date8(r.get('개발계획승인일자')),'development_plan_change_date':date8(r.get('개발계획변경일자')),'implementation_plan_approval_date':date8(r.get('실시계획승인일자')),'implementation_plan_change_date':date8(r.get('실시계획변경일자')),'completion_date':date8(r.get('준공일자')),
          'latest_history_no':h.get('지구이력번호',''),'latest_notice_district_name':h.get('고시사업지구명',''),'latest_step_code':h.get('단계코드',''),'latest_step_progress_code':h.get('단계진행코드',''),'law_code_1':lc1,'law_name_1':ln1,'law_code_2':lc2,'law_name_2':ln2,'notice_no':h.get('고시번호',''),'notice_date':date8(h.get('고시일자')),'approval_authority_code':h.get('승인기관코드',''),'approval_authority_name':h.get('승인기관코드명',''),'responsible_authority_code':h.get('담당기관코드',''),'responsible_authority_name':h.get('담당기관코드명',''),'responsible_department':h.get('담당기관부서',''),'source_snapshot_date':a.snapshot_date})
    seen=set();ad=[]
    for x in aliases:
        k=(x['place_id'],x['alias'],x['alias_type'])
        if x['alias'] and k not in seen:seen.add(k);ad.append(x)
    pf=['place_id','place_type','hierarchy_level','name_ko','full_name_ko','official_code','parent_place_id','legal_status','valid_from','valid_to','source_id','validity_source_id','source_snapshot_date','latitude','longitude']
    rf=['from_place_id','to_place_id','relation_type','confidence','source_id','valid_from','valid_to'];af=['place_id','alias','alias_type','source_id']
    df=['place_id','designation_no','development_type','core_housing_development_type','public_private_code','public_private_name','location_code','location_name','area_sqm','project_cost_krw','land_cost_krw','construction_cost_krw','other_cost_krw','planned_population','planned_households','project_period','project_start_date','project_end_date','planned_completion_date','designation_date','designation_change_date','development_plan_approval_date','development_plan_change_date','implementation_plan_approval_date','implementation_plan_change_date','completion_date','latest_history_no','latest_notice_district_name','latest_step_code','latest_step_progress_code','law_code_1','law_name_1','law_code_2','law_name_2','notice_no','notice_date','approval_authority_code','approval_authority_name','responsible_authority_code','responsible_authority_name','responsible_department','source_snapshot_date']
    write(a.out_dir/'places_development.csv',places,pf);write(a.out_dir/'development_details.csv',details,df);write(a.out_dir/'development_aliases.csv',ad,af);write(a.out_dir/'development_relations.csv',rels,rf);write(a.out_dir/'development_unmatched_regions.csv',unmatched,['place_id','designation_no','name','location_code','location_name']);write(a.out_dir/'development_missing_history.csv',no_hist,['designation_no','name'])
    report={'districts':len(places),'progress_history_rows':len(hist),'districts_with_latest_history':len(latest),'missing_latest_history':len(no_hist),'region_relations':len(rels),'unmatched_regions':len(unmatched),'aliases':len(ad),'by_development_type':dict(by_type),'core_housing_types':dict(core),'latest_primary_laws':{f'{k[0]} {k[1]}':v for k,v in by_law.most_common()},'encoding':{'info':enc1,'progress_history':enc2}}
    (a.out_dir/'development_import_report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()

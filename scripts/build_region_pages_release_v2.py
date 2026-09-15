from __future__ import annotations
import csv, json, html, re, shutil, argparse
from pathlib import Path
from collections import defaultdict, Counter

BASE='https://englishpt.kr'
TYPE_LABEL={
'SIDO':'법정 시도','ADMIN_SIDO':'행정 시도','SIGUNGU':'법정 시군구','ADMIN_SIGUNGU':'행정 시군구','LEGAL_EUP':'법정 읍','ADMIN_EUP':'행정 읍','LEGAL_MYEON':'법정 면','ADMIN_MYEON':'행정 면','LEGAL_DONG':'법정동','ADMIN_DONG':'행정동','LEGAL_RI':'법정리','STATION':'철도·도시철도역','NEWTOWN':'신도시','LAND_DEVELOPMENT_DISTRICT':'택지개발지구','URBAN_DEVELOPMENT_DISTRICT':'도시개발지구','PUBLIC_HOUSING_DISTRICT':'공공주택지구','INDUSTRIAL_COMPLEX':'산업단지','PRIVATE_RENTAL_DISTRICT':'민간임대주택지구','FREE_ECONOMIC_ZONE':'경제자유구역','INNOVATION_CITY_DISTRICT':'혁신도시','REGIONAL_DEVELOPMENT_DISTRICT':'지역개발지구','RND_SPECIAL_ZONE':'연구개발특구','ENTERPRISE_CITY_DISTRICT':'기업도시','URBAN_CONVERGENCE_DISTRICT':'도심융합특구','JEJU_SPECIAL_DISTRICT':'제주특별지구','WATERFRONT_DISTRICT':'친수구역','PROVINCIAL_OFFICE_RELOCATION_DISTRICT':'도청이전지구','RURAL_DEVELOPMENT_DISTRICT':'농촌개발지구','COAST_INLAND_DEVELOPMENT_DISTRICT':'해안·내륙권 개발지구','HAPPY_CITY_DISTRICT':'행복도시지구','RURAL_VILLAGE':'농촌마을','RURAL_CENTER':'농촌중심지'}
ADMIN_TYPES={'SIDO','ADMIN_SIDO','SIGUNGU','ADMIN_SIGUNGU','LEGAL_EUP','ADMIN_EUP','LEGAL_MYEON','ADMIN_MYEON','LEGAL_DONG','ADMIN_DONG','LEGAL_RI'}
DISTRICT_TYPES={k for k in TYPE_LABEL if k.endswith('_DISTRICT')}|{'INDUSTRIAL_COMPLEX','FREE_ECONOMIC_ZONE','RND_SPECIAL_ZONE','ENTERPRISE_CITY_DISTRICT','INNOVATION_CITY_DISTRICT'}
TARGET_TYPES=ADMIN_TYPES|{'STATION','NEWTOWN'}|DISTRICT_TYPES
SOURCE_LABEL={'codego_bjd':'법정동 코드 원천','mois_jscode':'행정기관 코드 원천','kric_urban_station':'KRIC 도시철도역 원천','molit_newtown_1_2':'국토교통부 신도시 원천','tpsis_district_info':'택지정보시스템 지구정보','mafra_rural_village_basic':'농림축산식품부 농촌마을 원천'}
HEADER='''<a class="skip-link" href="#main-content">본문 바로가기</a><header class="site-head"><div class="shell head-inner"><div class="brand-wrap"><a class="brand" href="/">잉글리시PT</a><a class="brand-section" href="/region/">지역정보</a></div><nav class="global" aria-label="주요 메뉴"><a href="/search/">통합검색</a><a href="/region/">행정구역</a><a href="/station/">역</a><a href="/newtown/">신도시</a><a href="/district/">개발지구</a></nav><details class="mobile-nav"><summary>메뉴</summary><div><a href="/search/">통합검색</a><a href="/region/">행정구역</a><a href="/station/">역</a><a href="/newtown/">신도시</a><a href="/district/">개발지구</a></div></details></div></header>'''
FOOTER='''<footer class="site-footer"><div class="shell footer-grid"><div><strong>잉글리시PT</strong><p>공식 코드와 관계 데이터를 바탕으로 정리한 대한민국 지역정보입니다.</p></div><nav><a href="/search/">전국 지역검색</a><a href="/region/">행정구역</a><a href="/station/">역</a><a href="/newtown/">신도시</a><a href="/district/">개발지구</a></nav></div></footer>'''

def read_csv(path):
    with path.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def esc(v):return html.escape(str(v or ''))
def safe_id(v):return re.sub(r'[^A-Za-z0-9._-]+','-',v).strip('-')
def brand_title(t):
    s=' | 잉글리시PT'
    return t+s if len(t)+len(s)<=58 else t

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--master',required=True);ap.add_argument('--out',required=True);ap.add_argument('--base-css',required=True);a=ap.parse_args()
    root=Path(a.master);out=Path(a.out)
    if out.exists():shutil.rmtree(out)
    for d in ['assets','region','station','newtown','district','search','sitemaps','manifest']: (out/d).mkdir(parents=True,exist_ok=True)
    places=read_csv(root/'places_geo_master.csv'); relations=read_csv(root/'relations_geo_master.csv'); alias_rows=read_csv(root/'aliases_geo_master.csv')
    P={p['place_id']:p for p in places}; A=defaultdict(list); RF=defaultdict(list); RT=defaultdict(list)
    for x in alias_rows:
        if x.get('alias'):A[x['place_id']].append(x['alias'])
    for r in relations:
        RF[r['from_place_id']].append(r);RT[r['to_place_id']].append(r)
    target=[p for p in places if p['legal_status']=='CURRENT' and p['place_type'] in TARGET_TYPES]; T={p['place_id'] for p in target}
    bytype=defaultdict(list)
    for p in target:bytype[p['place_type']].append(p)
    legal_full={p['full_name_ko'] for p in bytype['LEGAL_DONG']}; sgcodes={p['official_code'] for p in bytype['SIGUNGU']}; administers=Counter(); richri=set()
    for r in relations:
        if r['relation_type']=='ADMINISTERS' and r['legal_status']=='CURRENT':administers[r['from_place_id']]+=1
        if r['relation_type'] in {'VILLAGE_IN','RURAL_CENTER_IN'}:richri.add(r['to_place_id'])
    def name(p):
        n=(p.get('full_name_ko') or p.get('name_ko') or p['place_id']).strip()
        if p['place_type']=='STATION' and n.endswith('역역'):n=n[:-1]
        return n
    def short(p):return (p.get('name_ko') or name(p)).strip()
    def url(p):
        s=safe_id(p['place_id']);t=p['place_type']
        return f'/station/{s}/' if t=='STATION' else f'/newtown/{s}/' if t=='NEWTOWN' else f'/district/{s}/' if t in DISTRICT_TYPES else f'/region/{s}/'
    def meta0(p):
        t=p['place_type'];f=name(p);n=short(p)
        if t=='SIDO':return f'{f} 행정구역 | 시군구·읍면동 지역정보',f'{f}의 행정구역 정보입니다. 공식 지역코드와 하위 시군구, 연결된 법정·행정 구역을 확인합니다.',f'{f} 행정구역'
        if t=='ADMIN_SIDO':return f'{f} 행정기관 | 관할 행정구역',f'{f}의 행정기관 정보입니다. 행정기관 코드와 관할 행정구역 관계를 확인합니다.',f'{f} 행정기관'
        if t=='SIGUNGU':return f'{f} 지역정보 | 법정동·행정동',f'{f}의 지역정보입니다. 공식 지역코드와 상위 시도, 하위 법정구역 및 행정 관할 관계를 확인합니다.',f'{f} 지역정보'
        if t=='ADMIN_SIGUNGU':return f'{f} 행정기관 | 관할 읍면동',f'{f}의 행정기관 정보입니다. 행정기관 코드와 관할 읍면동, 관련 법정구역을 확인합니다.',f'{f} 행정기관'
        if t=='LEGAL_EUP':return f'{f} | 읍·리 지역정보',f'{f}의 법정 읍 정보입니다. 공식 지역코드와 상위 지역, 하위 법정리를 확인합니다.',f
        if t=='ADMIN_EUP':return f'{f} | 행정 읍 정보',f'{f}의 행정 읍 정보입니다. 행정기관 코드와 관할 법정구역을 확인합니다.',f'{f} 행정 읍'
        if t=='LEGAL_MYEON':return f'{f} | 면·리 지역정보',f'{f}의 법정 면 정보입니다. 공식 지역코드와 상위 지역, 하위 법정리를 확인합니다.',f
        if t=='ADMIN_MYEON':return f'{f} | 행정 면 정보',f'{f}의 행정 면 정보입니다. 행정기관 코드와 관할 법정구역을 확인합니다.',f'{f} 행정 면'
        if t=='LEGAL_DONG':return f'{f} | 법정동 정보',f'{f}의 법정동 정보입니다. 법정동 코드와 상위 행정구역, 현재 관할 행정동을 확인합니다.',f'{f} 법정동'
        if t=='ADMIN_DONG':return f'{f} | 행정동 정보',f'{f}의 행정동 정보입니다. 행정기관 코드와 상위 행정구역, 관할 법정동을 확인합니다.',f'{f} 행정동'
        if t=='LEGAL_RI':return f'{f} | 법정리 정보',f'{f}의 법정리 정보입니다. 공식 지역코드와 상위 읍·면, 연결된 공식 농촌마을 정보를 확인합니다.',f
        if t=='STATION':return f'{f} | 위치·지역정보',f'{f}의 위치와 지역정보입니다. 공식 좌표, 소재 행정구역, 역명 별칭과 데이터 출처를 확인합니다.',f
        if t=='NEWTOWN':return f'{n} | 신도시·개발지구 정보',f'{n}의 신도시 정보입니다. 공식 데이터에서 연결된 개발사업과 관련 행정구역을 확인합니다.',n
        return f'{n} | 개발지구 정보',f'{n}의 {TYPE_LABEL.get(t,"개발지구")} 정보입니다. 사업 코드, 유효 시점과 소재 행정구역을 확인합니다.',n
    base_titles=defaultdict(list)
    for p in target:base_titles[meta0(p)[0]].append(p['place_id'])
    collisions={x for v in base_titles.values() if len(v)>1 for x in v}; station_collision={x for v in base_titles.values() if len(v)>1 and all(P[z]['place_type']=='STATION' for z in v) for x in v}
    def meta(p):
        t,d,h=meta0(p)
        if p['place_id'] in collisions:
            ident=p.get('official_code') or safe_id(p['place_id'])[-8:];t=f'{t} · {ident}';d=d.rstrip('.')+f' 데이터 식별값 {ident}을 함께 표시합니다.'
        return brand_title(t),d,h
    def indexable(p):
        t=p['place_type'];pid=p['place_id']
        if t in {'SIDO','SIGUNGU','LEGAL_EUP','LEGAL_MYEON','LEGAL_DONG'}:return True
        if t=='ADMIN_SIGUNGU':return p['official_code'] not in sgcodes
        if t=='ADMIN_DONG':return p['full_name_ko'] not in legal_full or administers[pid]>=2
        if t=='LEGAL_RI':return pid in richri
        if t=='STATION':return pid not in station_collision
        return t=='NEWTOWN' or t in DISTRICT_TYPES
    IDX={p['place_id'] for p in target if indexable(p)}
    def chain(pid):
        z=[];seen=set();cur=P.get(pid)
        while cur and cur.get('parent_place_id') and cur['parent_place_id'] not in seen:
            q=P.get(cur['parent_place_id']);
            if not q:break
            z.append(q);seen.add(q['place_id']);cur=q
        return list(reversed(z))
    def rel(pid,typ,outgoing=True,current=False):
        rr=RF[pid] if outgoing else RT[pid];z=[]
        for r in rr:
            if r['relation_type']!=typ or (current and r['legal_status']!='CURRENT'):continue
            q=P.get(r['to_place_id'] if outgoing else r['from_place_id'])
            if q:z.append(q)
        return z
    def link(q):return f'<a class="entity-link" href="{url(q)}">{esc(name(q))} <span>→</span></a>' if q['place_id'] in T else f'<span class="entity-link is-static">{esc(name(q))}</span>'
    def chips(items):return '<ul class="chip-list">'+''.join(f'<li>{link(q)}</li>' for q in items[:80])+'</ul>' if items else '<p class="empty">표시할 현재 데이터가 없습니다.</p>'
    def facts(p):
        vals=[('유형',TYPE_LABEL.get(p['place_type'],p['place_type'])),('상태','현재')]
        if p.get('official_code'):vals.append(('공식 코드',p['official_code']))
        if p.get('source_snapshot_date'):vals.append(('데이터 기준일',p['source_snapshot_date']))
        if p.get('valid_from'):vals.append(('유효 시작일',p['valid_from']))
        return '<div class="facts">'+''.join(f'<div class="fact"><span>{esc(k)}</span><strong>{esc(v)}</strong></div>' for k,v in vals)+'</div>'
    def modules(p):
        t=p['place_type'];pid=p['place_id'];z=[]
        if t in {'SIDO','SIGUNGU','LEGAL_EUP','LEGAL_MYEON'}:
            kids=[P[r['from_place_id']] for r in RT[pid] if r['relation_type']=='PART_OF' and r['legal_status']=='CURRENT' and r['from_place_id'] in P and P[r['from_place_id']]['legal_status']=='CURRENT'];z.append(('하위 행정구역',chips(kids)))
        elif t.startswith('ADMIN_'):z.append(('현재 관할 법정구역',chips(rel(pid,'ADMINISTERS',True,True))))
        elif t=='LEGAL_DONG':z.append(('현재 행정 관할',chips(rel(pid,'ADMINISTERS',False,True))))
        elif t=='LEGAL_RI':z.append(('공식 농촌마을 연결',chips(rel(pid,'VILLAGE_IN',False)+rel(pid,'RURAL_CENTER_IN',False))))
        elif t=='STATION':
            z.append(('역 소재 지역',chips(rel(pid,'STATION_IN')))
            if p.get('latitude') and p.get('longitude'):z.append(('좌표',f'<div class="coordinate"><div><span>위도</span><strong>{esc(p["latitude"])}</strong></div><div><span>경도</span><strong>{esc(p["longitude"])}</strong></div></div>'))
            if pid in station_collision:z.append(('데이터 중복 주의','<div class="notice">동일 역명이 여러 KRIC 레코드로 존재해 임의 병합하지 않았습니다. 현재 검색색인은 보류합니다.</div>'))
        elif t=='NEWTOWN':
            pr=rel(pid,'NEWTOWN_PROJECT_OF');z.append(('연계 개발사업',chips(pr)));areas=[]
            for q in pr:areas+=rel(q['place_id'],'DISTRICT_IN')
            if areas:z.append(('개발사업 소재 지역',chips(areas)))
        elif t in DISTRICT_TYPES:z.append(('소재 행정구역',chips(rel(pid,'DISTRICT_IN')))
        return ''.join(f'<section class="panel"><div class="panel-head"><span class="kicker">TYPE MODULE</span><h2>{esc(h)}</h2></div>{b}</section>' for h,b in z)
    def crumb(p):
        base='/station/' if p['place_type']=='STATION' else '/newtown/' if p['place_type']=='NEWTOWN' else '/district/' if p['place_type'] in DISTRICT_TYPES else '/region/'
        parts=['<a href="/">홈</a>',f'<a href="{base}">지역정보</a>']
        if p['place_type'] in ADMIN_TYPES:parts += [link(q) for q in chain(p['place_id'])]
        parts.append(f'<span>{esc(short(p))}</span>');return '<nav class="breadcrumb">'+ '<span class="sep">/</span>'.join(parts)+'</nav>'
    def jsonld(p,title):
        items=[{'@type':'ListItem','position':1,'name':'홈','item':BASE+'/'}];pos=2
        base='/station/' if p['place_type']=='STATION' else '/newtown/' if p['place_type']=='NEWTOWN' else '/district/' if p['place_type'] in DISTRICT_TYPES else '/region/'
        items.append({'@type':'ListItem','position':pos,'name':'지역정보','item':BASE+base});pos+=1
        if p['place_type'] in ADMIN_TYPES:
            for q in chain(p['place_id']):items.append({'@type':'ListItem','position':pos,'name':short(q),'item':BASE+url(q)});pos+=1
        items.append({'@type':'ListItem','position':pos,'name':short(p),'item':BASE+url(p)})
        place={'@context':'https://schema.org','@type':'Place','name':name(p),'additionalType':TYPE_LABEL.get(p['place_type'],p['place_type'])}
        if p.get('latitude') and p.get('longitude'):place['geo']={'@type':'GeoCoordinates','latitude':p['latitude'],'longitude':p['longitude']}
        return json.dumps([{'@context':'https://schema.org','@type':'BreadcrumbList','itemListElement':items},place,{'@context':'https://schema.org','@type':'WebPage','name':title,'url':BASE+url(p),'isPartOf':{'@type':'WebSite','name':'잉글리시PT','url':BASE+'/'}}],ensure_ascii=False,separators=(',',':'))
    manifest=[]
    for i,p in enumerate(target,1):
        title,desc,h1=meta(p);robots='index,follow' if p['place_id'] in IDX else 'noindex,follow';canonical=BASE+url(p);parent=P.get(p.get('parent_place_id',''));hier=chain(p['place_id'])+[p]
        alias='<div class="alias-grid">'+''.join(f'<div><strong>{esc(x)}</strong></div>' for x in list(dict.fromkeys(A[p["place_id"]]))[:24])+'</div>' if A[p['place_id']] else '<p class="empty">별도 별칭 데이터가 없습니다.</p>'
        hierarchy='<ol class="hierarchy">'+''.join(f'<li>{link(q)}<small>{esc(TYPE_LABEL.get(q["place_type"],q["place_type"]))}</small></li>' for q in hier)+'</ol>'
        src=SOURCE_LABEL.get(p.get('source_id'),p.get('source_id') or '—')
        doc=f'''<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><meta name="description" content="{esc(desc)}"><meta name="robots" content="{robots}"><link rel="canonical" href="{canonical}"><meta property="og:title" content="{esc(title)}"><meta property="og:description" content="{esc(desc)}"><meta property="og:type" content="website"><meta property="og:url" content="{canonical}"><meta property="og:site_name" content="잉글리시PT"><link rel="stylesheet" href="/assets/region.css"><script type="application/ld+json">{jsonld(p,title)}</script></head><body>{HEADER}<main id="main-content"><div class="shell">{crumb(p)}</div><section class="hero"><div class="shell hero-grid"><div><div class="badges"><span class="badge badge-type">{esc(TYPE_LABEL.get(p['place_type'],p['place_type']))}</span><span class="badge badge-current">CURRENT</span></div><h1>{esc(h1)}</h1><p>{esc(desc)}</p><div class="hero-code"><span>PLACE ID</span><code>{esc(p['place_id'])}</code></div></div><aside class="identity"><span class="identity-label">데이터 식별</span><strong>{esc(short(p))}</strong><dl><div><dt>분류</dt><dd>{esc(p['place_type'])}</dd></div><div><dt>공식 코드</dt><dd>{esc(p.get('official_code') or '—')}</dd></div><div><dt>스냅샷</dt><dd>{esc(p.get('source_snapshot_date') or '—')}</dd></div></dl></aside></div></section><section class="shell overview"><div class="panel"><div class="panel-head"><span class="kicker">OVERVIEW</span><h2>핵심 정보</h2></div>{facts(p)}</div><div class="panel"><div class="panel-head"><span class="kicker">HIERARCHY</span><h2>행정계층</h2></div>{hierarchy}</div></section><div class="shell content-grid"><div class="main-col">{modules(p)}<section class="panel"><div class="panel-head"><span class="kicker">ALIASES</span><h2>명칭·별칭</h2></div>{alias}</section></div><aside class="side-col"><section class="panel sticky-panel"><div class="panel-head"><span class="kicker">SOURCE</span><h2>데이터 출처</h2></div><div class="source-row"><span>주 데이터 원천</span><strong>{esc(src)}</strong></div><div class="source-row"><span>스냅샷</span><strong>{esc(p.get('source_snapshot_date') or '—')}</strong></div><div class="quality"><span>검색노출 정책</span><strong>{robots}</strong></div></section></aside></div><section class="data-note"><div class="shell"><h2>공식 관계 기반 지역정보</h2><p>잉글리시PT의 지역정보 전용 데이터 페이지입니다. V5 master의 공식 코드·관계 데이터만 사용합니다.</p></div></section></main>{FOOTER}</body></html>'''
        fp=out/url(p).strip('/')/'index.html';fp.parent.mkdir(parents=True,exist_ok=True);fp.write_text(doc,encoding='utf-8')
        manifest.append({'place_id':p['place_id'],'place_type':p['place_type'],'name':name(p),'url_path':url(p),'title':title,'description':desc,'h1':h1,'robots':robots,'indexable':p['place_id'] in IDX,'source_snapshot_date':p.get('source_snapshot_date','')})
        if i%5000==0:print('generated',i,'/',len(target))
    # Search records
    def cat(p):return 'STATION' if p['place_type']=='STATION' else 'NEWTOWN' if p['place_type']=='NEWTOWN' else 'DISTRICT' if p['place_type'] in DISTRICT_TYPES else 'ADMIN'
    search=[]
    for p in target:
        aa=list(dict.fromkeys(A[p['place_id']]))[:8];q=' '.join([short(p),name(p),TYPE_LABEL.get(p['place_type'],p['place_type']),*aa]).lower();search.append({'n':short(p),'f':name(p),'t':TYPE_LABEL.get(p['place_type'],p['place_type']),'c':cat(p),'u':url(p),'a':aa,'q':q})
    (out/'assets/search-index.json').write_text(json.dumps(search,ensure_ascii=False,separators=(',',':')),encoding='utf-8')
    searchjs="""(()=>{const $=s=>document.querySelector(s),i=$('#region-search'),r=$('#search-results'),st=$('#search-status'),fs=[...document.querySelectorAll('[data-cat]')];let d=[],c='ALL',tm;const e=s=>(s||'').replace(/[&<>\"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','\"':'&quot;',\"'\":'&#39;'}[m]));function run(){let q=(i.value||'').toLowerCase().trim(),x=d.filter(z=>(c==='ALL'||z.c===c)&&z.q.includes(q)).slice(0,50);st.textContent=`${x.length.toLocaleString()}개 표시`;r.innerHTML=q?(x.length?x.map(z=>`<a class=\"result-card\" href=\"${z.u}\"><div><span class=\"result-type\">${e(z.t)}</span><h2>${e(z.f)}</h2></div><b>보기 →</b></a>`).join(''):'<div class=\"search-empty\">검색 결과가 없습니다.</div>'):'<div class=\"search-empty\">지역명을 입력해보세요.</div>'}i.addEventListener('input',()=>{clearTimeout(tm);tm=setTimeout(run,130)});fs.forEach(f=>f.onclick=()=>{fs.forEach(x=>x.classList.remove('on'));f.classList.add('on');c=f.dataset.cat;run()});fetch('/assets/search-index.json').then(x=>x.json()).then(x=>{d=x;st.textContent=`전체 ${d.length.toLocaleString()}개 검색 가능`;let u=new URL(location.href),q=u.searchParams.get('q');if(q){i.value=q;run()}})})();"""
    (out/'assets/search.js').write_text(searchjs,encoding='utf-8')
    css=Path(a.base_css).read_text(encoding='utf-8')+'''\n.skip-link{position:absolute;left:-9999px}.skip-link:focus{left:12px;top:8px;background:#fff;padding:10px;z-index:100}.brand-wrap{display:flex;align-items:center;gap:10px}.brand-section{font-size:11px;font-weight:850;color:var(--blue);background:var(--soft);padding:5px 9px;border-radius:999px}.mobile-nav{display:none}.site-footer{background:#102842;color:#fff;padding:34px 0}.footer-grid{display:grid;grid-template-columns:1fr auto;gap:28px}.site-footer p,.site-footer a{font-size:12px;color:#c5d4e3}.site-footer nav{display:flex;gap:16px;flex-wrap:wrap}.hub-hero{padding:54px 0 44px;background:linear-gradient(135deg,#102842,#173f6f);color:#fff}.hub-eyebrow{font-size:10px;font-weight:900;letter-spacing:.15em;color:#a7c8ef}.hub-hero h1{font-size:clamp(32px,4vw,48px);margin:10px 0}.hub-hero p{color:#c8d7e7}.primary-link{display:inline-flex;background:var(--blue);color:#fff;padding:11px 18px;border-radius:11px;font-size:13px;font-weight:850}.hub-section,.search-section{padding:34px 0 54px}.sido-grid,.entity-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.sido-grid a,.entity-grid a{background:#fff;border:1px solid var(--line);border-radius:13px;padding:13px}.hub-group{background:#fff;border:1px solid var(--line);border-radius:18px;margin-bottom:12px}.hub-group summary{display:flex;justify-content:space-between;padding:16px 18px;font-weight:850;cursor:pointer}.search-box{background:#fff;border:1px solid var(--line);border-radius:20px;padding:22px;margin-bottom:18px}.search-input-row{display:flex;gap:8px}.search-input-row input{flex:1;padding:13px;border:1px solid var(--line);border-radius:12px}.filter-row{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}.filter-row button{border:1px solid var(--line);background:#fff;border-radius:999px;padding:7px 11px}.filter-row button.on{background:var(--navy);color:#fff}.search-results{display:grid;gap:9px}.result-card{display:flex;justify-content:space-between;align-items:center;background:#fff;border:1px solid var(--line);border-radius:16px;padding:17px 19px}.result-card h2{font-size:16px;margin:3px 0}.result-type,.search-status{font-size:11px;color:var(--muted)}.search-empty{background:#fff;border:1px dashed var(--line);border-radius:18px;padding:38px;text-align:center}.sr-only{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0,0,0,0)}@media(max-width:900px){.global{display:none}.mobile-nav{display:block}.sido-grid,.entity-grid{grid-template-columns:repeat(2,1fr)}.footer-grid{grid-template-columns:1fr}}@media(max-width:560px){.sido-grid,.entity-grid{grid-template-columns:1fr}.search-input-row{display:grid}}'''
    (out/'assets/region.css').write_text(css,encoding='utf-8')
    def head(t,d,path,extra=''):
        tt=brand_title(t);can=BASE+path;ld=json.dumps({'@context':'https://schema.org','@type':'WebPage','name':tt,'url':can,'isPartOf':{'@type':'WebSite','name':'잉글리시PT','url':BASE+'/'}},ensure_ascii=False,separators=(',',':'))
        return f'<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(tt)}</title><meta name="description" content="{esc(d)}"><meta name="robots" content="index,follow"><link rel="canonical" href="{can}"><meta property="og:url" content="{can}"><meta property="og:site_name" content="잉글리시PT"><link rel="stylesheet" href="/assets/region.css">{extra}<script type="application/ld+json">{ld}</script></head><body>{HEADER}'
    def hub_page(path,title,desc,items):
        groups='<div class="entity-grid">'+''.join(f'<a href="{url(p)}"><strong>{esc(name(p))}</strong><small>{esc(TYPE_LABEL.get(p["place_type"],p["place_type"]))}</small></a>' for p in items)+'</div>'
        (out/path/'index.html').write_text(head(title,desc,'/'+path+'/')+f'<main id="main-content"><section class="hub-hero"><div class="shell"><span class="hub-eyebrow">REGION DATA</span><h1>{esc(title)}</h1><p>{esc(desc)}</p></div></section><section class="shell hub-section">{groups}</section></main>{FOOTER}</body></html>',encoding='utf-8')
    hub_page('region','전국 행정구역','시도에서 읍면동·리까지 V5 CURRENT 행정구역을 탐색합니다.',sorted([p for p in target if p['place_type']=='SIDO'],key=name))
    hub_page('station','전국 역 찾기','전국 철도·도시철도 역을 공식 관계 데이터로 찾아봅니다.',sorted(bytype['STATION'],key=name))
    hub_page('newtown','전국 신도시','공식 신도시 프로젝트와 연결된 개발사업 관계를 확인합니다.',sorted(bytype['NEWTOWN'],key=name))
    hub_page('district','전국 개발지구','택지·도시개발·공공주택 등 전국 개발지구를 확인합니다.',sorted([p for p in target if p['place_type'] in DISTRICT_TYPES],key=name))
    sdesc='행정구역·역·신도시·개발지구 26,937개 데이터를 이름과 별칭으로 통합 검색합니다.'
    (out/'search/index.html').write_text(head('전국 지역 통합검색',sdesc,'/search/','<script defer src="/assets/search.js"></script>')+'''<main id="main-content"><section class="hub-hero"><div class="shell"><span class="hub-eyebrow">REGION SEARCH</span><h1>전국 지역 통합검색</h1><p>행정구역·역·신도시·개발지구를 이름과 별칭으로 검색합니다.</p></div></section><section class="shell search-section"><div class="search-box"><label for="region-search">검색어</label><div class="search-input-row"><input id="region-search" type="search" placeholder="예: 청운동, 신사역, 분당신도시"><button type="button" onclick="document.getElementById('region-search').dispatchEvent(new Event('input'))">검색</button></div><div class="filter-row"><button data-cat="ALL" class="on">전체</button><button data-cat="ADMIN">행정구역</button><button data-cat="STATION">역</button><button data-cat="NEWTOWN">신도시</button><button data-cat="DISTRICT">개발지구</button></div><p id="search-status" class="search-status">검색 데이터를 불러오는 중입니다.</p></div><div id="search-results" class="search-results"></div></section></main>'''+FOOTER+'</body></html>',encoding='utf-8')
    # sitemaps and manifest
    cats={'region-admin.xml':[],'region-stations.xml':[],'region-newtowns.xml':[],'region-districts.xml':[]}
    for p in target:
        if p['place_id'] not in IDX:continue
        fn='region-stations.xml' if p['place_type']=='STATION' else 'region-newtowns.xml' if p['place_type']=='NEWTOWN' else 'region-districts.xml' if p['place_type'] in DISTRICT_TYPES else 'region-admin.xml';cats[fn].append(p)
    for fn,items in cats.items():
        lines=['<?xml version="1.0" encoding="UTF-8"?>','<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
        for p in items:
            lm=p.get('source_snapshot_date','');tag=f'<lastmod>{lm}</lastmod>' if re.fullmatch(r'\d{4}-\d{2}-\d{2}',lm or '') else ''
            lines.append(f'<url><loc>{BASE+url(p)}</loc>{tag}</url>')
        lines.append('</urlset>');(out/'sitemaps'/fn).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    with (out/'manifest/pages.csv').open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(manifest[0]));w.writeheader();w.writerows(manifest)
    counts={'ADMIN':sum(1 for p in target if p['place_type'] in ADMIN_TYPES),'STATION':len(bytype['STATION']),'NEWTOWN':len(bytype['NEWTOWN']),'DISTRICT':sum(1 for p in target if p['place_type'] in DISTRICT_TYPES)}
    titles=Counter(m['title'] for m in manifest);paths={m['url_path'] for m in manifest};qa={'pass':len(target)==26937 and counts=={'ADMIN':24491,'STATION':1052,'NEWTOWN':22,'DISTRICT':1372} and len(paths)==26937 and not any(v>1 for v in titles.values()),'entity_pages':len(target),'category_counts':counts,'indexable':len(IDX),'station_collision_noindex':len(station_collision),'duplicate_titles':sum(v>1 for v in titles.values())}
    (out/'manifest/qa.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(qa,ensure_ascii=False,indent=2))
    if not qa['pass']:raise SystemExit('QA failed')
if __name__=='__main__':main()

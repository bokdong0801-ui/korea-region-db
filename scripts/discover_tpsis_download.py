#!/usr/bin/env python3
from __future__ import annotations
import json,urllib.parse,urllib.request
from html.parser import HTMLParser
BASE='https://openapi.jigu.go.kr'; URL=BASE+'/down/detail.do?table=BLS5_DSTRC_INFO'
class P(HTMLParser):
    def __init__(self): super().__init__();self.scripts=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='script' and a.get('src'):self.scripts.append(a['src'])
def req(url,data=None):
    body=urllib.parse.urlencode(data).encode() if data is not None else None
    r=urllib.request.Request(url,data=body,headers={'User-Agent':'Mozilla/5.0','Referer':URL})
    with urllib.request.urlopen(r,timeout=60) as x:return x.read(),dict(x.headers)
def main():
    html=req(URL)[0].decode('utf-8','replace');p=P();p.feed(html)
    print('HTML CONTEXT')
    for i,line in enumerate(html.splitlines(),1):
        if any(q in line for q in ['_PATH','testAt','pageTable','dataTy','hisFileNo','hisStdrDe']):print(i,line[:1000])
    for src in p.scripts:
        u=urllib.parse.urljoin(URL,src);txt=req(u)[0].decode('utf-8','replace')
        for i,line in enumerate(txt.splitlines(),1):
            if '_PATH' in line:print('PATH',u,i,line[:1000])
    print('TITLE JSON')
    raw,_=req(BASE+'/down/title.json',{'table':'BLS5_DSTRC_INFO'});print(raw.decode('utf-8','replace')[:3000])
    print('LIST JSON')
    raw,_=req(BASE+'/api/list.json',{'tNm':'BLS5_DSTRC_INFO','table':'BLS5_DSTRC_INFO','ctprvn':'','ntfcDe':''})
    txt=raw.decode('utf-8','replace');print(txt[:12000])
    try:
        data=json.loads(txt); rows=data.get('list',[]);print('LIST_COUNT',len(rows));
        if rows:print('FIRST_ROW',json.dumps(rows[0],ensure_ascii=False,indent=2))
    except Exception as e:print('JSON_ERR',e)
if __name__=='__main__':main()

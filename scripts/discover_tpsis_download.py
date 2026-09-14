#!/usr/bin/env python3
from __future__ import annotations
import urllib.parse, urllib.request
from html.parser import HTMLParser
URL='https://openapi.jigu.go.kr/down/detail.do?table=BLS5_DSTRC_INFO'
class P(HTMLParser):
    def __init__(self): super().__init__();self.scripts=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='script' and a.get('src'):self.scripts.append(a['src'])
def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=60) as r:return r.read().decode('utf-8','replace')
def main():
    html=fetch(URL);p=P();p.feed(html)
    print('HTML _PATH / hidden context')
    for i,line in enumerate(html.splitlines(),1):
        if any(q in line for q in ['_PATH','pageTable','dataTy','hisFileNo','hisFileTy','hisFileDtNtfc']):print(i,line[:1000])
    for src in p.scripts:
        u=urllib.parse.urljoin(URL,src)
        if not u.endswith('/main/js/detail.js'):continue
        txt=fetch(u);lines=txt.splitlines();print('DETAIL_JS',u,'lines',len(lines))
        for aa,bb in [(55,120),(220,280),(285,345),(380,435)]:
            print(f'--- {aa}:{bb} ---')
            for i in range(aa,min(bb,len(lines))+1):print(f'{i}: {lines[i-1][:1200]}')
if __name__=='__main__':main()

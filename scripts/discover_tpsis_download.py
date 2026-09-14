#!/usr/bin/env python3
from __future__ import annotations
import re, urllib.parse, urllib.request
from html.parser import HTMLParser

URL='https://openapi.jigu.go.kr/down/detail.do?table=BLS5_DSTRC_INFO'
class P(HTMLParser):
    def __init__(self): super().__init__(); self.forms=[];self.inputs=[];self.scripts=[];self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if tag=='form':self.forms.append(a)
        elif tag=='input':self.inputs.append(a)
        elif tag=='script' and a.get('src'):self.scripts.append(a['src'])
        elif tag=='a' and a.get('href'):self.links.append(a)

def fetch(url):
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
    with urllib.request.urlopen(req,timeout=60) as r:return r.read().decode('utf-8','replace')

def main():
    html=fetch(URL);p=P();p.feed(html)
    print('FORMS');
    for x in p.forms:print(x)
    print('\nINPUTS relevant')
    for x in p.inputs:
        z=' '.join(f'{k}={v}' for k,v in x.items())
        if any(q in z.lower() for q in ['file','down','table','job','org','use','data','seq','sn']):print(x)
    print('\nLINKS relevant')
    for x in p.links:
        if any(q in str(x).lower() for q in ['down','file','column','code']):print(x)
    print('\nINLINE matches')
    for pat in [r'[^"\']{0,120}(?:download|downFile|fileDown|down\.do|ajax)[^"\']{0,180}',r'url\s*[:=]\s*["\'][^"\']+["\']']:
        for m in re.finditer(pat,html,re.I): print(m.group(0)[:500])
    print('\nSCRIPTS',len(p.scripts))
    for src in p.scripts:
        u=urllib.parse.urljoin(URL,src);print('SCRIPT',u)
        try: txt=fetch(u)
        except Exception as e: print('ERR',e);continue
        lines=txt.splitlines()
        for i,line in enumerate(lines,1):
            if any(q in line.lower() for q in ['download','downfile','filedown','down.do','dstrc_info','fn_down','file_']): print(f'{i}: {line[:700]}')
if __name__=='__main__':main()

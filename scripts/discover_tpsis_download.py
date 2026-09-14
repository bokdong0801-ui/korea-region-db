#!/usr/bin/env python3
from __future__ import annotations
import re,urllib.parse,urllib.request
BASE='https://openapi.jigu.go.kr'; URL=BASE+'/down/detail.do?table=BLS5_DSTRC_INFO'
def req(url):
    r=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':URL})
    with urllib.request.urlopen(r,timeout=60) as x:return x.read().decode('utf-8','replace')
def main():
    html=req(URL)
    print('TABLE REFERENCES')
    seen=set()
    for m in re.finditer(r'[^\n]{0,300}(?:BLS5_[A-Z0-9_]+)[^\n]{0,300}',html):
        line=m.group(0).strip()
        if line not in seen:seen.add(line);print(line[:1200])
    print('\nDETAIL LINKS')
    for m in re.finditer(r'href=["\']([^"\']*detail\.do\?table=[^"\']+)["\'][^>]*>(.*?)</a>',html,re.I|re.S):
        print(urllib.parse.urljoin(URL,m.group(1)), re.sub('<[^>]+>','',m.group(2)).strip())
if __name__=='__main__':main()

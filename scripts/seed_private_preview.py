#!/usr/bin/env python3
"""Create synthetic local review accounts through the real API. Never sends mail.

Requires a disposable loopback server with DC_DATA_DIR=<temporary directory>,
DC_AUTH_MODE=development and DC_ALLOW_DEMO_SIGNUP=1.
Refuses public hosts, retained preview ports, non-temp stores or non-test users.
Outputs single-use local links; keep them in the private review workspace.
"""
import argparse
import base64
import http.client
import json
import sqlite3
import tempfile
from pathlib import Path
from urllib.parse import urlparse


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--url',required=True)
    parser.add_argument('--data-dir',type=Path,required=True)
    args=parser.parse_args()
    url=urlparse(args.url)
    root=args.data_dir.resolve()
    allowed=(Path('/tmp').resolve(),Path(tempfile.gettempdir()).resolve())
    if url.scheme!='http' or url.hostname not in ('127.0.0.1','localhost') or not url.port or url.port in (18745,18746):
        parser.error('use a separate local HTTP preview')
    if not any(root.is_relative_to(p) and root!=p for p in allowed):
        parser.error('use a disposable data directory under TMPDIR or /tmp')
    with sqlite3.connect(root/'dogcare.db') as c:
        emails=[row[0] for row in c.execute('SELECT email FROM user')]
    if any(not email.endswith('@example.com') for email in emails):
        parser.error('refusing a store containing non-synthetic accounts')

    def call(method,path,payload=None,cookie=None):
        headers={'Content-Type':'application/json'}
        if cookie:
            headers['Cookie']='dc_s='+cookie
            if method!='GET':
                state=call('GET','/api/state',cookie=cookie)[1]
                headers.update({'X-DogCare-Business':str(state['business_id']),'If-Match':'"'+str(state['revision'])+'"'})
        conn=http.client.HTTPConnection(url.hostname,url.port,timeout=15)
        try:
            conn.request(method,path,json.dumps(payload) if payload is not None else None,headers)
            response=conn.getresponse();raw=response.read();out_headers=dict(response.getheaders())
            body=json.loads(raw) if raw else None
            if response.status not in (200,302):raise RuntimeError(f'{method} {path}: {response.status} {body}')
            return response.status,body,out_headers
        finally:conn.close()

    def link(email):
        call('POST','/api/auth/access',{'email':email,'service':'day'})
        for file in sorted((root/'.dev-outbox').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True):
            record=json.loads(file.read_text())
            if record['to']==email:return record['link']
        raise RuntimeError('local outbox did not contain the requested account')

    owner='preview-owner@example.com';client='preview-family@example.com'
    if owner not in emails:call('POST','/api/auth/request',{'email':owner})
    # Bootstrap link is already present if this is the first account.
    links=sorted((root/'.dev-outbox').glob('*.json'),key=lambda p:p.stat().st_mtime,reverse=True)
    if owner in emails:owner_link=link(owner)
    else:owner_link=next(json.loads(f.read_text())['link'] for f in links if json.loads(f.read_text())['to']==owner)
    parsed=urlparse(owner_link)
    _,_,headers=call('GET',parsed.path+'?'+parsed.query)
    cookie=headers['Set-Cookie'].split(';')[0].split('=',1)[1]
    state=call('GET','/api/state',cookie=cookie)[1]
    if not state['daily']['dogs']:
        daily={'version':1,'clients':[{'id':'preview-family','name':'Famille de démonstration'},{'id':'preview-other','name':'Autre famille de démonstration'}],
               'dogs':[{'id':'nino','name':'Nino','clientId':'preview-family'},{'id':'pablo','name':'Pablo','clientId':'preview-other'}],
               'bookings':[],'rates':{'currency':'CHF','day':None,'night':None,'walk':None},'documents':[]}
        call('PUT','/api/daily',{'daily':daily},cookie)
        call('PUT','/api/observations',{'observations':{}},cookie)
        call('POST','/api/portal/members',{'email':client,'role':'client','clientId':'preview-family'},cookie)
        call('POST','/api/portal/updates',{'dogId':'nino','text':'Nino a profité de sa sortie. Nous vous retrouverons ici pour ses prochaines nouvelles.'},cookie)
        call('POST','/api/portal/documents',{'dogId':'nino','label':'Accueil — document de démonstration','renewal':'','name':'accueil-demo.pdf','type':'application/pdf','data':base64.b64encode(b'%PDF-1.4\nSynthetic preview document only.\n%%EOF').decode()},cookie)
    call('PUT','/api/prefs',{'language':'fr'},cookie)
    print(json.dumps({'url':args.url,'syntheticOnly':True,'publicRatesConfigured':False,'owner':link(owner),'client':link(client)},ensure_ascii=False,indent=2))

if __name__=='__main__':main()

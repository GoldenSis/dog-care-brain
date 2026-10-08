"""Real account boundaries with synthetic, isolated businesses and memberships."""
import base64
import hashlib
import uuid

from tests.test_tenant_isolation import ApiServerTestCase, _http


class ClientPortalTest(ApiServerTestCase):
    def setUp(self):
        self.prefix = uuid.uuid4().hex
        self.owner = self.login(self.prefix + '-owner@example.com')
        self.other_owner = self.login(self.prefix + '-other@example.com')
        self.daily = {"version": 1, "clients": [{"id": "one", "name": "First family"}, {"id": "two", "name": "Other family"}],
                      "dogs": [{"id": "nino", "name": "Nino", "clientId": "one"}, {"id": "pablo", "name": "Private Pablo", "clientId": "two"}],
                      "bookings": [], "rates": {"currency": "CHF", "day": 99123, "night": None, "walk": None}, "documents": []}
        status, body, _ = _http(self.port, 'PUT', '/api/daily', {'daily': self.daily}, cookie=self.owner)
        self.assertEqual(status, 200, body)
        self.client_email = self.prefix + '-client@example.com'
        self.member(self.client_email, 'client', 'one')
        self.client = self.login(self.client_email)
        carer_email = self.prefix + '-carer@example.com'
        self.member(carer_email, 'trusted-carer', None)
        self.carer = self.login(carer_email)

    def member(self, email, role, client):
        status, body, _ = _http(self.port, 'POST', '/api/portal/members', {'email': email, 'role': role, 'clientId': client}, cookie=self.owner)
        self.assertEqual(status, 200, body)
        return body

    def upload(self, endpoint, dog='nino'):
        payload = {'dogId': dog, 'label': 'Welcome agreement', 'renewal': '', 'name': 'agreement.pdf', 'type': 'application/pdf',
                   'data': base64.b64encode(b'%PDF-1.4\nsynthetic agreement').decode()}
        status, body, _ = _http(self.port, 'POST', endpoint, payload, cookie=self.owner)
        self.assertEqual(status, 200, body)
        return body

    def test_anonymous_payloads_and_client_projection_exclude_internal_records(self):
        for path in ['/api/state', '/api/dogs', '/api/observations', '/api/invites', '/api/finance', '/api/client-documents/guess']:
            status, body, _ = _http(self.port, 'GET', path)
            self.assertEqual(status, 401, path)
            self.assertNotIn('Private Pablo', str(body))
        for dog, text in [('nino', 'Shared walk news'), ('pablo', 'Other private family news')]:
            status, _, _ = _http(self.port, 'POST', '/api/portal/updates', {'dogId': dog, 'text': text}, cookie=self.owner)
            self.assertEqual(status, 200)
        status, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.client)
        self.assertEqual(status, 200)
        self.assertEqual([x['name'] for x in state['dogs']], ['Nino'])
        self.assertEqual(state['observations'], {})
        self.assertEqual(state['invites'], [])
        self.assertIsNone(state['finance'])
        self.assertIsNone(state['knowledge'])
        self.assertEqual([x['text'] for x in state['portal']['updates']], ['Shared walk news'])
        self.assertEqual(state['portal']['members'], [])
        for private in ['Private Pablo', 'Other family', 'Other private family news', '99123', 'Evening medication']:
            self.assertNotIn(private, str(state))

    def test_client_requests_persist_and_only_own_dogs_can_be_requested(self):
        payload = {'dogId': 'nino', 'service': 'day', 'start': '2026-11-02', 'end': '2026-11-02', 'note': 'A quiet arrival'}
        status, state, _ = _http(self.port, 'POST', '/api/portal/requests', payload, cookie=self.client)
        self.assertEqual(status, 200, state)
        request = state['portal']['requests'][0]
        self.assertEqual(request['status'], 'requested')
        self.assertEqual(state['daily']['bookings'], [])
        for dog in ['pablo', 'guess']:
            status, _, _ = _http(self.port, 'POST', '/api/portal/requests', {**payload, 'dogId': dog}, cookie=self.client)
            self.assertEqual(status, 403)
        _, reloaded, _ = _http(self.port, 'GET', '/api/state', cookie=self.client)
        self.assertEqual(reloaded['portal']['requests'], [request])
        status, _, _ = _http(self.port, 'POST', '/api/portal/decide', {'id': request['id'], 'status': 'accepted'}, cookie=self.other_owner)
        self.assertEqual(status, 400)
        status, owner, _ = _http(self.port, 'POST', '/api/portal/decide', {'id': request['id'], 'status': 'accepted'}, cookie=self.owner)
        self.assertEqual(status, 200, owner)
        self.assertEqual(owner['daily']['bookings'][0]['unitMinor'], 99123)
        _, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.client)
        self.assertEqual(state['portal']['requests'][0]['status'], 'accepted')
        self.assertEqual(state['daily']['bookings'][0]['dogId'], 'nino')

    def test_direct_private_endpoints_and_writes_are_denied(self):
        for path in ['/api/finance', '/api/knowledge', '/api/daily', '/api/invites', '/api/documents/'+'a'*32,
                     '/api/finance-documents/'+'a'*64, '/api/blobs/'+'a'*32+'.webm']:
            status, _, _ = _http(self.port, 'GET', path, cookie=self.client)
            self.assertEqual(status, 403, path)
        for path in ['/api/daily', '/api/observations', '/api/knowledge', '/api/finance', '/api/invites']:
            status, _, _ = _http(self.port, 'PUT', path, {}, cookie=self.client)
            self.assertEqual(status, 403, path)
        for path in ['/api/dogs', '/api/documents', '/api/blobs', '/api/import', '/api/portal/members', '/api/portal/decide', '/api/portal/updates', '/api/portal/documents']:
            status, _, _ = _http(self.port, 'POST', path, {}, cookie=self.client)
            self.assertEqual(status, 403, path)
        status, _, _ = _http(self.port, 'GET', '/api/finance-documents/'+'a'*64, cookie=self.carer)
        self.assertEqual(status, 403)
        status, _, _ = _http(self.port, 'POST', '/api/portal/members', {}, cookie=self.carer)
        self.assertEqual(status, 403)
        status, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.carer)
        self.assertEqual(status, 200)
        self.assertIsNone(state['finance'])
        self.assertTrue(state['observations'])

    def test_only_explicit_client_documents_can_be_downloaded(self):
        internal = self.upload('/api/documents')['daily']['documents'][0]
        a = self.upload('/api/portal/documents')['portal']['documents'][0]
        self.upload('/api/portal/documents', 'pablo')
        status, state, _ = _http(self.port, 'GET', '/api/state', cookie=self.client)
        self.assertEqual(state['daily']['documents'], [])
        self.assertEqual([x['id'] for x in state['portal']['documents']], [a['id']])
        status, raw, _ = _http(self.port, 'GET', '/api/client-documents/'+a['id'], cookie=self.client)
        self.assertEqual(status, 200)
        self.assertIn('synthetic agreement', raw)
        status, _, _ = _http(self.port, 'GET', '/api/documents/'+internal['id'], cookie=self.client)
        self.assertEqual(status, 403)
        status, _, _ = _http(self.port, 'GET', '/api/client-documents/'+a['id'], cookie=self.other_owner)
        self.assertEqual(status, 404)
        other = self.member(self.client_email, 'client', 'two')
        revoked_status, _, _ = _http(self.port, 'GET', '/api/state', cookie=self.client)
        self.assertEqual(revoked_status, 401)
        self.client = self.login(self.client_email)
        status, _, _ = _http(self.port, 'GET', '/api/client-documents/'+a['id'], cookie=self.client)
        self.assertEqual(status, 404)

    def test_public_access_request_does_not_create_an_owner(self):
        email = self.prefix+'-unknown@example.com'
        status, body, _ = _http(self.port, 'POST', '/api/auth/access', {'email': email})
        self.assertEqual((status, body), (200, {'ok': True, 'mailed': False}))
        with self.server_mod.connection() as c:
            self.assertIsNone(c.execute('SELECT id FROM user WHERE email=?', (email,)).fetchone())


    def test_quote_rates_freeze_and_owner_extras_persist_without_finance_access(self):
        request = {'dogId':'nino','service':'day','start':'2026-11-02','end':'2026-11-03','note':''}
        status, state, _ = _http(self.port, 'POST', '/api/portal/requests', request, cookie=self.client)
        self.assertEqual(status, 200, state)
        ident = state['portal']['requests'][0]['id']
        self.assertEqual(state['portal']['quotes'][ident]['totalMinor'], 198246)
        # Configured future rates must never reprice an existing request.
        self.daily['rates']['day'] = 123
        self.assertEqual(_http(self.port,'PUT','/api/daily',{'daily':self.daily},cookie=self.owner)[0],200)
        extra = {'targetId':ident,'id':'','label':'Synthetic optional pickup','unitMinor':1250,'currency':'CHF','quantity':2,'reusable':True}
        for user in (self.client,self.carer):
            self.assertEqual(_http(self.port,'POST','/api/portal/extras',extra,cookie=user)[0],403)
        self.assertEqual(_http(self.port,'POST','/api/portal/extras',extra,cookie=self.other_owner)[0],400)
        status, state, _ = _http(self.port,'POST','/api/portal/extras',extra,cookie=self.owner)
        self.assertEqual(status,200,state)
        q = state['portal']['quotes'][ident]
        self.assertEqual(q['totalMinor'],200746)
        self.assertEqual(len(state['portal']['extras']),1)
        eid = q['extras'][0]['id']
        for bad in ({'currency':'EUR'},{'unitMinor':None},{'unitMinor':-1},{'unitMinor':1.5},{'quantity':0},{'quantity':True},{'id':'unknown'}):
            self.assertEqual(_http(self.port,'POST','/api/portal/extras',{**extra,**bad},cookie=self.owner)[0],400,bad)
        status, state, _ = _http(self.port,'POST','/api/portal/extras',{**extra,'id':eid,'quantity':3,'reusable':False},cookie=self.owner)
        self.assertEqual(status,200,state)
        self.assertEqual(state['portal']['quotes'][ident]['totalMinor'],201996)
        status, state, _ = _http(self.port,'POST','/api/portal/decide',{'id':ident,'status':'accepted'},cookie=self.owner)
        self.assertEqual(status,200,state)
        self.assertEqual(state['daily']['bookings'][0]['unitMinor'],99123)
        _, state, _ = _http(self.port,'GET','/api/state',cookie=self.client)
        self.assertEqual(state['portal']['quotes'][ident]['totalMinor'],201996)
        self.assertEqual(state['portal']['extras'],[])
        self.assertIsNone(state['finance'])
        self.assertEqual(_http(self.port,'POST','/api/portal/extra-remove',{'targetId':ident,'id':eid},cookie=self.client)[0],403)
        self.assertEqual(_http(self.port,'POST','/api/portal/extra-remove',{'targetId':ident,'id':eid},cookie=self.owner)[0],200)
        self.assertEqual(_http(self.port,'GET','/api/state',cookie=self.client)[1]['portal']['quotes'][ident]['totalMinor'],198246)

    def test_unknown_zero_and_explicit_quote_completion(self):
        request = {'dogId':'nino','service':'night','start':'2026-11-02','end':'2026-11-04','note':''}
        status, state, _ = _http(self.port,'POST','/api/portal/requests',request,cookie=self.client)
        self.assertEqual(status,200,state)
        ident=state['portal']['requests'][0]['id']
        self.assertIsNone(state['portal']['quotes'][ident]['totalMinor'])
        extra={'targetId':ident,'id':'','label':'Synthetic free option','unitMinor':0,'currency':'CHF','quantity':1,'reusable':False}
        status,state,_=_http(self.port,'POST','/api/portal/extras',extra,cookie=self.owner)
        self.assertEqual(status,200,state)
        self.assertIsNone(state['portal']['quotes'][ident]['totalMinor'])
        self.assertEqual(state['portal']['quotes'][ident]['extras'][0]['totalMinor'],0)
        price={'targetId':ident,'unitMinor':0,'currency':'CHF'}
        self.assertEqual(_http(self.port,'POST','/api/portal/quote',price,cookie=self.client)[0],403)
        status,state,_=_http(self.port,'POST','/api/portal/quote',price,cookie=self.owner)
        self.assertEqual(status,200,state)
        self.assertEqual(state['portal']['quotes'][ident]['totalMinor'],0)
        self.assertEqual(_http(self.port,'POST','/api/portal/quote',{**price,'unitMinor':99},cookie=self.owner)[0],400)
        # The public projection is empty until explicitly bound to a business.
        from unittest.mock import patch
        with patch.dict('os.environ',{'DC_PUBLIC_BUSINESS':''}):
            self.assertEqual(_http(self.port,'GET','/api/public/services')[1],{'ok':True,'rates':None})
        _,owner,_=_http(self.port,'GET','/api/state',cookie=self.owner)
        with patch.dict('os.environ',{'DC_PUBLIC_BUSINESS':str(owner['business_id'])}):
            public=_http(self.port,'GET','/api/public/services')[1]
            self.assertEqual(public,{'ok':True,'rates':self.daily['rates']})
        query='/api/portal/estimate?dogId=nino&service=day&start=2026-11-02&end=2026-11-03'
        self.assertEqual(_http(self.port,'GET',query,cookie=self.client)[1]['quote']['totalMinor'],198246)
        self.assertEqual(_http(self.port,'GET',query.replace('nino','pablo'),cookie=self.client)[0],403)

    def test_actual_finance_original_and_guessed_dog_ids_remain_private(self):
        _,state,_=_http(self.port,'GET','/api/state',cookie=self.owner)
        value=state['finance']
        blob=b'%PDF-1.4\nPrivate synthetic finance original.\n%%EOF'
        ident=hashlib.sha256(blob).hexdigest()
        value['documents'].append({'id':ident,'sha256':ident,'name':'private.pdf','type':'application/pdf','size':len(blob)})
        status,body,_=_http(self.port,'PUT','/api/finance',{'finance':value,'uploads':[{'id':ident,'data':base64.b64encode(blob).decode()}]},cookie=self.owner)
        self.assertEqual(status,200,body)
        self.assertEqual(_http(self.port,'GET','/api/finance-documents/'+ident,cookie=self.owner)[0],200)
        for member in (self.client,self.carer):
            self.assertEqual(_http(self.port,'GET','/api/finance-documents/'+ident,cookie=member)[0],403)
        self.assertEqual(_http(self.port,'GET','/api/finance-documents/'+ident,cookie=self.other_owner)[0],404)
        for dog in state['dogs']:
            self.assertEqual(_http(self.port,'GET','/api/dogs/'+str(dog['id']),cookie=self.client)[0],404)
        changed={**self.daily,'rates':{**self.daily['rates'],'day':1}}
        self.assertEqual(_http(self.port,'PUT','/api/daily',{'daily':changed},cookie=self.carer)[0],400)

    def test_family_members_share_requests_but_dog_reassignment_does_not_transfer_private_history(self):
        other_family_email=self.prefix+'-second-parent@example.com'
        self.member(other_family_email,'client','one')
        sibling=self.login(other_family_email)
        payload={'dogId':'nino','service':'day','start':'2026-11-02','end':'2026-11-02','note':'Family private request'}
        status,state,_=_http(self.port,'POST','/api/portal/requests',payload,cookie=self.client)
        self.assertEqual(status,200,state)
        ident=state['portal']['requests'][0]['id']
        self.assertEqual(_http(self.port,'GET','/api/state',cookie=sibling)[1]['portal']['requests'][0]['id'],ident)
        self.assertEqual(_http(self.port,'POST','/api/portal/decide',{'id':ident,'status':'accepted'},cookie=self.owner)[0],200)
        doc=self.upload('/api/portal/documents')['portal']['documents'][0]
        self.assertEqual(_http(self.port,'POST','/api/portal/updates',{'dogId':'nino','text':'Private first family news'},cookie=self.owner)[0],200)
        _,owner,_=_http(self.port,'GET','/api/state',cookie=self.owner)
        changed=owner['daily']
        next(d for d in changed['dogs'] if d['id']=='nino')['clientId']='two'
        self.assertEqual(_http(self.port,'PUT','/api/daily',{'daily':changed},cookie=self.owner)[0],200)
        _,saved,_=_http(self.port,'GET','/api/state',cookie=self.owner)
        self.assertEqual(saved['portal']['bookingClients'], {ident:'one'})
        self.member(other_family_email,'client','two')
        sibling=self.login(other_family_email)
        _,other,_=_http(self.port,'GET','/api/state',cookie=sibling)
        self.assertIn('nino',[d['id'] for d in other['daily']['dogs']])
        self.assertEqual(other['daily']['bookings'],[])
        self.assertEqual(other['portal']['requests'],[])
        self.assertEqual(other['portal']['documents'],[])
        self.assertEqual(other['portal']['updates'],[])
        self.assertEqual(other['portal']['quotes'],{})
        self.assertEqual(other['portal']['bookingClients'],{})
        self.assertEqual(_http(self.port,'GET','/api/client-documents/'+doc['id'],cookie=sibling)[0],404)

    def test_carer_bookings_receive_stored_rates_without_price_editing(self):
        import copy
        value = copy.deepcopy(self.daily)
        value['bookings'] = [
            {'id': 'priced', 'dogId': 'nino', 'service': 'day', 'start': '2026-11-02', 'end': '2026-11-02', 'unitMinor': None, 'currency': 'CHF'},
            {'id': 'unknown', 'dogId': 'nino', 'service': 'walk', 'start': '2026-11-02', 'end': '2026-11-02', 'unitMinor': None, 'currency': 'CHF'},
        ]
        forged = copy.deepcopy(value)
        forged['bookings'][0]['unitMinor'] = 99123
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': forged}, cookie=self.carer)[0], 400)
        status, state, _ = _http(self.port, 'PUT', '/api/daily', {'daily': value}, cookie=self.carer)
        self.assertEqual(status, 200, state)
        self.assertEqual([b['unitMinor'] for b in state['daily']['bookings']], [99123, None])
        value = state['daily']
        value['rates']['day'] = 12345
        self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': value}, cookie=self.owner)[0], 200)
        value['bookings'][0]['end'] = '2026-11-03'
        status, state, _ = _http(self.port, 'PUT', '/api/daily', {'daily': value}, cookie=self.carer)
        self.assertEqual(status, 200, state)
        self.assertEqual(state['daily']['bookings'][0]['unitMinor'], 99123)
        for amount in (0, None, 12345):
            forged = copy.deepcopy(state['daily'])
            forged['bookings'][0]['unitMinor'] = amount
            self.assertEqual(_http(self.port, 'PUT', '/api/daily', {'daily': forged}, cookie=self.carer)[0], 400)

"""Accounting snapshot, immutable originals and business/revision isolation."""
import base64
import copy
import hashlib

from tests.test_tenant_isolation import ApiServerTestCase, _http


def draft(kind='purchase'):
    return {'id': 'entry-1', 'kind': kind, 'status': 'draft', 'number': '', 'date': '', 'due': '', 'party': '',
            'address': '', 'issuer': '', 'issuerAddress': '', 'taxId': '', 'currency': '', 'category': 'other',
            'lines': [{'description': '', 'quantity': 1, 'unitMinor': None, 'bookingId': ''}], 'vatMinor': None,
            'note': '', 'sourceId': '', 'region': None, 'raw': '', 'payments': [], 'cancelReason': ''}


class FinanceApiTest(ApiServerTestCase):
    def state(self, sid):
        status, data, _ = _http(self.port, 'GET', '/api/state', cookie=sid)
        self.assertEqual(status, 200)
        return data

    def save(self, sid, value, uploads=None, headers=None):
        return _http(self.port, 'PUT', '/api/finance', {'finance': value, 'uploads': uploads or []}, sid, headers)

    def test_save_original_review_reload_and_isolation(self):
        a, b = self.login('finance-a@example.test'), self.login('finance-b@example.test')
        before = self.state(a)
        value = copy.deepcopy(before['finance'])
        blob = b'%PDF-1.4\nsynthetic document fixture\n%%EOF'
        ident = hashlib.sha256(blob).hexdigest()
        value['documents'].append({'id': ident, 'sha256': ident, 'name': 'fixture.pdf', 'type': 'application/pdf', 'size': len(blob)})
        e = draft()
        e.update(sourceId=ident, region={'page': 1, 'x': 0, 'y': 0, 'width': 1, 'height': 1})
        value['entries'].append(e)
        uploads = [{'id': ident, 'data': base64.b64encode(blob).decode()}]
        self.assertEqual(self.save(a, value, uploads)[0], 200)
        self.assertEqual(self.state(a)['finance'], value)
        for key in ('daily', 'knowledge', 'observations', 'dogs', 'language'):
            self.assertEqual(self.state(a)[key], before[key])
        self.assertEqual(self.state(b)['finance']['entries'], [])
        self.assertEqual(_http(self.port, 'GET', '/api/finance-documents/' + ident, cookie=a)[0], 200)
        self.assertEqual(_http(self.port, 'GET', '/api/finance-documents/' + ident, cookie=b)[0], 404)
        self.assertEqual(_http(self.port, 'GET', '/api/finance-documents/' + ident)[0], 401)
        self.assertEqual(self.save(a, value, uploads)[0], 400)
        self.assertEqual(self.state(a)['finance'], value)

    def test_issued_invoice_and_payment_history_are_preserved(self):
        sid = self.login('finance-invoice@example.test')
        v = self.state(sid)['finance']
        e = draft('sale')
        e.update(status='confirmed', number='F-001', date='2026-10-06', party='Fixture client', address='Client address', issuer='Fixture business', issuerAddress='Business address', currency='CHF')
        e['lines'] = [{'description': 'Day', 'quantity': 2, 'unitMinor': 6500, 'bookingId': ''}]
        v['entries'].append(e)
        self.assertEqual(self.save(sid, v)[0], 200)
        old = self.state(sid)
        for patch in [{'number': 'F-002'}, {'party': 'Changed'}, {'status': 'draft'}, {'lines': []}, {'payments': [{'id': 'overpay', 'date': '2026-10-06', 'amountMinor': 13001, 'note': ''}]}]:
            bad = copy.deepcopy(v)
            bad['entries'][0].update(patch)
            self.assertEqual(self.save(sid, bad)[0], 400)
            self.assertEqual(self.state(sid), old)
        e['payments'].append({'id': 'p1', 'date': '2026-10-06', 'amountMinor': 5000, 'note': 'Bank record entered manually'})
        self.assertEqual(self.save(sid, v)[0], 200)
        self.assertEqual(self.save(sid, old['finance'])[0], 400)

    def test_invalid_upload_and_stale_revision_roll_back(self):
        sid = self.login('finance-stale@example.test')
        old = self.state(sid)
        v = old['finance']
        v['entries'].append(draft())
        headers = {'X-DogCare-Business': str(old['business_id']), 'If-Match': f'"{old["revision"]}"'}
        self.assertEqual(self.save(sid, v, headers=headers)[0], 200)
        v['entries'][0]['note'] = 'stale'
        self.assertEqual(self.save(sid, v, headers=headers)[0], 409)
        self.assertEqual(self.state(sid)['finance']['entries'][0]['note'], '')
        before = self.state(sid)
        bad = copy.deepcopy(before['finance'])
        bad['documents'].append({'id': 'a'*64, 'sha256': 'a'*64, 'name': 'bad.pdf', 'type': 'application/pdf', 'size': 5})
        self.assertEqual(self.save(sid, bad, [{'id': 'a'*64, 'data': 'bm90cGRm'}])[0], 400)
        self.assertEqual(self.state(sid), before)

import copy
import uuid

from tests.test_finance_api import draft
from tests.test_tenant_isolation import ApiServerTestCase, _http


class BookingCancellationTest(ApiServerTestCase):
    def setUp(self):
        prefix = uuid.uuid4().hex
        self.owner = self.login(prefix + '-owner@example.test')
        value = {'version': 1, 'clients': [{'id': 'family', 'name': 'Family'}, {'id': 'other', 'name': 'Other'}],
                 'dogs': [{'id': 'pup', 'name': 'Pup', 'clientId': 'family'}], 'bookings': [],
                 'rates': {'currency': 'CHF', 'day': 2500, 'night': None, 'walk': None}, 'documents': []}
        self.call('PUT', '/api/daily', {'daily': value})
        for role, family in [('client', 'family'), ('client', 'other'), ('trusted-carer', None)]:
            email = prefix + '-' + (family or role) + '@example.test'
            self.call('POST', '/api/portal/members', {'email': email, 'role': role, 'clientId': family})
            setattr(self, family or 'carer', self.login(email))
        state = self.call('POST', '/api/portal/requests', {'dogId': 'pup', 'service': 'day',
                          'start': '2099-10-01', 'end': '2099-10-02', 'note': ''}, cookie=self.family)
        self.ident = state['portal']['requests'][0]['id']
        self.call('POST', '/api/portal/extras', {'targetId': self.ident, 'id': '', 'label': 'Pickup',
                  'unitMinor': 100, 'currency': 'CHF', 'quantity': 2, 'reusable': False})
        self.call('POST', '/api/portal/decide', {'id': self.ident, 'status': 'accepted'})

    def call(self, method, path, payload=None, cookie=None, expected=200, headers=None):
        status, body, _ = _http(self.port, method, path, payload, cookie=cookie or self.owner, headers=headers)
        self.assertEqual(status, expected, body)
        return body

    def state(self):
        return self.call('GET', '/api/state')

    def test_omission_cannot_erase_agreement_before_carer_recreation(self):
        value = self.state()['daily']
        value['rates']['day'] = 9000
        self.call('PUT', '/api/daily', {'daily': value})
        before = self.state()
        value['bookings'] = []
        for cookie in (self.carer, self.owner):
            self.call('PUT', '/api/daily', {'daily': value}, cookie=cookie, expected=400)
            self.assertEqual(self.state(), before)
        value = copy.deepcopy(before['daily'])
        value['bookings'][0]['unitMinor'] = None
        self.call('PUT', '/api/daily', {'daily': value}, cookie=self.carer, expected=400)
        self.assertEqual(self.state(), before)
        for changes in ({'service': 'walk'}, {'dogId': 'another'}):
            value = copy.deepcopy(before['daily'])
            value['dogs'].append({'id': 'another', 'name': 'Another', 'clientId': 'other'})
            value['bookings'][0].update(changes)
            self.call('PUT', '/api/daily', {'daily': value}, cookie=self.carer, expected=400)
            self.assertEqual(self.state(), before)
        value = copy.deepcopy(before['daily'])
        value['bookings'][0]['end'] = '2099-10-03'
        saved = self.call('PUT', '/api/daily', {'daily': value}, cookie=self.carer)
        self.assertEqual(saved['daily']['bookings'][0]['unitMinor'], 2500)

    def test_cancellation_is_owner_only_and_preserves_history(self):
        before = self.state()
        for cookie in (self.carer, self.family, self.other):
            self.call('POST', '/api/portal/cancel-booking', {'id': self.ident}, cookie=cookie, expected=403)
        foreign = self.login(uuid.uuid4().hex + '@example.test')
        self.call('POST', '/api/portal/cancel-booking', {'id': self.ident}, cookie=foreign, expected=400)
        self.call('POST', '/api/portal/cancel-booking', {'id': 'guessed'}, expected=400)
        self.call('POST', '/api/portal/cancel-booking', {'id': self.ident}, headers={
            'X-DogCare-Business': str(before['business_id'] + 1)}, expected=409)
        self.assertEqual(self.state(), before)
        value = copy.deepcopy(before['daily'])
        value['bookings'][0]['status'] = 'cancelled'
        self.call('PUT', '/api/daily', {'daily': value}, expected=400)
        cancelled = self.call('POST', '/api/portal/cancel-booking', {'id': self.ident})
        self.assertEqual(cancelled['daily'], value)
        self.assertEqual(cancelled['finance'], before['finance'])
        self.assertEqual(cancelled['portal']['quotes'], before['portal']['quotes'])
        self.assertEqual(cancelled['portal']['bookingClients'], before['portal']['bookingClients'])
        self.assertEqual(self.state(), cancelled)
        client = self.call('GET', '/api/state', cookie=self.family)
        self.assertEqual(client['daily']['bookings'][0]['status'], 'cancelled')
        self.assertEqual(client['portal']['requests'][0]['status'], 'cancelled')
        self.assertEqual(self.call('GET', '/api/state', cookie=self.other)['daily']['bookings'], [])
        for field, change in [('status', 'planned'), ('end', '2099-10-03'), ('unitMinor', 1)]:
            modified = copy.deepcopy(value)
            modified['bookings'][0][field] = change
            self.call('PUT', '/api/daily', {'daily': modified}, expected=400)
        extra = before['portal']['quotes'][self.ident]['extras'][0]
        self.call('POST', '/api/portal/extra-remove', {'targetId': self.ident, 'id': extra['id']}, expected=400)
        self.assertEqual(self.state(), cancelled)

    def test_cancelled_booking_cannot_create_new_charges_but_saved_payments_remain(self):
        value = self.state()['finance']
        invoice = draft('sale')
        invoice.update(status='confirmed', number='F-1', date='2099-10-01', party='Family',
                       address='Address', issuer='Business', issuerAddress='Address', currency='CHF')
        invoice['lines'][0].update(description='Day', unitMinor=2500, bookingId=self.ident)
        invoice['payments'] = [{'id': 'paid', 'date': '2099-10-01', 'amountMinor': 100, 'note': ''}]
        value['entries'] = [invoice]
        pending = copy.deepcopy(invoice)
        pending.update(id='pending', status='draft', number='F-2', payments=[])
        value['entries'].append(pending)
        self.call('PUT', '/api/finance', {'finance': value, 'uploads': []})
        self.call('POST', '/api/portal/cancel-booking', {'id': self.ident})
        self.assertEqual(self.state()['finance'], value)
        invalid = copy.deepcopy(value)
        invalid['entries'].append({**pending, 'id': 'new'})
        self.call('PUT', '/api/finance', {'finance': invalid, 'uploads': []}, expected=400)
        invalid = copy.deepcopy(value)
        invalid['entries'][1]['status'] = 'confirmed'
        self.call('PUT', '/api/finance', {'finance': invalid, 'uploads': []}, expected=400)
        invoice['payments'].append({'id': 'paid-later', 'date': '2099-10-02', 'amountMinor': 100, 'note': ''})
        self.call('PUT', '/api/finance', {'finance': value, 'uploads': []})
        self.assertEqual(self.state()['finance'], value)

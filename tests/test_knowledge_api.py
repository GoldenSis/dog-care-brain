"""Private experience snapshots retain care data and business/revision boundaries."""
import copy

from tests.test_tenant_isolation import ApiServerTestCase, _http


class KnowledgeApiTest(ApiServerTestCase):
    def state(self, sid):
        status, data, _ = _http(self.port, 'GET', '/api/state', cookie=sid)
        self.assertEqual(status, 200)
        return data

    def draft(self):
        return {'version': 1, 'experiences': [{'id': 'fixture-tip', 'title': 'A calm arrival',
                'body': 'We left space and observed.\nA private experience, not a care rule.',
                'category': 'colleague', 'author': 'Fixture carer',
                'url': 'https://example.org/experience', 'status': 'draft'}]}

    def save(self, sid, value, headers=None):
        return _http(self.port, 'PUT', '/api/knowledge', {'knowledge': value}, sid, headers)

    def test_save_edit_reload_is_private_and_preserves_existing_care(self):
        a = self.login('knowledge-a@example.test')
        b = self.login('knowledge-b@example.test')
        before = self.state(a)
        self.assertEqual(before['knowledge'], {'version': 1, 'experiences': []})
        value = self.draft()
        self.assertEqual(self.save(a, value)[0], 200)
        value['experiences'][0]['body'] = 'Edited private observation'
        self.assertEqual(self.save(a, value)[0], 200)
        after = self.state(a)
        self.assertEqual(after['knowledge'], value)
        for key in ('daily', 'observations', 'dogs', 'invites', 'language'):
            self.assertEqual(after[key], before[key])
        self.assertEqual(self.state(b)['knowledge']['experiences'], [])
        self.assertEqual(self.save(None, value)[0], 401)

    def test_stale_and_switched_business_saves_cannot_overwrite(self):
        a = self.login('knowledge-stale@example.test')
        b = self.login('knowledge-other@example.test')
        state = self.state(a)
        headers = {'X-DogCare-Business': str(state['business_id']), 'If-Match': f'"{state["revision"]}"'}
        self.assertEqual(self.save(a, self.draft(), headers)[0], 200)
        changed = self.draft()
        changed['experiences'][0]['title'] = 'Stale overwrite'
        self.assertEqual(self.save(a, changed, headers)[0], 409)
        self.assertEqual(self.save(b, changed, headers)[0], 409)
        self.assertEqual(self.state(a)['knowledge'], self.draft())
        self.assertEqual(self.state(b)['knowledge']['experiences'], [])

    def test_bad_links_status_and_records_are_rejected_atomically(self):
        sid = self.login('knowledge-invalid@example.test')
        before = self.state(sid)
        for field, value in [('url', 'javascript:alert(1)'), ('url', 'https://user:secret@example.org'),
                             ('url', 'https://example.org/\n'), ('url', 'file:///tmp/x'),
                             ('title', ''), ('body', 'x' * 4001), ('status', 'verified'),
                             ('category', 'clinical'), ('author', []), ('id', '../other')]:
            with self.subTest(field=field, value=value):
                data = self.draft()
                data['experiences'][0][field] = value
                self.assertEqual(self.save(sid, data)[0], 400)
                self.assertEqual(self.state(sid), before)
        duplicate = self.draft()
        duplicate['experiences'].append(copy.deepcopy(duplicate['experiences'][0]))
        self.assertEqual(self.save(sid, duplicate)[0], 400)
        self.assertEqual(self.state(sid), before)

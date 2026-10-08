"""No real SMTP traffic: delivery and failure semantics use a mocked transport."""
import os
from unittest.mock import patch, MagicMock

from tests.test_tenant_isolation import ApiServerTestCase, _http


class LoginDeliveryTest(ApiServerTestCase):
    def smtp(self):
        return patch.dict(os.environ,{'DC_AUTH_MODE':'smtp','DC_ALLOW_DEMO_SIGNUP':'0','DC_PUBLIC_ORIGIN':'https://dogs.example.com',
            'DC_INSECURE_COOKIE':'0','DC_SMTP_HOST':'smtp.example.com','DC_SMTP_USER':'access@example.com','DC_SMTP_PASSWORD':'synthetic-test-only',
            'DC_SMTP_FROM':'Le Bus des Toutous by Plus de Fun <access@example.com>','DC_SMTP_TLS':'ssl'})

    def test_closed_signup_unknown_and_revoked_accounts_do_not_get_links(self):
        import login_delivery
        cookie=self.login('retained-owner@example.com')
        with self.server_mod.connection() as c:
            before=c.execute('SELECT count(*) FROM user').fetchone()[0]
            magic_before=c.execute('SELECT count(*) FROM magic').fetchone()[0]
        with self.smtp(),patch.object(login_delivery,'send') as send:
            status,body,_=_http(self.port,'POST','/api/auth/request',{'email':'unknown-no-owner@example.com'})
            self.assertEqual((status,body),(200,{'ok':True,'mailed':True}))
            send.assert_not_called()
            with self.server_mod.connection() as c:
                self.assertEqual(c.execute('SELECT count(*) FROM user').fetchone()[0],before)
                self.assertEqual(c.execute('SELECT count(*) FROM magic').fetchone()[0],magic_before)
        with patch.dict(os.environ,{'DC_ALLOW_DEMO_SIGNUP':'0'}):
            # Explicit bootstrap creates no fake care history in any mode.
            with self.server_mod.connection() as c:
                uid,bid=self.server_mod.ensure_account(c,'empty-operator-owner@example.com')
                self.assertEqual(c.execute('SELECT language FROM pref WHERE user_id=?',(uid,)).fetchone()[0],'fr')
                self.assertEqual(c.execute('SELECT count(*) FROM dog WHERE business_id=?',(bid,)).fetchone()[0],0)
        self.assertEqual(_http(self.port,'GET','/api/state',cookie=cookie)[0],200)

    def test_smtp_uses_canonical_origin_tls_and_never_an_outbox(self):
        import login_delivery
        self.login('smtp-owner@example.com')
        smtp=MagicMock();smtp.__enter__.return_value=smtp;smtp.send_message.return_value={}
        with self.smtp(),patch('login_delivery.smtplib.SMTP_SSL',return_value=smtp) as factory,patch.object(self.server_mod,'write_outbox') as outbox:
            status,body,_=_http(self.port,'POST','/api/auth/access',{'email':'smtp-owner@example.com','service':'walk'},headers={'Host':'attacker.example'})
            self.assertEqual((status,body),(200,{'ok':True,'mailed':True}))
            factory.assert_called_once()
            self.assertTrue(factory.call_args.kwargs['context'].check_hostname)
            smtp.login.assert_called_once_with('access@example.com','synthetic-test-only')
            message=smtp.send_message.call_args.args[0]
            self.assertIn('https://dogs.example.com/api/auth/verify?',message.get_content())
            self.assertIn('&service=walk',message.get_content())
            self.assertNotIn('attacker.example',message.get_content())
            self.assertIn('by Plus de Fun',message['Subject'])
            self.assertIn('by Plus de Fun',message['From'])
            self.assertTrue(message['Date'])
            self.assertTrue(message['Message-ID'].endswith('@example.com>'))
            self.assertEqual(message['Auto-Submitted'],'auto-generated')
            self.assertEqual(smtp.send_message.call_args.kwargs,{'from_addr':'access@example.com','to_addrs':['smtp-owner@example.com']})
            outbox.assert_not_called()
        with self.smtp(),patch.dict(os.environ,{'DC_SMTP_TLS':'starttls','DC_SMTP_PORT':'2525'}),patch('login_delivery.smtplib.SMTP',return_value=smtp) as factory:
            login_delivery.send(login_delivery.configuration(),'synthetic@example.com','https://dogs.example.com/link')
            self.assertTrue(smtp.starttls.call_args.kwargs['context'].check_hostname)
            factory.assert_called_once_with('smtp.example.com',2525,timeout=15)

    def test_missing_failed_transport_invalidates_token_without_fallback(self):
        import login_delivery
        self.login('smtp-failed@example.com')
        with self.smtp(),patch.dict(os.environ,{'DC_SMTP_PASSWORD':''}),patch.object(self.server_mod,'write_outbox') as outbox:
            self.assertEqual(_http(self.port,'POST','/api/auth/access',{'email':'smtp-failed@example.com'})[0],503)
            outbox.assert_not_called()
        with self.server_mod.connection() as c:
            before=c.execute('SELECT count(*) FROM magic').fetchone()[0]
        with self.smtp(),patch.object(login_delivery,'send',side_effect=login_delivery.DeliveryUnavailable('fixture failure')),patch.object(self.server_mod,'write_outbox') as outbox:
            status,body,_=_http(self.port,'POST','/api/auth/access',{'email':'smtp-failed@example.com'})
            self.assertEqual(status,503)
            self.assertNotIn('fixture failure',str(body))
            outbox.assert_not_called()
        with self.server_mod.connection() as c:
            self.assertEqual(c.execute('SELECT count(*) FROM magic').fetchone()[0],before)
        with patch.dict(os.environ,{'DC_AUTH_MODE':'disabled'}):
            self.assertEqual(_http(self.port,'POST','/api/auth/request',{'email':'nobody@example.com'})[0],503)
        with patch.dict(os.environ,{'DC_AUTH_MODE':'development','DC_HOST':'0.0.0.0'}):
            self.assertEqual(_http(self.port,'POST','/api/auth/request',{'email':'nobody@example.com'})[0],503)

    def test_sender_must_match_authenticated_mailbox(self):
        import login_delivery
        for sender in ('Other <other@example.com>', 'access@example.com\r\nBcc: other@example.com'):
            with self.smtp(),patch.dict(os.environ,{'DC_SMTP_FROM':sender}):
                with self.assertRaises(login_delivery.DeliveryUnavailable):
                    login_delivery.configuration()

    def test_production_attempts_are_bounded_even_for_unknown_addresses(self):
        with self.smtp():
            for _ in range(5):
                self.assertEqual(_http(self.port,'POST','/api/auth/access',{'email':'limited@example.com'})[0],200)
            self.assertEqual(_http(self.port,'POST','/api/auth/access',{'email':'limited@example.com'})[0],429)

    def test_anonymous_home_and_script_aliases_do_not_ship_workspace_demo_payload(self):
        status,body,_=_http(self.port,'GET','/')
        self.assertEqual(status,200)
        self.assertNotIn('src="app.js"',body)
        self.assertNotIn('data-page="business"',body)
        for path in ('/app.js','/%2e/app.js','//app.js'):
            self.assertEqual(_http(self.port,'GET',path)[0],401)

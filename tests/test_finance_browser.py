"""Owned synthetic accounting journeys in account and browser-local modes."""
import base64
import io
import json
import threading
import zipfile
from functools import partial
from http.server import ThreadingHTTPServer
from xml.etree import ElementTree as ET

from tests.test_browser_acceptance import BrowserFixture, QuietStaticHandler, ROOT


class FinanceBrowserTest(BrowserFixture):
    async def asyncSetUp(self):
        self.sid = self.login(f'finance-{self._testMethodName}@example.test')
        await super().asyncSetUp()
        await self.page.click('#main-nav [data-page="business"]')

    async def snapshot(self):
        return await self.page.evaluate('FinanceStore.snapshot()')

    async def save_entry(self, status='draft'):
        await self.page.click(f'#finance-form button[value="{status}"]')
        await self.page.wait_for_function('!savePending')
        self.assertTrue(await self.page.locator('#finance-error').is_hidden())

    async def test_invoice_extra_payment_reload_and_excel_archive(self):
        await self.page.click('#finance-new-sale')
        for name, value in {'number': 'F-001', 'party': '=SUM(A1)', 'address': 'Client fixture address', 'issuer': 'Fixture business', 'issuerAddress': 'Business fixture address', 'description-0': 'Day care', 'quantity-0': '2', 'unit-0': '65,00'}.items():
            await self.page.fill(f'#finance-form [name="{name}"]', value)
        await self.page.click('#finance-add-line')
        await self.page.fill('[name="description-1"]', 'Extra fixture')
        await self.page.fill('[name="unit-1"]', '5')
        await self.page.fill('[name="note"]', '  Literal café 🐾\n=1+1  ')
        await self.save_entry('confirmed')
        data = await self.snapshot()
        self.assertEqual(data['entries'][0]['status'], 'confirmed')
        self.assertEqual(data['entries'][0]['note'], '  Literal café 🐾\n=1+1  ')
        self.assertTrue(await self.page.locator('#finance-form [name="number"]').is_disabled())
        await self.page.fill('#finance-payment [name="amount"]', '35.00')
        await self.page.click('#finance-payment button')
        await self.page.wait_for_function('!savePending')
        await self.page.reload()
        await self.wait_ready()
        await self.page.click('[data-page="business"]')
        data = await self.snapshot()
        self.assertEqual(len(data['entries']), 1)
        self.assertEqual(data['entries'][0]['payments'][0]['amountMinor'], 3500)
        async with self.page.expect_download() as info:
            await self.page.click('#finance-export')
        download = await info.value
        with zipfile.ZipFile(await download.path()) as archive:
            records = json.loads(archive.read('records.json'))
            self.assertEqual(records, data)
            with zipfile.ZipFile(io.BytesIO(archive.read('comptabilite.xlsx'))) as workbook:
                ns = {'m': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
                sheet = ET.fromstring(workbook.read('xl/worksheets/sheet1.xml'))
                self.assertEqual(sheet.find('.//m:c[@r="F2"]/m:is/m:t', ns).text, '=SUM(A1)')
                self.assertEqual(sheet.find('.//m:c[@r="I2"]/m:v', ns).text, '135')
                self.assertEqual(sheet.find('.//m:c[@r="K2"]/m:v', ns).text, '35')
                self.assertEqual(sheet.find('.//m:c[@r="L2"]/m:v', ns).text, '100')
                self.assertEqual(sheet.findall('.//m:f', ns), [])
        self.assertEqual(self.console_errors, [])
        self.assertEqual(self.page_errors, [])

    async def receipt_photo(self):
        data = await self.page.evaluate('''() => {
          const c=document.createElement('canvas');c.width=1500;c.height=1000;const x=c.getContext('2d');x.fillStyle='#383838';x.fillRect(0,0,1500,1000);
          for(const [left,party,number,total] of [[50,'FOURNISSEUR ALPHA','F-101','42.50'],[800,'FOURNISSEUR BETA','F-102','18.20']]){
            x.fillStyle='white';x.fillRect(left,50,650,900);x.fillStyle='black';x.font='bold 32px sans-serif';
            [party,'Facture '+number,'06.10.2026','Croquettes pour chiens','TOTAL CHF '+total].forEach((text,i)=>x.fillText(text,left+35,150+i*130));
          }return c.toDataURL('image/png').split(',')[1];
        }''')
        return base64.b64decode(data)

    async def test_two_receipts_local_ocr_review_original_reload_duplicate_and_export(self):
        await self.page.select_option('#language-picker', 'fr')
        photo = await self.receipt_photo()
        requests = []
        self.page.on('request', lambda req: requests.append(req.url))
        await self.page.click('#finance-import')
        await self.page.set_input_files('#finance-files', {'name': 'synthetic-two-receipts.png', 'mimeType': 'image/png', 'buffer': photo})
        await self.page.wait_for_selector('#finance-recognize')
        self.assertEqual(await self.page.locator('.finance-region').count(), 2)
        await self.page.click('#finance-recognize')
        await self.page.wait_for_function('!savePending', timeout=120000)
        data = await self.snapshot()
        self.assertEqual(len(data['entries']), 2)
        self.assertEqual(sorted(e['lines'][0]['unitMinor'] for e in data['entries']), [1820, 4250])
        self.assertEqual({e['status'] for e in data['entries']}, {'draft'})
        self.assertEqual({e['currency'] for e in data['entries']}, {'CHF'})
        self.assertEqual(len(data['documents']), 1)
        self.assertTrue(all(url.startswith(self.url + '/') or url.startswith('blob:') for url in requests), requests)
        await self.capture_evidence(f'finance-photo-review-{self.api_mode}.png')
        await self.page.click('[data-finance-edit] >> nth=0')
        await self.save_entry('confirmed')
        await self.page.reload()
        await self.wait_ready()
        await self.page.click('[data-page="business"]')
        data = await self.snapshot()
        self.assertEqual(sum(e['status']=='confirmed' for e in data['entries']), 1)
        async with self.page.expect_download() as info:
            await self.page.click('#finance-export')
        with zipfile.ZipFile(await (await info.value).path()) as archive:
            original = [n for n in archive.namelist() if n.startswith('originals/')]
            self.assertEqual(len(original), 1)
            self.assertEqual(archive.read(original[0]), photo)
        await self.page.click('#finance-import')
        await self.page.set_input_files('#finance-files', {'name': 'same-photo.png', 'mimeType': 'image/png', 'buffer': photo})
        await self.page.wait_for_function('!savePending')
        self.assertIn('déjà enregistré', await self.page.inner_text('#finance-error'))
        self.assertEqual(await self.snapshot(), data)
        self.assertEqual(self.console_errors, [])
        self.assertEqual(self.page_errors, [])

    async def test_localized_views_routes_and_unsaved_literal_draft(self):
        await self.page.click('#finance-new-expense')
        await self.page.fill('[name="party"]', 'Day care')
        await self.page.fill('[name="description-0"]', 'All good')
        await self.page.fill('[name="unit-0"]', '12.30')
        for locale in ('fr', 'en', 'it', 'de', 'es'):
            await self.page.select_option('#language-picker', locale)
            await self.page.click('[data-page="dashboard"]')
            await self.page.click('[data-page="business"]')
            self.assertEqual(await self.page.input_value('[name="party"]'), 'Day care')
            self.assertEqual(await self.page.input_value('[name="description-0"]'), 'All good')
        await self.save_entry()
        await self.page.click('#finance-back')
        await self.page.select_option('#language-picker', 'fr')
        for width,height in ((1440,900),(1024,768),(390,844)):
            await self.page.set_viewport_size({'width':width,'height':height})
            for tab in ('journal','invoices','expenses','review','rates'):
                await self.page.click(f'[data-finance-tab="{tab}"]')
                self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth>innerWidth'))
            await self.page.click('[data-finance-tab="journal"]')
            await self.capture_evidence(f'finance-fr-{width}-{self.api_mode}.png')
            pages = await self.page.locator('#main-nav [data-page]').evaluate_all('(nodes)=>nodes.map(n=>n.dataset.page)')
            self.assertEqual(len(pages), 12)
            for page in pages:
                await self.page.click(f'#main-nav [data-page="{page}"]')
                self.assertEqual(await self.page.get_attribute(f'[data-page="{page}"]','aria-current'),'page')
            await self.page.click('[data-page="business"]')
        self.assertEqual(self.console_errors, [])
        self.assertEqual(self.page_errors, [])


class StaticFinanceBrowserTest(FinanceBrowserTest):
    api_mode = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.static_server = ThreadingHTTPServer(('127.0.0.1', 0), partial(QuietStaticHandler, directory=str(ROOT)))
        cls.static_thread = threading.Thread(target=cls.static_server.serve_forever, daemon=True)
        cls.static_thread.start()
        cls.url = f'http://127.0.0.1:{cls.static_server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.static_server.shutdown()
        cls.static_server.server_close()
        cls.static_thread.join()
        super().tearDownClass()

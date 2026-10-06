"""Owned synthetic accounting journeys in account and browser-local modes."""
import base64
import hashlib
import io
import json
import os
from pathlib import Path
import threading
import zipfile
from functools import partial
from http.server import ThreadingHTTPServer
from xml.etree import ElementTree as ET

from tests.test_browser_acceptance import BrowserFixture, QuietStaticHandler, ROOT


class FinanceBrowserTest(BrowserFixture):
    async def test_multipage_intake_bounds_canvas_lifetime_and_retains_regions(self):
        objects = [b'<< /Type /Catalog /Pages 2 0 R >>',
                   ('<< /Type /Pages /Kids [' + ' '.join(f'{3+i} 0 R' for i in range(20)) + '] /Count 20 >>').encode()]
        objects.extend([b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 1200 1600] /Resources << >> >>'])
        objects.extend([b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 80 100] /Resources << >> >>'] * 19)
        pdf = b'%PDF-1.4\n'
        offsets = [0]
        for i, obj in enumerate(objects, 1):
            offsets.append(len(pdf))
            pdf += f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n'
        start = len(pdf)
        pdf += f'xref\n0 {len(offsets)}\n0000000000 65535 f \n'.encode()
        pdf += b''.join(f'{v:010d} 00000 n \n'.encode() for v in offsets[1:])
        pdf += f'trailer\n<< /Size {len(offsets)} /Root 1 0 R >>\nstartxref\n{start}\n%%EOF'.encode()
        originals = [pdf + f'\n% original {i}'.encode() for i in range(10)]
        await self.page.evaluate('''() => {
          const canvases=[],create=document.createElement.bind(document);
          let peak=0;
          const measure=()=>{const pixels=canvases.reduce((sum,c)=>sum+c.width*c.height,0);peak=Math.max(peak,pixels);return {pixels,peak};};
          document.createElement=function(name,...args){const el=create(name,...args);if(name==='canvas'){canvases.push(el);measure();}return el;};
          for(const key of ['width','height']){
            const descriptor=Object.getOwnPropertyDescriptor(HTMLCanvasElement.prototype,key);
            Object.defineProperty(HTMLCanvasElement.prototype,key,{...descriptor,set(value){descriptor.set.call(this,value);if(!canvases.includes(this))canvases.push(this);measure();}});
          }
          window.canvasMemory=()=>({...measure(),large:canvases.filter(c=>c.width>720||c.height>720).length});
        }''')
        await self.page.click('#finance-import')
        await self.page.set_input_files('#finance-files', [
            {'name': f'pages-{i}.pdf', 'mimeType': 'application/pdf', 'buffer': blob}
            for i, blob in enumerate(originals)])
        await self.page.wait_for_function('!savePending')
        self.assertEqual(await self.page.locator('[data-finance-canvas]').count(), 200)
        self.assertLessEqual((await self.page.evaluate('canvasMemory()'))['peak'], 4 * 720 * 720)
        await self.page.locator('.finance-regions summary').first.click()
        await self.page.locator('[data-region="0,0,width"]').fill('50')
        await self.page.locator('[data-region="0,0,width"]').press('Tab')
        await self.page.locator('[data-finance-canvas="199"]').scroll_into_view_if_needed()
        await self.page.wait_for_function("document.querySelector('[data-finance-canvas=\"199\"]').width > 0")
        self.assertLessEqual((await self.page.evaluate('canvasMemory()'))['peak'], 4 * 720 * 720)
        await self.page.click('[data-page="dogs"]')
        await self.page.wait_for_function('canvasMemory().pixels === 0')
        await self.page.click('[data-page="business"]')
        self.assertEqual(await self.page.locator('[data-region="0,0,width"]').input_value(), '50')
        await self.page.route('**/tesseract.js/tesseract.min.js', lambda route: route.fulfill(
            content_type='text/javascript', body='''window.Tesseract={createWorker:async()=>({
              recognize:async(canvas,{rectangle})=>{if(!window.failedOCR){window.failedOCR=true;throw Error('Recognition unavailable');}window.readRegions??=[];window.readRegions.push(rectangle.width/canvas.width);return {data:{text:'Supplier\\nTotal CHF 1.00'}};},
              terminate:async()=>{window.terminatedOCR=true;}
            })};'''))
        await self.page.click('#finance-recognize')
        await self.page.wait_for_function('!savePending')
        self.assertTrue(await self.page.locator('#finance-error').is_visible())
        self.assertTrue(await self.page.evaluate('terminatedOCR'))
        self.assertEqual((await self.page.evaluate('canvasMemory()'))['large'], 0)
        self.assertEqual((await self.snapshot())['documents'], [])
        self.assertEqual(await self.page.locator('[data-region="0,0,width"]').input_value(), '50')
        await self.page.click('#finance-recognize')
        await self.page.wait_for_function('!savePending', timeout=60000)
        self.assertEqual(await self.page.evaluate('readRegions.length'), 200)
        self.assertEqual(await self.page.evaluate('readRegions[0]'), .5)
        await self.page.wait_for_function('canvasMemory().pixels === 0')
        self.assertLessEqual((await self.page.evaluate('canvasMemory()'))['peak'], 2400 * 2400)
        saved = await self.snapshot()
        self.assertEqual(len(saved['entries']), 200)
        self.assertEqual(saved['entries'][0]['region']['width'], .5)
        self.assertEqual([e['region']['page'] for e in saved['entries']], list(range(1, 21)) * 10)
        for meta, original in zip(saved['documents'], originals):
            actual = await self.page.evaluate('''async id => Array.from(new Uint8Array(
              await (await FinanceStore.document(id)).arrayBuffer()))''', meta['id'])
            self.assertEqual(bytes(actual), original)
        await self.page.click('#finance-import')
        await self.page.set_input_files('#finance-files', {
            'name': 'discard.pdf', 'mimeType': 'application/pdf', 'buffer': pdf})
        await self.page.wait_for_function("!savePending && [...document.querySelectorAll('[data-finance-canvas]')].some(c=>c.width>0)")
        await self.page.click('#finance-discard-intake')
        await self.page.wait_for_function('canvasMemory().pixels === 0')
        self.assertEqual(await self.snapshot(), saved)
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])

    async def test_unrelated_edits_preserve_literal_finance_text(self):
        entry = await self.page.evaluate("FinanceModel.draft('literal-record', 'sale')")
        literal = '\r\n  =Text\twith\rline\nbreaks\r\n'
        for key in ('number', 'party', 'issuer', 'taxId', 'address', 'issuerAddress', 'note'):
            entry[key] = literal + key
        entry['lines'][0]['description'] = literal + 'description'
        await self.seed_finance([entry])
        await self.page.click('[data-finance-edit="literal-record"]')
        await self.page.fill('[name="quantity-0"]', '2')
        await self.page.click('#finance-add-line')
        await self.page.click('[data-finance-remove="1"]')
        for locale in ('fr', 'it', 'de', 'es', 'en'):
            await self.page.select_option('#language-picker', locale)
            await self.page.wait_for_function('!savePending')
        await self.page.click('[data-page="dogs"]')
        await self.page.click('[data-page="business"]')
        await self.page.check('[name="keepProfile"]')
        await self.save_entry()
        entry['lines'][0]['quantity'] = 2
        saved = await self.snapshot()
        self.assertEqual(saved['entries'], [entry])
        self.assertEqual(saved['profile'], {'name': entry['issuer'], 'address': entry['issuerAddress'], 'taxId': entry['taxId']})
        await self.page.fill('[name="party"]', 'Edited party')
        await self.page.fill('[name="note"]', 'Edited\nnote')
        await self.page.fill('[name="description-0"]', 'Edited line')
        await self.save_entry()
        entry['party'], entry['note'], entry['lines'][0]['description'] = 'Edited party', 'Edited\nnote', 'Edited line'
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual((await self.snapshot())['entries'], [entry])
        self.assertEqual(self.console_errors, [])

    async def test_retained_original_metadata_survives_save_rejection_and_reload(self):
        self.assertTrue(await self.page.evaluate('''async () => {
          const next=FinanceStore.snapshot(),files=new Map();
          for(let i=0;i<2;i++){
            const blob=new Blob(['%PDF-1.4\\nOriginal '+i+'\\n%%EOF'],{type:'application/pdf'});
            const hash=await crypto.subtle.digest('SHA-256',await blob.arrayBuffer());
            const id=Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');
            next.documents.push({id,name:'=Original café '+i+'.pdf',type:blob.type,size:blob.size,sha256:id});
            files.set(id,blob);
          }
          const entry=FinanceModel.draft('source-linked');entry.sourceId=next.documents[0].id;
          next.entries.push(entry);
          return FinanceStore.save(next,files);
        }'''))
        saved = await self.snapshot()
        for change in ('name', 'type', 'size', 'identity', 'missing', 'key-order'):
            with self.subTest(change=change):
                self.assertFalse(await self.page.evaluate('''change => {
                  const next=FinanceStore.snapshot(),doc=next.documents[1];
                  if(change==='name')doc.name='Renamed.pdf';
                  if(change==='type')doc.type='image/png';
                  if(change==='size')doc.size++;
                  if(change==='identity')doc.id=doc.sha256='f'.repeat(64);
                  if(change==='missing')next.documents.pop();
                  if(change==='key-order')next.documents[1]=Object.fromEntries(Object.entries(doc).reverse());
                  return FinanceStore.save(next);
                }''', change))
                self.assertEqual(await self.snapshot(), saved)
        self.assertTrue(await self.page.evaluate('''() => {
          const next=FinanceStore.snapshot();next.documents.reverse();next.entries[0].note='Reviewed';
          return FinanceStore.save(next);
        }'''))
        saved['documents'].reverse()
        saved['entries'][0]['note'] = 'Reviewed'
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        for i, doc in enumerate(reversed(saved['documents'])):
            original = await self.page.evaluate('''async id => Array.from(new Uint8Array(
              await (await FinanceStore.document(id)).arrayBuffer()))''', doc['id'])
            self.assertEqual(bytes(original), f'%PDF-1.4\nOriginal {i}\n%%EOF'.encode())
        self.assertEqual(self.console_errors, [])

    async def test_confirmed_conversion_requires_successful_invoice_issuance(self):
        entries = await self.page.evaluate('''() => ['expense','purchase','extra','paid-extra'].map(id=>{
          const e=FinanceModel.draft(id,id==='paid-extra'?'extra':id);
          Object.assign(e,{status:'confirmed',date:'2026-10-06',party:'Supplier',currency:'JPY'});
          e.lines[0]={description:'Literal =1+1',quantity:1,unitMinor:1050,bookingId:''};
          if(id==='paid-extra')e.payments=[{id:'payment',date:e.date,amountMinor:250,note:'Original payment'}];
          return e;
        })''')
        await self.seed_finance(entries)
        for entry in entries:
            await self.page.click(f'[data-finance-edit="{entry["id"]}"]')
            await self.page.select_option('#finance-form [name="kind"]', 'sale')
            self.assertTrue(await self.page.locator('#finance-form [name="number"]').is_enabled())
            self.assertEqual(await self.page.locator('#finance-print').count(), 0)
            for locale in ('fr', 'en', 'it', 'de', 'es'):
                await self.page.select_option('#language-picker', locale)
                await self.page.wait_for_function('!savePending')
                draft = await self.page.evaluate("FinanceUI.text('draft')")
                self.assertIn(draft, await self.page.inner_text('#finance-form h2'))
            await self.page.click('#finance-form button[value="confirmed"]')
            self.assertEqual((await self.snapshot())['entries'][entries.index(entry)], entry)
            self.assertEqual(await self.page.locator('#finance-print').count(), 0)
            for name, value in {'number': 'CONVERT-'+entry['id'], 'address': 'Client address', 'issuer': 'Business', 'issuerAddress': 'Business address'}.items():
                await self.page.fill(f'#finance-form [name="{name}"]', value)
            if self.api_mode:
                await self.page.route('**/api/finance', lambda route: route.fulfill(status=200, json={'ok': False}))
            else:
                await self.page.evaluate('''() => {
                  window.originalPut=IDBObjectStore.prototype.put;
                  IDBObjectStore.prototype.put=function(...args){if(this.name==='state')throw new DOMException('Quota','QuotaExceededError');return originalPut.apply(this,args);};
                }''')
            await self.page.click('#finance-form button[value="confirmed"]')
            await self.page.wait_for_function('!savePending')
            self.assertTrue(await self.page.locator('#finance-error').is_visible())
            self.assertEqual((await self.snapshot())['entries'][entries.index(entry)], entry)
            self.assertEqual(await self.page.locator('#finance-print').count(), 0)
            await self.page.click('[data-finance-tab="rates"]')
            await self.page.click('#finance-resume')
            self.assertEqual(await self.page.input_value('#finance-form [name="number"]'), 'CONVERT-'+entry['id'])
            if self.api_mode:
                await self.page.unroute('**/api/finance')
            else:
                await self.page.evaluate('() => { IDBObjectStore.prototype.put=window.originalPut; }')
            await self.save_entry('confirmed')
            self.assertTrue(await self.page.locator('#finance-form [name="number"]').is_disabled())
            self.assertTrue(await self.page.locator('#finance-print').is_visible())
            saved = (await self.snapshot())['entries'][entries.index(entry)]
            self.assertEqual(saved['status'], 'confirmed')
            self.assertEqual(saved['kind'], 'sale')
            self.assertEqual(saved['payments'], entry['payments'])
            self.assertEqual(saved['currency'], entry['currency'])
            await self.page.click('#finance-back')
            await self.page.click('[data-finance-tab="journal"]')
        saved = await self.snapshot()
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])

    async def test_failed_issuance_allows_incomplete_draft_save(self):
        await self.page.click('#finance-new-sale')
        await self.page.fill('[name="description-0"]', 'Still under review')
        await self.page.click('#finance-form button[value="confirmed"]')
        self.assertEqual((await self.snapshot())['entries'], [])
        await self.save_entry('draft')
        saved = await self.snapshot()
        self.assertEqual(len(saved['entries']), 1)
        entry = saved['entries'][0]
        self.assertEqual(entry['status'], 'draft')
        self.assertEqual(entry['party'], '')
        self.assertEqual(entry['number'], '')
        self.assertIsNone(entry['lines'][0]['unitMinor'])
        self.assertEqual(entry['lines'][0]['description'], 'Still under review')
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])

    async def test_saved_bookings_and_changed_rates_remain_available(self):
        await self.page.click('[data-finance-tab="rates"]')
        await self.page.select_option('#rates-form [name="currency"]', 'EUR')
        await self.page.fill('#rates-form [name="day"]', '10.50')
        await self.page.click('#rates-form button')
        await self.page.wait_for_function("document.querySelector('#rates-saved').textContent.length > 0 && !savePending")
        await self.page.click('[data-page="schedule"]')
        await self.page.click('#new-booking')
        await self.page.fill('#booking-form [name="client"]', 'Booking client')
        await self.page.select_option('#booking-form [name="service"]', 'day')
        await self.page.fill('#booking-form [name="start"]', '2026-10-06')
        await self.page.fill('#booking-form [name="end"]', '2026-10-07')
        await self.page.click('#booking-form [type="submit"]')
        await self.page.wait_for_selector('#booking-form', state='detached')
        await self.page.click('[data-page="business"]')
        await self.page.click('#finance-new-sale')
        self.assertEqual(await self.page.input_value('[name="currency"]'), 'EUR')
        await self.page.click('#finance-booking')
        await self.page.locator('#finance-booking + select').select_option(index=1)
        self.assertEqual(await self.page.input_value('[name="party"]'), 'Booking client')
        self.assertEqual(await self.page.input_value('[name="unit-0"]'), '10.50')
        self.assertEqual(await self.page.input_value('[name="quantity-0"]'), '2')
        await self.save_entry()
        saved = (await self.snapshot())['entries'][0]
        self.assertTrue(saved['lines'][0]['bookingId'])
        self.assertEqual(saved['currency'], 'EUR')
        self.assertEqual(self.console_errors, [])

    async def test_invalid_daily_data_keeps_manual_accounting_usable(self):
        malformed = [None, {}, {'rates': {'currency': 'CHF'}}, {'rates': {'currency': 'BAD!'}},
                     {'version': 1, 'clients': [], 'dogs': [], 'bookings': [None],
                      'rates': {'currency': 'CHF', 'walk': None, 'day': None, 'night': None}, 'documents': []}]
        for index, value in enumerate(malformed):
            with self.subTest(daily=value):
                if self.api_mode:
                    async def bad_daily(route):
                        response = await route.fetch()
                        body = await response.json()
                        body['daily'] = value
                        await route.fulfill(response=response, json=body)
                    await self.page.route('**/api/state', bad_daily)
                else:
                    await self.page.evaluate("value=>localStorage.setItem('dogcare-daily-v1',JSON.stringify(value))", value)
                await self.page.reload()
                await self.wait_ready()
                await self.page.click('[data-page="business"]')
                for kind in ('sale', 'expense'):
                    await self.page.click('#finance-new-sale' if kind == 'sale' else '#finance-new-expense')
                    self.assertEqual(await self.page.locator('#finance-form').count(), 1)
                    self.assertEqual(await self.page.input_value('[name="currency"]'), '')
                    for locale in ('fr', 'en', 'it', 'de', 'es'):
                        await self.page.select_option('#language-picker', locale)
                        await self.page.wait_for_function('!savePending')
                        self.assertTrue(await self.page.locator('#finance-bookings-unavailable').is_visible())
                        self.assertEqual(await self.page.inner_text('#finance-bookings-unavailable'),
                                         await self.page.evaluate("FinanceUI.text('bookingsUnavailable')"))
                        self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth>innerWidth'))
                        if index == 0 and kind == 'sale' and locale == 'fr':
                            await self.capture_evidence(f'finance-manual-unavailable-{self.api_mode}.png')
                    if kind == 'sale':
                        self.assertTrue(await self.page.locator('#finance-booking').is_disabled())
                    await self.page.fill('[name="party"]', f'Manual {kind} {index}')
                    await self.page.fill('[name="currency"]', 'EUR')
                    await self.page.fill('[name="description-0"]', 'Manual line')
                    await self.page.fill('[name="unit-0"]', '10.50')
                    await self.save_entry('draft' if kind == 'sale' else 'confirmed')
                    await self.page.click('#finance-back')
                await self.page.click('[data-finance-tab="rates"]')
                await self.page.click('[data-page="capture"]')
                self.assertTrue(await self.page.locator('#observation').is_visible())
                if self.api_mode:
                    await self.page.unroute('**/api/state')
                else:
                    self.assertEqual(await self.page.evaluate("localStorage.getItem('dogcare-daily-v1')"),
                                     json.dumps(value, separators=(',', ':')))
        self.assertEqual(len((await self.snapshot())['entries']), len(malformed)*2)
        self.assertEqual(self.console_errors, [])

    async def seed_finance(self, entries):
        self.assertTrue(await self.page.evaluate('''entries => {
          const next=FinanceStore.snapshot();next.entries.push(...entries);return FinanceStore.save(next);
        }''', entries))
        await self.page.click('[data-page="dashboard"]')
        await self.page.click('[data-page="business"]')

    async def test_paid_editor_preserves_payment_currency_and_direction(self):
        entry = await self.page.evaluate('''() => {
          const e=FinanceModel.draft('paid-expense','expense');Object.assign(e,{status:'confirmed',date:'2026-10-06',party:'Fixture',currency:'CHF'});
          e.lines[0]={description:'Receipt',quantity:1,unitMinor:1050,bookingId:''};
          e.payments=[{id:'p1',date:e.date,amountMinor:500,note:'Original payment'}];return e;
        }''')
        await self.seed_finance([entry])
        await self.page.click('[data-finance-edit]')
        self.assertTrue(await self.page.locator('#finance-form [name="currency"]').is_disabled())
        self.assertTrue(await self.page.locator('#finance-form [name="kind"] option[value="extra"]').evaluate('(option)=>option.disabled'))
        await self.page.select_option('#finance-form [name="kind"]', 'purchase')
        await self.page.fill('#finance-form [name="note"]', 'Corrected note')
        await self.save_entry('confirmed')
        await self.page.reload()
        await self.wait_ready()
        saved = (await self.snapshot())['entries'][0]
        self.assertEqual(saved['currency'], 'CHF')
        self.assertEqual(saved['kind'], 'purchase')
        self.assertEqual(saved['payments'], entry['payments'])

    async def test_hundredths_and_unknown_print_lines_in_every_locale(self):
        entries = await self.page.evaluate('''() => {
          const e=FinanceModel.draft('invoice-jpy','sale');Object.assign(e,{status:'confirmed',number:'JPY-1',date:'2026-10-06',party:'Client',address:'Address',issuer:'Business',issuerAddress:'Address',currency:'JPY'});
          e.lines[0]={description:'Literal line',quantity:1,unitMinor:1050,bookingId:''};e.payments=[{id:'p',date:e.date,amountMinor:250,note:''}];
          const unknown=FinanceModel.draft('unknown','sale');Object.assign(unknown,{status:'cancelled',currency:'JPY',cancelReason:'Unpriced draft'});return [e,unknown];
        }''')
        await self.seed_finance(entries)
        await self.page.evaluate('''() => {
          const append=document.body.append;document.body.append=function(...nodes){for(const n of nodes)if(n.matches?.('.finance-print-frame'))n.onload=()=>{};return append.apply(this,nodes);};
        }''')
        for locale in ('fr', 'en', 'it', 'de', 'es'):
            await self.page.select_option('#language-picker', locale)
            await self.page.wait_for_function('!savePending')
            expected = await self.page.evaluate("() => new Intl.NumberFormat(formatLocale(Intl.NumberFormat),{style:'currency',currency:'JPY',minimumFractionDigits:2,maximumFractionDigits:2}).format(10.5)")
            await self.page.click('[data-finance-tab="journal"]')
            self.assertIn(expected, await self.page.inner_text('[data-finance-entry="invoice-jpy"]'))
            await self.page.click('[data-finance-edit="invoice-jpy"]')
            await self.page.click('#finance-print')
            frame = self.page.frame_locator('.finance-print-frame').last
            self.assertEqual(await frame.locator('table tr:nth-child(2) td:nth-child(4)').inner_text(), expected)
            await self.page.locator('.finance-print-frame').evaluate_all('(frames)=>frames.forEach(f=>f.remove())')
            await self.page.click('#finance-back')
            await self.page.click('[data-finance-edit="unknown"]')
            await self.page.click('#finance-print')
            unknown = await self.page.evaluate("FinanceUI.text('unknown')")
            frame = self.page.frame_locator('.finance-print-frame').last
            self.assertEqual(await frame.locator('table tr:nth-child(2) td:nth-child(4)').inner_text(), unknown)
            await self.page.locator('.finance-print-frame').evaluate_all('(frames)=>frames.forEach(f=>f.remove())')
            await self.page.click('#finance-back')
        self.assertEqual(self.console_errors, [])

    async def test_retained_editor_total_tracks_current_inputs_after_redraw(self):
        entries = await self.page.evaluate('''() => ['sale','expense'].map(kind=>{
          const e=FinanceModel.draft('preview-'+kind,kind);e.currency='CHF';
          e.lines[0]={description:'Original line',quantity:1,unitMinor:1050,bookingId:''};return e;
        })''')
        await self.seed_finance(entries)
        saved = await self.snapshot()
        for entry in entries:
            await self.page.click(f'[data-finance-edit="{entry["id"]}"]')
            await self.page.fill('[name="description-0"]', 'Today =1+1')
            await self.page.fill('[name="unit-0"]', '20,50')
            await self.page.fill('#finance-form [name="currency"]', 'EUR')
            expected = await self.page.evaluate("() => new Intl.NumberFormat(formatLocale(Intl.NumberFormat),{style:'currency',currency:'EUR',minimumFractionDigits:2,maximumFractionDigits:2}).format(20.5)")
            self.assertEqual(await self.page.inner_text('#finance-total'), expected)
            await self.page.click('[data-finance-tab="rates"]')
            await self.page.click('#finance-resume')
            self.assertEqual(await self.page.inner_text('#finance-total'), expected)
            for locale in ('fr', 'en', 'it', 'de', 'es'):
                await self.page.select_option('#language-picker', locale)
                await self.page.wait_for_function('!savePending')
                expected = await self.page.evaluate("() => new Intl.NumberFormat(formatLocale(Intl.NumberFormat),{style:'currency',currency:'EUR',minimumFractionDigits:2,maximumFractionDigits:2}).format(20.5)")
                self.assertEqual(await self.page.inner_text('#finance-total'), expected)
                self.assertEqual(await self.page.input_value('[name="unit-0"]'), '20,50')
                self.assertEqual(await self.page.input_value('#finance-form [name="currency"]'), 'EUR')
                self.assertEqual(await self.page.input_value('[name="description-0"]'), 'Today =1+1')
                if locale == 'fr':
                    await self.capture_evidence(f'finance-retained-preview-{entry["kind"]}-{self.api_mode}.png')
            self.assertEqual(await self.snapshot(), saved)
            self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth>innerWidth'))
            await self.page.click('[data-finance-tab="journal"]')
            await self.page.click('#finance-discard')
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])

    async def test_retained_editor_total_stays_unknown_for_invalid_inputs(self):
        entry = await self.page.evaluate('''() => {
          const e=FinanceModel.draft('invalid-preview','sale');e.currency='CHF';
          e.lines[0].unitMinor=1050;return e;
        }''')
        await self.seed_finance([entry])
        saved = await self.snapshot()
        await self.page.click('[data-finance-edit="invalid-preview"]')
        cases = [('quantity-0', value) for value in ('', '0', '-1', '1.5', '10001')]
        cases += [('unit-0', value) for value in ('', '20,unfinished', '20,', '1000000.01')]
        cases += [('currency', value) for value in ('', 'EU', 'eur')]
        for index, (name, value) in enumerate(cases):
            with self.subTest(name=name, value=value):
                for field, valid in {'quantity-0': '2', 'unit-0': '20.50', 'currency': 'JPY'}.items():
                    await self.page.fill(f'#finance-form [name="{field}"]', valid)
                await self.page.fill(f'#finance-form [name="{name}"]', value)
                self.assertEqual(await self.page.inner_text('#finance-total'), await self.page.evaluate("FinanceUI.text('unknown')"))
                await self.page.click('[data-finance-tab="rates"]')
                await self.page.click('#finance-resume')
                self.assertEqual(await self.page.inner_text('#finance-total'), await self.page.evaluate("FinanceUI.text('unknown')"))
                await self.page.select_option('#language-picker', ('fr', 'en', 'it', 'de', 'es')[index % 5])
                await self.page.wait_for_function('!savePending')
                self.assertEqual(await self.page.inner_text('#finance-total'), await self.page.evaluate("FinanceUI.text('unknown')"))
                self.assertEqual(await self.page.input_value(f'#finance-form [name="{name}"]'), value)
        self.assertEqual(await self.snapshot(), saved)
        self.assertEqual(self.console_errors, [])

    async def test_internal_navigation_preserves_editor_until_explicit_discard(self):
        entries = await self.page.evaluate("[FinanceModel.draft('existing-a'),FinanceModel.draft('existing-b')]")
        await self.seed_finance(entries)
        await self.page.click('#finance-new-sale')
        await self.page.fill('[name="party"]', 'Unsaved client')
        await self.page.fill('[name="unit-0"]', '12,unfinished')
        await self.page.click('#finance-add-line')
        await self.page.fill('[name="description-1"]', 'Unsaved extra')
        for locale in ('fr', 'en', 'it', 'de', 'es'):
            await self.page.select_option('#language-picker', locale)
            await self.page.wait_for_function('!savePending')
            for tab in ('rates', 'review', 'invoices', 'expenses', 'journal'):
                await self.page.click(f'[data-finance-tab="{tab}"]')
                self.assertEqual(await self.page.locator('#finance-form').count(), 0)
                await self.page.click('#finance-resume')
                self.assertEqual(await self.page.input_value('[name="party"]'), 'Unsaved client')
                self.assertEqual(await self.page.input_value('[name="unit-0"]'), '12,unfinished')
                self.assertEqual(await self.page.input_value('[name="description-1"]'), 'Unsaved extra')
        await self.page.click('#finance-back')
        await self.page.click('[data-finance-edit="existing-a"]')
        await self.page.click('#finance-resume')
        self.assertEqual(await self.page.input_value('[name="party"]'), 'Unsaved client')
        await self.page.click('#finance-back')
        await self.page.click('#finance-new-expense')
        await self.page.click('#finance-resume')
        self.assertEqual(await self.page.input_value('[name="party"]'), 'Unsaved client')
        await self.page.click('[data-page="dashboard"]')
        await self.page.click('[data-finance-rates]')
        self.assertTrue(await self.page.locator('#rates-form').is_visible())
        await self.page.click('#finance-resume')
        self.assertEqual(await self.page.input_value('[name="party"]'), 'Unsaved client')
        await self.page.click('#finance-back')
        await self.page.click('#finance-discard')
        await self.page.click('#finance-new-expense')
        self.assertEqual(await self.page.input_value('[name="party"]'), '')
        self.assertEqual((await self.snapshot())['entries'], entries)
        self.assertFalse(await self.page.evaluate('document.documentElement.scrollWidth>innerWidth'))
        self.assertEqual(self.console_errors, [])

    async def test_failed_finance_hydration_blocks_export_and_recovers(self):
        await self.page.click('#finance-new-expense')
        await self.page.fill('[name="party"]', 'Stored record')
        await self.save_entry()
        saved = await self.snapshot()
        if self.api_mode:
            async def bad_finance(route):
                response = await route.fetch()
                body = await response.json()
                body.pop('finance')
                await route.fulfill(response=response, json=body)
            await self.page.route('**/api/state', bad_finance)
        else:
            await self.page.add_init_script('''
              const original=IDBObjectStore.prototype.get;
              IDBObjectStore.prototype.get=function(...args){if(this.name==='state'&&!window.allowFinanceRead)throw Error('Read unavailable');return original.apply(this,args);};
            ''')
        await self.page.reload()
        await self.wait_ready()
        await self.page.click('[data-page="business"]')
        self.assertEqual(await self.page.locator('.finance-table').count(), 0)
        self.assertTrue(await self.page.locator('#finance-export').is_disabled())
        self.assertFalse(await self.page.evaluate('FinanceStore.save(FinanceModel.empty())'))
        await self.page.click('[data-page="capture"]')
        self.assertTrue(await self.page.locator('#observation').is_visible())
        await self.page.click('[data-page="business"]')
        if self.api_mode:
            await self.page.unroute('**/api/state')
        else:
            await self.page.evaluate('window.allowFinanceRead=true')
        await self.page.click('#finance-retry')
        await self.page.wait_for_function('!savePending')
        self.assertEqual(await self.snapshot(), saved)
        self.assertTrue(await self.page.locator('#finance-export').is_enabled())
        self.assertEqual(await self.page.locator('[data-finance-entry]').count(), 1)

    async def test_unreadable_pdf_retains_original_for_manual_review(self):
        original = b'%PDF-1.4\nreader failure fixture\n%%EOF'
        await self.page.click('#finance-import')
        await self.page.set_input_files('#finance-files', {'name': 'unreadable.pdf', 'mimeType': 'application/pdf', 'buffer': original})
        await self.page.wait_for_function('!savePending')
        self.assertTrue(await self.page.locator('#finance-manual-import').is_visible())
        self.assertTrue(await self.page.locator('#finance-recognize').is_disabled())
        await self.page.click('#finance-manual-import')
        await self.page.wait_for_function('!savePending')
        saved = await self.snapshot()
        self.assertEqual(len(saved['documents']), 1)
        self.assertEqual(len(saved['entries']), 1)
        self.assertIsNone(saved['entries'][0]['region'])
        self.assertIsNone(saved['entries'][0]['lines'][0]['unitMinor'])
        await self.page.click('[data-finance-edit]')
        await self.page.fill('[name="party"]', 'Manual supplier')
        await self.save_entry()
        await self.page.reload()
        await self.wait_ready()
        data = await self.snapshot()
        self.assertEqual(data['entries'][0]['party'], 'Manual supplier')
        blob = await self.page.evaluate('''async id => Array.from(new Uint8Array(await (await FinanceStore.document(id)).arrayBuffer()))''', data['documents'][0]['id'])
        self.assertEqual(bytes(blob), original)

    async def test_payment_inputs_stay_with_record_and_wait_for_saved_edits(self):
        entries = await self.page.evaluate('''() => ['a','b'].map(id=>{
          const e=FinanceModel.draft(id,'expense');Object.assign(e,{status:'confirmed',date:'2026-10-06',party:id,currency:'CHF'});
          e.lines[0]={description:'Expense',quantity:1,unitMinor:1050,bookingId:''};return e;
        })''')
        await self.seed_finance(entries)
        await self.page.click('[data-finance-edit="a"]')
        await self.page.fill('#finance-payment [name="amount"]', '2.50')
        await self.page.fill('#finance-payment [name="note"]', 'Pending payment A')
        await self.page.click('#finance-back')
        await self.page.click('[data-finance-edit="b"]')
        await self.page.click('#finance-resume')
        self.assertEqual(await self.page.input_value('#finance-form [name="party"]'), 'a')
        self.assertEqual(await self.page.input_value('#finance-payment [name="note"]'), 'Pending payment A')
        await self.page.fill('#finance-form [name="currency"]', 'EUR')
        await self.page.select_option('#finance-form [name="kind"]', 'extra')
        self.assertTrue(await self.page.locator('#finance-payment button').is_disabled())
        await self.page.locator('#finance-payment').evaluate("form=>form.dispatchEvent(new Event('submit',{cancelable:true,bubbles:true}))")
        self.assertEqual(await self.snapshot(), {'version': 1, 'profile': {'name': '', 'address': '', 'taxId': ''}, 'entries': entries, 'documents': []})
        await self.save_entry('confirmed')
        self.assertEqual(await self.page.input_value('#finance-payment [name="note"]'), 'Pending payment A')
        await self.page.click('[data-finance-tab="rates"]')
        await self.page.click('#finance-resume')
        await self.page.click('#finance-payment button')
        await self.page.wait_for_function('!savePending')
        record = (await self.snapshot())['entries'][0]
        self.assertEqual(record['currency'], 'EUR')
        self.assertEqual(record['kind'], 'extra')
        self.assertEqual(record['payments'][0]['amountMinor'], 250)
        self.assertEqual(await self.page.input_value('#finance-payment [name="amount"]'), '')
        await self.page.click('#finance-back')
        await self.page.click('[data-finance-tab="journal"]')
        await self.page.click('[data-finance-edit="b"]')
        self.assertEqual(await self.page.input_value('#finance-payment [name="note"]'), '')
        self.assertEqual(self.console_errors, [])

    async def test_pdf_reader_failures_fall_back_but_limits_still_reject(self):
        original = b'%PDF-1.4\nreader fixture\n%%EOF'
        for failure in ('module', 'worker', 'render', 'pages'):
            with self.subTest(failure=failure):
                module = {
                    'module': "throw Error('Reader missing');",
                    'worker': "export const GlobalWorkerOptions={};export const getDocument=()=>({promise:Promise.reject(Error('Worker unavailable')),destroy:async()=>{}});",
                    'render': "export const GlobalWorkerOptions={};export const getDocument=()=>({promise:Promise.resolve({numPages:2,getPage:async()=>({getViewport:()=>({width:50,height:70}),render:()=>({promise:Promise.reject(Error('Rendering failed'))})})}),destroy:async()=>{}});",
                    'pages': "export const GlobalWorkerOptions={};export const getDocument=()=>({promise:Promise.resolve({numPages:21}),destroy:async()=>{}});",
                }[failure]
                await self.page.route('**/pdfjs-dist/pdf.mjs', lambda route: route.fulfill(content_type='text/javascript', body=module))
                await self.page.reload()
                await self.wait_ready()
                await self.page.click('[data-page="business"]')
                await self.page.click('#finance-import')
                await self.page.set_input_files('#finance-files', {'name': 'reader.pdf', 'mimeType': 'application/pdf', 'buffer': original})
                await self.page.wait_for_function('!savePending')
                if failure == 'render':
                    await self.page.wait_for_function("document.querySelector('#finance-recognize')?.disabled")
                if failure == 'pages':
                    self.assertTrue(await self.page.locator('#finance-error').is_visible())
                    self.assertEqual(await self.page.locator('#finance-manual-import').count(), 0)
                else:
                    self.assertTrue(await self.page.locator('#finance-manual-import').is_visible())
                    self.assertEqual(await self.page.locator('[data-finance-canvas]').count(), 0)
                    await self.page.click('[data-finance-tab="rates"]')
                    await self.page.click('#finance-resume-intake')
                    self.assertTrue(await self.page.locator('#finance-manual-import').is_visible())
                    await self.page.click('#finance-discard-intake')
                self.assertEqual((await self.snapshot())['documents'], [])
                await self.page.unroute('**/pdfjs-dist/pdf.mjs')
        for name, blob in [('unsupported.txt', b'not a document'), ('large.pdf', b'%PDF-'+bytes(5*1024*1024))]:
            await self.page.set_input_files('#finance-files', {'name': name, 'mimeType': 'application/pdf', 'buffer': blob})
            await self.page.wait_for_function('!savePending')
            self.assertTrue(await self.page.locator('#finance-error').is_visible())
            self.assertEqual(await self.page.locator('#finance-manual-import').count(), 0)
        self.assertEqual(self.console_errors, [])

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
        if os.environ.get('DOGCARE_EVIDENCE_DIR'):
            await download.save_as(str(Path(os.environ['DOGCARE_EVIDENCE_DIR']) / f'finance-export-{self.api_mode}.zip'))
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

    async def test_filtered_export_preserves_all_records_sources_and_print_surface(self):
        await self.page.select_option('#language-picker', 'fr')
        await self.page.wait_for_function('!savePending')
        photo = await self.receipt_photo()
        self.assertTrue(await self.page.evaluate('''async encoded => {
          const blob=new Blob([Uint8Array.from(atob(encoded),c=>c.charCodeAt(0))],{type:'image/png'});
          const hash=await crypto.subtle.digest('SHA-256',await blob.arrayBuffer());
          const id=Array.from(new Uint8Array(hash),b=>b.toString(16).padStart(2,'0')).join('');
          const next=FinanceStore.snapshot();
          next.documents.push({id,name:'=Original café.png',type:blob.type,size:blob.size,sha256:id});
          const sale=FinanceModel.draft('export-sale','sale');
          Object.assign(sale,{status:'confirmed',number:'F-2026-001',date:'2026-10-06',
            party:'=SUM(A1)',address:'Adresse du client',issuer:'Entreprise exemple',
            issuerAddress:'Adresse de l’entreprise',currency:'CHF',vatMinor:1000});
          sale.lines=[{description:'Garde de jour',quantity:2,unitMinor:6500,bookingId:''},
            {description:'Supplément',quantity:1,unitMinor:500,bookingId:''}];
          sale.payments=[{id:'partial',date:'2026-10-06',amountMinor:3500,note:'Acompte saisi'}];
          const purchase=FinanceModel.draft('export-purchase','purchase');
          Object.assign(purchase,{status:'confirmed',date:'2026-10-06',party:'Fournisseur exemple',currency:'EUR',sourceId:id});
          purchase.lines[0]={description:'Croquettes',quantity:1,unitMinor:4250,bookingId:''};
          purchase.payments=[{id:'cost-partial',date:'2026-10-06',amountMinor:1000,note:'Paiement saisi'}];
          const draft=FinanceModel.draft('export-draft','expense');
          Object.assign(draft,{date:'2026-09-30',party:'Montant à vérifier',currency:'CHF',sourceId:id});
          const cancelled=FinanceModel.draft('export-cancelled','sale');
          Object.assign(cancelled,{status:'cancelled',number:'F-ANNULEE',date:'2026-09-30',
            party:'Client annulé',currency:'EUR',cancelReason:'Annulation demandée par le client'});
          cancelled.lines[0]={description:'Prestation annulée',quantity:1,unitMinor:9900,bookingId:''};
          next.entries.push(sale,purchase,draft,cancelled);
          return FinanceStore.save(next,new Map([[id,blob]]));
        }''', base64.b64encode(photo).decode()))
        await self.page.reload()
        await self.wait_ready()
        await self.page.click('[data-page="business"]')
        saved = await self.snapshot()
        self.assertEqual(await self.page.locator('[data-finance-entry]').count(), 4)
        totals = await self.page.locator('.finance-totals strong').all_inner_texts()
        self.assertEqual([' '.join(value.split()) for value in totals], [
            '135,00 CHF', '0,00 CHF', '35,00 CHF', '0,00 CHF',
            '0,00 €', '42,50 €', '0,00 €', '10,00 €',
        ])
        await self.page.click('.finance-filter-panel summary')
        await self.page.fill('#finance-month', '2026-10')
        await self.page.locator('#finance-month').press('Tab')
        await self.page.click('.finance-filter-panel summary')
        await self.page.fill('#finance-query', '=SUM(A1)')
        await self.page.locator('#finance-query').press('Tab')
        self.assertEqual(await self.page.locator('[data-finance-entry]').count(), 1)
        await self.capture_evidence(f'finance-filtered-journal-{self.api_mode}.png')
        async with self.page.expect_download() as info:
            await self.page.click('#finance-export')
        download = await info.value
        directory = os.environ.get('DOGCARE_EVIDENCE_DIR')
        if directory:
            await download.save_as(str(Path(directory) / f'finance-complete-export-{self.api_mode}.zip'))
        with zipfile.ZipFile(await download.path()) as archive:
            self.assertEqual(json.loads(archive.read('records.json')), saved)
            source = 'originals/' + hashlib.sha256(photo).hexdigest() + '.png'
            self.assertEqual(archive.read(source), photo)
            with zipfile.ZipFile(io.BytesIO(archive.read('comptabilite.xlsx'))) as workbook:
                ns = {'r': 'http://schemas.openxmlformats.org/package/2006/relationships'}
                for sheet in (1, 4):
                    links = ET.fromstring(workbook.read(f'xl/worksheets/_rels/sheet{sheet}.xml.rels'))
                    targets = [link.attrib['Target'] for link in links.findall('r:Relationship', ns)]
                    self.assertTrue(targets)
                    self.assertTrue(all(target == source for target in targets))
        await self.page.click('[data-finance-edit="export-sale"]')
        await self.page.evaluate('''() => {
          const append=document.body.append;
          document.body.append=function(...nodes){
            for(const node of nodes)if(node.matches?.('.finance-print-frame')){
              const onload=node.onload;
              node.onload=function(event){
                node.contentWindow.print=()=>{window.financePrintCalled=true;};
                onload.call(node,event);
              };
            }
            return append.apply(this,nodes);
          };
        }''')
        await self.page.click('#finance-print')
        await self.page.wait_for_function('window.financePrintCalled === true')
        html = await self.page.locator('.finance-print-frame').get_attribute('srcdoc')
        if directory:
            Path(directory, f'finance-invoice-print-{self.api_mode}.html').write_text(html, encoding='utf-8')
            preview = await self.context.new_page()
            await preview.set_viewport_size({'width': 900, 'height': 1000})
            await preview.set_content(html)
            self.assertIn('135,00', await preview.inner_text('body'))
            self.assertIn('=SUM(A1)', await preview.inner_text('body'))
            await preview.screenshot(path=str(Path(directory) / f'finance-invoice-print-{self.api_mode}.png'), full_page=True)
            await preview.close()
        await self.page.click('#finance-back')
        downloads = []
        self.page.on('download', lambda item: downloads.append(item))
        await self.page.evaluate('FinanceStore.document = async () => null')
        await self.page.click('#finance-export')
        await self.page.wait_for_function('!savePending')
        self.assertEqual(downloads, [])
        self.assertTrue(await self.page.locator('#toast.show').is_visible())
        self.assertEqual(await self.page.inner_text('#toast'),
                         await self.page.evaluate("FinanceUI.text('exportError')"))
        self.assertEqual(await self.snapshot(), saved)
        await self.capture_evidence(f'finance-export-missing-original-{self.api_mode}.png')
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
        await self.capture_evidence(f'finance-two-paper-areas-{self.api_mode}.png')
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
        if os.environ.get('DOGCARE_EVIDENCE_DIR'):
            viewport = self.page.viewport_size
            await self.page.set_viewport_size({'width': 1440, 'height': 900})
            await self.capture_evidence(f'finance-photo-review-desktop-{self.api_mode}.png')
            await self.page.set_viewport_size(viewport)
        await self.page.click('[data-finance-edit] >> nth=0')
        await self.save_entry('confirmed')
        await self.page.reload()
        await self.wait_ready()
        await self.page.click('[data-page="business"]')
        data = await self.snapshot()
        self.assertEqual(sum(e['status']=='confirmed' for e in data['entries']), 1)
        async with self.page.expect_download() as info:
            await self.page.click('#finance-export')
        download = await info.value
        if os.environ.get('DOGCARE_EVIDENCE_DIR'):
            await download.save_as(str(Path(os.environ['DOGCARE_EVIDENCE_DIR']) / f'finance-receipts-{self.api_mode}.zip'))
        with zipfile.ZipFile(await download.path()) as archive:
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

    async def test_stale_tab_keeps_draft_and_does_not_overwrite(self):
        other = await self.context.new_page()
        await other.goto(self.url)
        await other.wait_for_function("document.querySelector('#app-content')?.dataset.ready === 'true'")
        await other.click('[data-page="business"]')
        await other.click('#finance-new-expense')
        await other.fill('[name="party"]', 'Unsaved other tab')
        await self.page.click('#finance-new-expense')
        await self.page.fill('[name="party"]', 'Saved first tab')
        await self.save_entry()
        await other.click('#finance-form button[value="draft"]')
        await other.wait_for_function('!savePending')
        self.assertTrue(await other.locator('#finance-error').is_visible())
        self.assertEqual(await other.input_value('[name="party"]'), 'Unsaved other tab')
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual([e['party'] for e in (await self.snapshot())['entries']], ['Saved first tab'])
        await other.close()

    async def test_pdf_pages_manual_fallback_and_atomic_storage_failure(self):
        # Valid two-page synthetic PDF; no user document or external fetch.
        objects = [b'<< /Type /Catalog /Pages 2 0 R >>', b'<< /Type /Pages /Kids [3 0 R 5 0 R] /Count 2 >>',
                   b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 500 700] /Resources << >> /Contents 4 0 R >>',
                   b'<< /Length 0 >>\nstream\n\nendstream',
                   b'<< /Type /Page /Parent 2 0 R /MediaBox [0 0 500 700] /Resources << >> /Contents 6 0 R >>',
                   b'<< /Length 0 >>\nstream\n\nendstream']
        pdf = b'%PDF-1.4\n'; offsets = [0]
        for i, obj in enumerate(objects, 1):
            offsets.append(len(pdf)); pdf += f'{i} 0 obj\n'.encode() + obj + b'\nendobj\n'
        start = len(pdf)
        pdf += b'xref\n0 7\n0000000000 65535 f \n' + b''.join(f'{v:010d} 00000 n \n'.encode() for v in offsets[1:])
        pdf += f'trailer\n<< /Size 7 /Root 1 0 R >>\nstartxref\n{start}\n%%EOF'.encode()
        await self.page.evaluate("() => { window.pdfRead=FinanceDocuments.pages;FinanceDocuments.pages=async(...args)=>{try{return await pdfRead(...args)}catch(e){window.pdfReadError=e.message;throw e}}; }")
        await self.page.click('#finance-import')
        await self.page.set_input_files('#finance-files', {'name': 'two-pages.pdf', 'mimeType': 'application/pdf', 'buffer': pdf})
        await self.page.wait_for_function('!savePending')
        self.assertEqual(await self.page.locator('#finance-recognize').count(), 1, await self.page.evaluate('window.pdfReadError'))
        self.assertEqual(await self.page.locator('[data-finance-canvas]').count(), 2)
        await self.page.evaluate("() => { window.originalRecognize=FinanceDocuments.recognize;FinanceDocuments.recognize=async()=>{throw Error('Reader unavailable')}; }")
        await self.page.click('#finance-recognize')
        await self.page.wait_for_function('!savePending')
        self.assertTrue(await self.page.locator('#finance-error').is_visible())
        self.assertEqual((await self.snapshot())['documents'], [])
        if self.api_mode:
            await self.page.route('**/api/finance', lambda route: route.fulfill(status=507, json={'ok': False}))
        else:
            await self.page.evaluate("() => { window.originalPut=IDBObjectStore.prototype.put;IDBObjectStore.prototype.put=function(...args){if(this.name==='state')throw new DOMException('Quota','QuotaExceededError');return originalPut.apply(this,args)}; }")
        await self.page.click('#finance-manual-import')
        await self.page.wait_for_function('!savePending')
        self.assertTrue(await self.page.locator('#finance-error').is_visible())
        self.assertEqual((await self.snapshot())['documents'], [])
        self.assertEqual(await self.page.locator('[data-finance-canvas]').count(), 2)
        if self.api_mode:
            await self.page.unroute('**/api/finance')
        else:
            await self.page.evaluate('() => { IDBObjectStore.prototype.put=window.originalPut; }')
        await self.page.click('#finance-manual-import')
        await self.page.wait_for_function('!savePending')
        data = await self.snapshot()
        self.assertEqual(len(data['documents']), 1)
        self.assertEqual([e['region']['page'] for e in data['entries']], [1, 2])
        self.assertTrue(all(e['lines'][0]['unitMinor'] is None for e in data['entries']))
        await self.page.reload()
        await self.wait_ready()
        self.assertEqual(await self.snapshot(), data)

    async def test_localized_views_routes_and_unsaved_literal_draft(self):
        await self.page.click('#finance-new-expense')
        await self.page.fill('[name="party"]', 'Day care')
        await self.page.fill('[name="description-0"]', 'All good')
        await self.page.fill('[name="unit-0"]', '12.30')
        for locale in ('fr', 'en', 'it', 'de', 'es'):
            await self.page.select_option('#language-picker', locale)
            await self.page.wait_for_function('!savePending')
            await self.page.click('[data-page="dashboard"]')
            await self.page.click('[data-page="business"]')
            self.assertEqual(await self.page.input_value('[name="party"]'), 'Day care')
            self.assertEqual(await self.page.input_value('[name="description-0"]'), 'All good')
        await self.save_entry()
        await self.page.click('#finance-back')
        await self.page.select_option('#language-picker', 'fr')
        await self.page.wait_for_function("!document.querySelector('#toast').classList.contains('show')")
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

    async def test_unreadable_daily_storage_preserves_manual_draft_and_original(self):
        await self.page.evaluate("localStorage.setItem('dogcare-daily-v1','{')")
        for blocked in (False, True):
            if blocked:
                await self.page.add_init_script('''
                  const get=Storage.prototype.getItem;
                  Storage.prototype.getItem=function(key){if(key==='dogcare-daily-v1')throw Error('Unavailable');return get.call(this,key);};
                  window.readStoredDaily=()=>get.call(localStorage,'dogcare-daily-v1');
                ''')
            await self.page.reload()
            await self.wait_ready()
            await self.page.click('[data-page="business"]')
            await self.page.click('#finance-new-expense')
            self.assertTrue(await self.page.locator('#finance-bookings-unavailable').is_visible())
            self.assertEqual(await self.page.input_value('[name="currency"]'), '')
            await self.page.fill('[name="party"]', 'Manual entry')
            await self.save_entry()
            raw = await self.page.evaluate("window.readStoredDaily ? readStoredDaily() : localStorage.getItem('dogcare-daily-v1')")
            self.assertEqual(raw, '{')
        self.assertEqual(len((await self.snapshot())['entries']), 2)
        self.assertEqual(self.console_errors, [])

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

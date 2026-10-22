"""Balades on a phone: record with mocked GPS, a tolerated spot, reload, GPX import/export, Planning link."""
import asyncio
import threading
import unittest
from functools import partial
from pathlib import Path

from tests.test_browser_acceptance import ROOT, BrowserFixture, QuietStaticHandler

STYLE = '{"version":8,"sources":{},"layers":[{"id":"bg","type":"background","paint":{"background-color":"#efe9dc"}}]}'
GPX = b'''<?xml version="1.0"?><gpx version="1.1" xmlns="http://www.topografix.com/GPX/1/1">
<metadata><name>Boucle des Etangs</name></metadata><wpt lat="48.8031" lon="2.1201"><name>Point d'eau</name></wpt>
<trk><trkseg><trkpt lat="48.8030" lon="2.1200"><time>2026-10-20T08:00:00Z</time></trkpt><trkpt lat="48.8040" lon="2.1210"><time>2026-10-20T08:20:00Z</time></trkpt>
<trkpt lat="48.8050" lon="2.1230"><time>2026-10-20T08:45:00Z</time></trkpt></trkseg></trk></gpx>'''


class BaladesBrowserTest(BrowserFixture):
    launch_args = ('--use-angle=swiftshader', '--enable-unsafe-swiftshader')

    async def asyncSetUp(self):
        await super().asyncSetUp()
        self.assertEqual(await self.page.evaluate('BaladesStore.save(BaladesModel.empty())'), 'ok')
        await self.page.evaluate('BaladesStore.draft(null)')

    async def asyncTearDown(self):
        self.assertEqual(self.console_errors, [])
        await super().asyncTearDown()

    async def no_overflow(self):
        self.assertLessEqual(await self.page.evaluate('document.documentElement.scrollWidth'), 390)

    async def seed_tracks(self, draft=False, delayed_style=None):
        await self.context.route('https://tiles.openfreemap.org/**', delayed_style or (lambda route: route.fulfill(
            status=200, content_type='application/json', body=STYLE)))
        await self.page.select_option('#language-picker', 'fr')
        await self.page.wait_for_function("document.documentElement.lang === 'fr' && !savePending")
        await self.page.evaluate('''async draft => {
          const tracks=['a','b'].map((id,i)=>({id,name:'Track '+id,date:'2026-10-20',dogs:[],
            points:[[48+i,2,null],[48.001+i,2.001,null]],durationSec:60,source:'import',walkRefs:[],
            spots:[{id:'s',type:'pause',lat:48+i,lon:2,note:'Spot '+id,rule:'',noted:'2026-10-20'}]}));
          if(await BaladesStore.save({version:1,tracks})!=='ok')throw Error('Seed failed');
          await BaladesStore.draft(draft?{id:crypto.randomUUID(),token:crypto.randomUUID(),startedAt:Date.now()-60000,savedAt:Date.now(),points:[[47,1,null],[47.001,1.001,null]]}:null);
          await BaladesUI.load();
        }''', draft)
        await self.open_route('balades')

    async def test_draft_ownership_rejects_other_recordings_and_stale_tabs(self):
        other = await self.context.new_page()
        try:
            await other.goto(self.url)
            await other.wait_for_function("document.querySelector('#app-content')?.dataset.ready === 'true'")
            await other.evaluate('BaladesStore.load()')
            a = {'id': 'record-a', 'token': 'v1', 'startedAt': 1000, 'savedAt': 2000, 'points': [[48, 2, None]]}
            b = {**a, 'id': 'record-b'}
            self.assertIsNone(await self.page.evaluate('BaladesStore.draft()'))
            self.assertIsNone(await other.evaluate('BaladesStore.draft()'))
            self.assertIs(await self.page.evaluate('value=>BaladesStore.draft(value)', a), True)
            self.assertEqual(await other.evaluate('value=>BaladesStore.draft(value)', b), {'conflict': True, 'draft': a})
            recovered = await other.evaluate('BaladesStore.draft()')
            updated = {**a, 'token': 'v2', 'points': [[48, 2, None], [48.001, 2, None]]}
            self.assertIs(await self.page.evaluate('([value,previous])=>BaladesStore.draft(value,previous)', [updated, a]), True)
            self.assertEqual(await other.evaluate('([value,previous])=>BaladesStore.draft(value,previous)', [{**a, 'token': 'stale'}, recovered]), {'conflict': True, 'draft': updated})
            self.assertEqual(await other.evaluate('previous=>BaladesStore.draft(null,previous)', recovered), {'conflict': True, 'draft': updated})
            self.assertEqual(await other.evaluate('BaladesStore.draft()'), updated)
            self.assertIs(await self.page.evaluate('previous=>BaladesStore.draft(null,previous)', updated), True)
            self.assertIs(await self.page.evaluate('value=>BaladesStore.draft(value)', b), True)
            self.assertEqual(await other.evaluate('previous=>BaladesStore.draft(null,previous)', updated), {'conflict': True, 'draft': b})
            self.assertEqual(await other.evaluate('BaladesStore.draft()'), b)
            outcomes = await other.evaluate('''previous=>Promise.all(['v3','v4'].map(token=>
              BaladesStore.draft({...previous,token},previous)))''', b)
            self.assertEqual(outcomes.count(True), 1)
            self.assertEqual([result for result in outcomes if result is not True],
                             [{'conflict': True, 'draft': await other.evaluate('BaladesStore.draft()')}])
        finally:
            await other.close()

    async def test_readiness_waits_for_draft_recovery(self):
        await self.seed_tracks(draft=True)
        before = await self.page.evaluate('BaladesStore.draft()')
        script = (ROOT / 'balades-store.js').read_text() + '''
          const readDraft=BaladesStore.draft;
          BaladesStore.draft=(...args)=>args[0]===undefined?
            new Promise(resolve=>window.releaseDraft=async()=>resolve(await readDraft(...args))):readDraft(...args);
        '''
        await self.page.route('**/balades-store.js', lambda route: route.fulfill(content_type='text/javascript', body=script))
        await self.page.reload()
        await self.wait_ready()
        await self.page.wait_for_function('!!window.releaseDraft')
        await self.open_route('balades')
        self.assertEqual(await self.page.locator('[data-b=record]').count(), 0)
        await self.page.evaluate('releaseDraft()')
        await self.page.wait_for_selector('[data-b=resume]')
        self.assertTrue(await self.page.locator('[data-b=record]').is_disabled())
        self.assertEqual(await self.page.evaluate('readDraft()'), before)

    async def test_legacy_draft_remains_recoverable_and_gains_ownership(self):
        await self.seed_tracks()
        legacy = await self.page.evaluate('''async () => {
          const value={startedAt:Date.now()-60000,savedAt:Date.now(),points:[[47,1,null],[47.001,1.001,null]]};
          const scope=window.DogCareAPI?'account:'+(await DogCareAPI.balades()).businessId:'static';
          await new Promise((resolve,reject)=>{
            const open=indexedDB.open('dogcare-balades-v1');open.onerror=()=>reject(open.error);
            open.onsuccess=()=>{const db=open.result,tx=db.transaction('drafts','readwrite');
              tx.objectStore('drafts').put(value,scope);tx.oncomplete=()=>{db.close();resolve();};tx.onerror=()=>reject(tx.error);};
          });
          await BaladesUI.load();return value;
        }''')
        await self.page.click('[data-b=finish-draft]')
        await self.page.wait_for_selector('#track-form')
        recovered = await self.page.evaluate('BaladesStore.draft()')
        self.assertEqual(recovered['points'], legacy['points'])
        self.assertEqual(recovered['startedAt'], legacy['startedAt'])
        self.assertTrue(recovered['id'])
        self.assertTrue(recovered['token'])
        await self.page.click('#track-form [type=submit]')
        await self.page.wait_for_selector('.balades-track')
        self.assertIsNone(await self.page.evaluate('BaladesStore.draft()'))

    async def test_save_cleanup_preserves_draft_replaced_in_another_tab(self):
        await self.seed_tracks(draft=True)
        await self.page.click('[data-b=finish-draft]')
        await self.page.wait_for_selector('#track-form')
        other = await self.context.new_page()
        try:
            await other.goto(self.url)
            await other.wait_for_function("document.querySelector('#app-content')?.dataset.ready === 'true'")
            await other.evaluate('BaladesStore.load()')
            replacement = await other.evaluate('''async () => {
              const old=await BaladesStore.draft();
              if(await BaladesStore.draft(null,old)!==true)throw Error('Clear failed');
              const next={...old,id:crypto.randomUUID(),token:crypto.randomUUID(),points:[[46,1,null],[46.001,1,null],[46.002,1,null]]};
              if(await BaladesStore.draft(next)!==true)throw Error('Create failed');return next;
            }''')
            await self.page.click('#track-form [type=submit]')
            await self.page.wait_for_selector('.balades-track')
            self.assertEqual(await other.evaluate('BaladesStore.draft()'), replacement)
            self.assertFalse(await self.page.locator('#balades-draft-warning').is_visible())
            await self.page.click('[data-b=back]')
            await self.page.click('[data-b=finish-draft]')
            await self.page.wait_for_selector('#track-form')
            self.assertIn('3 points', await self.page.locator('#track-form .daily-help').text_content())
            self.assertEqual((await self.page.evaluate('BaladesStore.draft()'))['id'], replacement['id'])
        finally:
            await other.close()

    async def test_recovered_draft_discard_requires_confirmation(self):
        await self.seed_tracks(draft=True)
        before = await self.page.evaluate('BaladesStore.draft()')
        await self.page.get_by_role('button', name='Abandonner', exact=True).click()
        self.assertEqual(await self.page.evaluate('BaladesStore.draft()'), before)
        await self.page.wait_for_selector('.balades-confirm')
        await self.page.click('[data-b=discard-no]')
        self.assertEqual(await self.page.locator('.balades-confirm').count(), 0)
        self.assertEqual(await self.page.evaluate('BaladesStore.draft()'), before)
        await self.page.get_by_role('button', name='Abandonner', exact=True).click()
        await self.page.click('[data-b=discard]')
        await self.page.wait_for_function('''async () => (await BaladesStore.draft()) === null''')
        self.assertTrue(await self.page.locator('[data-b=record]').is_enabled())
        await self.no_overflow()

    async def test_discard_reconciles_draft_removed_elsewhere(self):
        await self.seed_tracks(draft=True)
        await self.page.evaluate('''async () => {
          const previous=await BaladesStore.draft();
          if(await BaladesStore.draft(null,previous)!==true)throw Error('Clear failed');
        }''')
        await self.page.click('[data-b=discard-ask]')
        await self.page.click('[data-b=discard]')
        await self.page.wait_for_function("!document.querySelector('[data-b=record]').disabled", timeout=2000)
        self.assertEqual(await self.page.locator('[data-b=resume]').count(), 0)
        self.assertIsNone(await self.page.evaluate('BaladesStore.draft()'))

    async def test_creation_retry_keeps_track_and_spot_ids(self):
        await self.seed_tracks()
        page = self.page
        for kind in ('track', 'spot'):
            with self.subTest(kind=kind):
                if kind == 'track':
                    await page.set_input_files('#balades-import', files=[{'name': 'test.gpx', 'mimeType': 'application/gpx+xml', 'buffer': GPX}])
                else:
                    await page.click('[data-b=add-spot]')
                    if await page.locator('[data-b=place-center]').count():
                        await page.click('[data-b=place-center]')
                    await page.fill('#spot-form [name=note]', 'New spot')
                form = '#track-form' if kind == 'track' else '#spot-form'
                await page.evaluate('''() => {
                  const save=BaladesStore.save;let attempts=0;
                  BaladesStore.save=async next=>{
                    if(++attempts===1){if(await save(next)!=='ok')throw Error('Save failed');return 'failed';}
                    if(attempts===2)return 'conflict';
                    return save(next);
                  };
                  window.restoreSave=()=>BaladesStore.save=save;
                }''')
                await page.click(f'{form} [type=submit]')
                await page.wait_for_selector('#balades-message[role=alert]')
                before = await page.evaluate('BaladesStore.snapshot()')
                await page.click(f'{form} [type=submit]')
                await page.wait_for_selector('[data-b=replay]')
                await page.click('[data-b=replay]')
                await page.wait_for_selector('.balades-track')
                self.assertEqual(await page.evaluate('BaladesStore.snapshot()'), before)
                await page.evaluate('restoreSave()')

    async def test_form_edit_removes_abandoned_retry_button(self):
        await self.seed_tracks()
        page = self.page
        await page.evaluate("window.realSave=BaladesStore.save; BaladesStore.save=async()=> 'conflict'")
        for kind in ('import', 'track', 'spot'):
            with self.subTest(kind=kind):
                if kind == 'import':
                    await page.set_input_files('#balades-import', files=[{'name': 'test.gpx', 'mimeType': 'application/gpx+xml', 'buffer': GPX}])
                elif kind == 'track':
                    await page.click('[data-track=a] [data-b=open]')
                    await page.click('[data-b=edit]')
                else:
                    await page.click('[data-b=edit-spot]')
                form, field, cancel = {'import': ('#track-form', 'name', 'cancel-save'),
                                       'track': ('#edit-form', 'name', 'cancel-edit'),
                                       'spot': ('#spot-form', 'note', 'cancel-spot')}[kind]
                await page.click(f'{form} [type=submit]')
                await page.wait_for_selector('[data-b=replay]')
                await page.fill(f'{form} [name={field}]', 'Revised input')
                self.assertEqual(await page.locator('[data-b=replay]').count(), 0)
                self.assertEqual(await page.input_value(f'{form} [name={field}]'), 'Revised input')
                await page.click(f'[data-b={cancel}]')
        await self.no_overflow()

    async def test_late_wake_lock_is_released_after_recording_stops(self):
        await self.seed_tracks(draft=True)
        await self.context.grant_permissions(['geolocation'], origin=self.url)
        await self.context.set_geolocation({'latitude': 48.84, 'longitude': 2.22, 'accuracy': 5})
        page = self.page
        for stop, reject in (('finish', False), ('discard', False), ('finish', True)):
            with self.subTest(stop=stop, reject=reject):
                if await page.locator('[data-b=resume]').count() == 0:
                    await page.evaluate('''async () => {
                      await BaladesStore.draft({id:crypto.randomUUID(),token:crypto.randomUUID(),startedAt:Date.now()-1000,
                        savedAt:Date.now(),points:[[47,1,null],[47.001,1.001,null]]});await BaladesUI.load();
                    }''')
                await page.evaluate('''() => {
                  window.releasedLocks=0;
                  Object.defineProperty(navigator,'wakeLock',{configurable:true,value:{request:()=>new Promise((resolve,reject)=>{
                    window.resolveWake=()=>resolve({release:async()=>{releasedLocks++;},addEventListener:()=>{}});
                    window.rejectWake=()=>reject(Error('Denied'));
                  })}});
                }''')
                await page.click('[data-b=resume]')
                await page.wait_for_function('!!window.resolveWake')
                if stop == 'finish':
                    await page.click('[data-b=finish]')
                    await page.wait_for_selector('#track-form')
                else:
                    await page.click('[data-b=discard-ask]')
                    await page.click('[data-b=discard]')
                    await page.wait_for_selector('[data-b=record]')
                await page.evaluate('rejectWake()' if reject else 'resolveWake()')
                if not reject:
                    await page.wait_for_function('releasedLocks === 1', timeout=2000)
                self.assertEqual(self.page_errors, [])
                if stop == 'finish':
                    await page.click('[data-b=cancel-save]')

    async def test_import_failure_preserves_form_and_unrelated_recording(self):
        await self.seed_tracks(draft=True)
        page = self.page
        before = await page.evaluate('BaladesStore.draft()')
        await page.set_input_files('#balades-import', files=[{'name': 'test.gpx', 'mimeType': 'application/gpx+xml', 'buffer': GPX}])
        await page.fill('#track-form [name=name]', 'Changed import')
        await page.fill('#track-form [name=date]', '2026-10-19')
        await page.locator('#track-form [name=dog]').first.check()
        await page.evaluate("window.realSave=BaladesStore.save; BaladesStore.save=async()=> 'failed'")
        await page.click('#track-form [type=submit]')
        await page.wait_for_selector('#balades-message[role=alert]')
        self.assertEqual(await page.input_value('#track-form [name=name]'), 'Changed import')
        self.assertEqual(await page.input_value('#track-form [name=date]'), '2026-10-19')
        self.assertTrue(await page.locator('#track-form [name=dog]').first.is_checked())
        await page.evaluate('BaladesStore.save=realSave')
        await page.click('#track-form [type=submit]')
        await page.wait_for_selector('.balades-track h2:has-text("Changed import")')
        await page.click('[data-b=back]')
        self.assertTrue(await page.locator('[data-b=record]').is_disabled())
        self.assertTrue(await page.locator('[data-b=resume]').is_visible())
        self.assertEqual(await page.evaluate('BaladesStore.draft()'), before)
        await self.no_overflow()

    async def test_failed_link_keeps_recording_button_disabled(self):
        await self.seed_tracks(draft=True)
        await self.open_route('schedule')
        await self.page.evaluate('''() => {
          const button=document.createElement('button');button.dataset.baladeLink=Object.keys(dogs)[0];
          button.dataset.baladeDate='2026-10-20';document.body.append(button);button.click();button.remove();
          BaladesStore.save=async()=> 'failed';
        }''')
        await self.page.click('[data-track=a] [data-b=link]')
        await self.page.wait_for_selector('#balades-message[role=alert]')
        self.assertTrue(await self.page.locator('[data-b=record]').is_disabled())
        self.assertTrue(await self.page.locator('[data-b=resume]').is_enabled())

    async def test_successful_import_keeps_unfinished_recording(self):
        await self.seed_tracks(draft=True)
        page = self.page
        before = await page.evaluate('BaladesStore.draft()')
        await page.set_input_files('#balades-import', files=[{'name': 'test.gpx', 'mimeType': 'application/gpx+xml', 'buffer': GPX}])
        await page.click('#track-form [type=submit]')
        await page.wait_for_selector('.balades-track h2:has-text("Boucle des Etangs")')
        await page.click('[data-b=back]')
        self.assertTrue(await page.locator('[data-b=record]').is_disabled())
        self.assertTrue(await page.locator('[data-b=resume]').is_visible())
        self.assertEqual(await page.evaluate('BaladesStore.draft()'), before)

    async def test_failed_edits_and_missing_targets_keep_input(self):
        for kind in ('track', 'spot'):
            with self.subTest(kind=kind):
                if kind == 'spot':
                    await self.page.reload()
                    await self.wait_ready()
                await self.seed_tracks()
                page = self.page
                await page.click('[data-track=a] [data-b=open]')
                await page.click('[data-b=edit]' if kind == 'track' else '[data-b=edit-spot]')
                form = '#edit-form' if kind == 'track' else '#spot-form'
                if kind == 'track':
                    await page.fill(f'{form} [name=name]', 'Unsaved name')
                    await page.fill(f'{form} [name=date]', '2026-10-19')
                    await page.locator(f'{form} [name=dog]').first.check()
                else:
                    await page.check(f'{form} [value=tolere]')
                    await page.fill(f'{form} [name=note]', 'Unsaved practice')
                    await page.fill(f'{form} [name=rule]', 'Unsaved official rule')
                    await page.fill(f'{form} [name=noted]', '2026-10-19')
                await page.evaluate("window.realSave=BaladesStore.save; BaladesStore.save=async()=> 'failed'")
                await page.click(f'{form} [type=submit]')
                await page.wait_for_selector('#balades-message[role=alert]')
                if kind == 'track':
                    self.assertEqual(await page.input_value(f'{form} [name=name]'), 'Unsaved name')
                    self.assertEqual(await page.input_value(f'{form} [name=date]'), '2026-10-19')
                    self.assertTrue(await page.locator(f'{form} [name=dog]').first.is_checked())
                else:
                    self.assertEqual(await page.input_value(f'{form} [name=note]'), 'Unsaved practice')
                    self.assertEqual(await page.input_value(f'{form} [name=rule]'), 'Unsaved official rule')
                    self.assertEqual(await page.input_value(f'{form} [name=noted]'), '2026-10-19')
                await page.evaluate("BaladesStore.save=async()=> 'conflict'")
                await page.click(f'{form} [type=submit]')
                await page.wait_for_selector('[data-b=replay]')
                await page.evaluate('''async () => {
                  BaladesStore.save=realSave;const next=BaladesStore.snapshot();next.tracks=next.tracks.filter(t=>t.id!=='a');
                  if(await BaladesStore.save(next)!=='ok')throw Error('Delete failed');
                }''')
                await page.click('[data-b=replay]')
                await page.wait_for_selector('#balades-message[role=alert]:has-text("supprimé")')
                self.assertTrue(await page.locator(form).is_visible())
                self.assertEqual(await page.input_value(f'{form} [name={"name" if kind == "track" else "rule"}]'),
                                 'Unsaved name' if kind == 'track' else 'Unsaved official rule')
                self.assertEqual(await page.evaluate('BaladesStore.snapshot().tracks.map(t=>t.id)'), ['b'])
                await self.no_overflow()
                await self.open_route('schedule')

    async def test_delete_replay_locks_reload_and_cancels_on_navigation(self):
        await self.seed_tracks()
        page = self.page
        await page.click('[data-track=a] [data-b=open]')
        await page.click('[data-b=delete-ask]')
        await page.evaluate("window.realSave=BaladesStore.save; BaladesStore.save=async()=> 'conflict'")
        await page.click('[data-b=delete]')
        await page.wait_for_selector('[data-b=replay]')
        await page.evaluate('''() => {
          BaladesStore.save=realSave;window.realReload=BaladesStore.reload;
          BaladesStore.reload=()=>new Promise(resolve=>window.releaseReload=async()=>resolve(await realReload()));
        }''')
        await page.click('[data-b=replay]')
        await page.wait_for_function('!!window.releaseReload')
        self.assertTrue(await page.locator('[data-b=back]').is_disabled())
        await self.open_route('schedule')
        await page.evaluate('''() => {
          const button=document.createElement('button');button.dataset.baladeOpen='b';
          document.body.append(button);button.click();button.remove();
        }''')
        await page.evaluate('releaseReload()')
        await page.wait_for_function("!document.querySelector('#balades-panel [data-busy]')")
        self.assertEqual(await page.evaluate('BaladesStore.snapshot().tracks.map(t=>t.id)'), ['a', 'b'])
        self.assertEqual(await page.locator('[data-b=replay]').count(), 0)

    async def test_missing_unlink_target_is_reported(self):
        await self.seed_tracks()
        page = self.page
        await page.evaluate('''async () => {
          const next=BaladesStore.snapshot(),dog=Object.keys(dogs)[0];next.tracks[0].dogs=[dog];
          next.tracks[0].walkRefs=[{date:'2026-10-20',dogId:dog}];await BaladesStore.save(next);await BaladesUI.load();
        }''')
        await page.click('[data-track=a] [data-b=open]')
        await page.evaluate("window.realSave=BaladesStore.save; BaladesStore.save=async()=> 'conflict'")
        await page.click('[data-b=unlink]')
        await page.wait_for_selector('[data-b=replay]')
        await page.evaluate('''async () => {
          BaladesStore.save=realSave;const next=BaladesStore.snapshot();next.tracks.shift();await BaladesStore.save(next);
        }''')
        await page.click('[data-b=replay]')
        await page.wait_for_selector('#balades-message[role=alert]:has-text("supprimé")')
        self.assertEqual(await page.evaluate('BaladesStore.snapshot().tracks.map(t=>t.id)'), ['b'])

    async def test_successful_recording_save_cleans_draft_after_navigation(self):
        await self.seed_tracks(draft=True)
        page = self.page
        await page.click('[data-b=finish-draft]')
        await page.wait_for_selector('#track-form')
        await page.fill('#track-form [name=name]', 'Saved while away')
        await page.evaluate('''() => {
          const save=BaladesStore.save;
          BaladesStore.save=next=>new Promise(resolve=>window.releaseSave=async()=>resolve(await save(next)));
        }''')
        await page.click('#track-form [type=submit]')
        await page.wait_for_function('!!window.releaseSave')
        await self.open_route('schedule')
        await page.evaluate('releaseSave()')
        await page.wait_for_function('''async () => (await BaladesStore.draft()) === null''')
        await self.open_route('balades')
        self.assertEqual(await page.locator('#track-form').count(), 0)
        self.assertEqual(await page.locator('.balade-row:has-text("Saved while away")').count(), 1)
        self.assertTrue(await page.locator('[data-b=record]').is_enabled())

    async def test_abandoned_delete_is_cleared_and_confirmed_retry_recovers(self):
        await self.seed_tracks()
        page = self.page
        await page.evaluate("window.realSave=BaladesStore.save; BaladesStore.save=async()=> 'conflict'")
        await page.click('[data-track=a] [data-b=open]')
        await page.click('[data-b=delete-ask]')
        await page.click('[data-b=delete]')
        await page.wait_for_selector('[data-b=replay]')
        await page.click('[data-b=back]')
        await page.click('[data-track=b] [data-b=open]')
        self.assertEqual(await page.locator('[data-b=replay]').count(), 0)
        await page.click('[data-b=back]')
        await page.click('[data-track=a] [data-b=open]')
        await page.click('[data-b=delete-ask]')
        await page.click('[data-b=delete]')
        await page.wait_for_selector('[data-b=replay]')
        await page.evaluate('''() => {
          BaladesStore.save=realSave;window.realReload=BaladesStore.reload;BaladesStore.reload=async()=>false;
        }''')
        await page.click('[data-b=replay]')
        await page.wait_for_selector('#balades-message:has-text("charger")')
        self.assertTrue(await page.locator('[data-b=replay]').is_enabled())
        await page.evaluate('BaladesStore.reload=realReload')
        await page.click('[data-b=replay]')
        await page.wait_for_selector('.balade-row')
        self.assertEqual(await page.evaluate('BaladesStore.snapshot().tracks.map(t=>t.id)'), ['b'])

    async def test_map_draw_uses_latest_selection_after_style_load(self):
        requested, release = asyncio.Event(), asyncio.Event()
        async def delayed_style(route):
            requested.set()
            await release.wait()
            await route.fulfill(status=200, content_type='application/json', body=STYLE)
        await self.seed_tracks(delayed_style=delayed_style)
        page = self.page
        await page.evaluate('''async () => {
          const lib=await import('/assets/vendor/balades/maplibre-gl/maplibre-gl.mjs'),add=lib.Map.prototype.addSource;
          lib.Map.prototype.addSource=function(...args){window.testMap=this;return add.apply(this,args);};
        }''')
        await page.click('[data-track=a] [data-b=open]')
        await asyncio.wait_for(requested.wait(), 5)
        await page.click('[data-b=back]')
        await page.click('[data-track=b] [data-b=open]')
        release.set()
        await page.wait_for_function("window.testMap?.getSource('balade')?.serialize().data.geometry.coordinates.length === 2")
        self.assertEqual(await page.evaluate("testMap.getSource('balade').serialize().data.geometry.coordinates"),
                         [[2, 49], [2.001, 49.001]])
        self.assertEqual(await page.locator('#balades-map .balade-marker').get_attribute('aria-label'), 'Pause : Spot b')

    async def test_recording_persistence_failure_warns_and_keeps_memory(self):
        await self.seed_tracks()
        page = self.page
        await self.context.grant_permissions(['geolocation'], origin=self.url)
        await self.context.set_geolocation({'latitude': 48.84, 'longitude': 2.22, 'accuracy': 5})
        await page.evaluate('''() => {
          const draft=BaladesStore.draft;BaladesStore.draft=value=>value===undefined?draft():Promise.resolve(false);
        }''')
        await page.click('[data-b=record]')
        await page.wait_for_function("document.querySelector('#rec-points')?.textContent === '1'")
        await page.wait_for_selector('#balades-draft-warning[role=alert]')
        await self.context.set_geolocation({'latitude': 48.841, 'longitude': 2.22, 'accuracy': 5})
        await page.wait_for_function("document.querySelector('#rec-points')?.textContent === '2'")
        await page.click('[data-b=finish]')
        await page.wait_for_selector('#track-form')
        self.assertTrue(await page.locator('#balades-draft-warning').is_visible())
        await page.click('[data-b=cancel-save]')
        self.assertTrue(await page.locator('[data-b=resume]').is_visible())
        self.assertTrue(await page.locator('[data-b=record]').is_disabled())
        self.assertTrue(await page.locator('#balades-draft-warning').is_visible())
        await self.no_overflow()

    async def test_planning_clones_snapshot_at_most_once_for_many_dogs(self):
        await self.seed_tracks()
        count = await self.page.evaluate('''() => {
          let calls=0;const snapshot=BaladesStore.snapshot;BaladesStore.snapshot=()=>{calls++;return snapshot();};
          BaladesUI.walkLinks('2026-10-20',Array.from({length:20},(_,i)=>'dog'+i));return calls;
        }''')
        self.assertLessEqual(count, 1)

    async def test_record_spot_reload_import_export_and_link_on_phone(self):
        page = self.page
        await self.context.route('https://tiles.openfreemap.org/**', lambda route: route.fulfill(
            status=200, content_type='application/json', body=STYLE))
        await self.context.grant_permissions(['geolocation'], origin=self.url)
        await self.context.set_geolocation({'latitude': 48.8400, 'longitude': 2.2200, 'accuracy': 5})
        await page.select_option('#language-picker', 'fr')
        await page.wait_for_function("document.documentElement.lang === 'fr' && !savePending")

        # Record a short walk: three fixes about 55 m apart.
        await self.open_route('balades')
        await page.click('[data-b="record"]')
        await page.wait_for_function("document.querySelector('#rec-points')?.textContent === '1'")
        for count, lat in ((2, 48.8405), (3, 48.8410)):
            await self.context.set_geolocation({'latitude': lat, 'longitude': 2.2200, 'accuracy': 5})
            await page.wait_for_function(f"document.querySelector('#rec-points')?.textContent === '{count}'")
        self.assertIn('Gardez l’écran allumé', await page.locator('.balades-warning').text_content())
        await page.wait_for_selector('#balades-map canvas')
        await self.no_overflow()
        await self.capture_evidence(f'balades-recording-{self.api_mode}.png')
        await page.click('[data-b="finish"]')
        await page.fill('#track-form [name=name]', 'Parc de Saint-Cloud')
        await page.locator('#track-form [name=dog]').first.check()
        await page.click('#track-form [type=submit]')
        await page.wait_for_selector('.balades-track h2:has-text("Parc de Saint-Cloud")')

        # Tap the map to place a tolerated spot with its official rule.
        await page.click('[data-b="add-spot"]')
        box = await page.locator('#balades-map').bounding_box()
        await page.mouse.click(box['x'] + box['width'] / 2, box['y'] + box['height'] / 2)
        await page.click('label.balades-type:has([value=tolere])')
        await page.fill('#spot-form [name=note]', 'Chiens calmes sans laisse acceptés tôt le matin')
        await page.fill('#spot-form [name=rule]', 'Laisse obligatoire dans tout le parc')
        await page.click('#spot-form [type=submit]')
        spot = page.locator('.balade-spot')
        await spot.wait_for()
        self.assertIn('Règle officielle', await spot.text_content())
        self.assertIn('Laisse obligatoire dans tout le parc', await spot.text_content())
        await page.wait_for_selector('#balades-map button.balade-tolere[aria-label^="Toléré"]')
        await self.no_overflow()
        await self.capture_evidence(f'balades-track-tolere-{self.api_mode}.png')

        # Reload: the track and its spot persist.
        await page.reload()
        await self.wait_ready()
        await self.open_route('balades')
        await page.click('.balade-row:has-text("Parc de Saint-Cloud") [data-b="open"]')
        self.assertIn('Laisse obligatoire dans tout le parc', await page.locator('.balade-spot').text_content())
        async with page.expect_download() as info:
            await page.click('[data-b="export"]')
        exported = Path(await (await info.value).path()).read_text()
        self.assertEqual(exported.count('<trkpt'), 3)
        self.assertIn('<type>tolere</type>', exported)
        self.assertIn('<cmt>Laisse obligatoire dans tout le parc</cmt>', exported)

        # Import: a malformed file is refused in plain French, a GPX becomes a track with a pause spot.
        await page.click('[data-b="back"]')
        await page.set_input_files('#balades-import', files=[{'name': 'casse.gpx', 'mimeType': 'application/gpx+xml', 'buffer': b'<gpx><trk>'}])
        await page.wait_for_selector('#balades-message[role=alert]:has-text("pas un GPX lisible")')
        await page.set_input_files('#balades-import', files=[{'name': 'etangs.gpx', 'mimeType': 'application/gpx+xml', 'buffer': GPX}])
        await page.wait_for_selector('#track-form')
        self.assertEqual(await page.input_value('#track-form [name=name]'), 'Boucle des Etangs')
        self.assertEqual(await page.input_value('#track-form [name=date]'), '2026-10-20')
        await page.click('#track-form [type=submit]')
        await page.wait_for_selector('.balades-track h2:has-text("Boucle des Etangs")')
        self.assertIn('45 min', await page.locator('.balades-track .daily-help').first.text_content())
        self.assertIn("Point d'eau", await page.locator('.balade-spot').text_content())
        await page.click('[data-b="back"]')
        self.assertEqual(await page.locator('.balade-row').count(), 2)
        await self.no_overflow()
        await self.capture_evidence(f'balades-list-{self.api_mode}.png')

        # Planning: a saved walk gets "Ajouter le tracé", then "Voir le tracé".
        await self.open_route('schedule')
        walked = page.locator('#walk-form [name=walked]').first
        dog = await walked.get_attribute('value')
        await walked.check()
        await page.click('#walk-form [type=submit]')
        add = page.locator(f'[data-balade-link="{dog}"]')
        await add.click()
        self.assertEqual(await page.evaluate('state.page'), 'balades')
        await page.click('.balade-row:has-text("Boucle des Etangs") [data-b="link"]')
        await page.wait_for_function("state.page === 'schedule'")
        await page.click(f'#walk-tracks [data-balade-open]')
        await page.wait_for_selector('.balades-track h2:has-text("Boucle des Etangs")')
        self.assertIn('Balades du Planning', await page.locator('.balades-track').text_content())
        await self.no_overflow()
        self.assertEqual(self.console_errors, [])


class StaticBaladesBrowserTest(BaladesBrowserTest):
    api_mode = False

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.static_httpd = cls.server_mod.Server(('127.0.0.1', 0), partial(QuietStaticHandler, directory=str(ROOT)))
        cls.static_thread = threading.Thread(target=cls.static_httpd.serve_forever, daemon=True)
        cls.static_thread.start()
        cls.url = f'http://127.0.0.1:{cls.static_httpd.server_address[1]}'

    @classmethod
    def tearDownClass(cls):
        cls.static_httpd.shutdown()
        cls.static_httpd.server_close()
        cls.static_thread.join(timeout=2)
        super().tearDownClass()


if __name__ == '__main__':
    unittest.main()

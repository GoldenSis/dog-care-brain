const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const { test } = require('node:test');

const source = fs.readFileSync(require('node:path').join(__dirname, '..', 'api.js'), 'utf8');
const serverState = { ok: true, business_id: 1, imported: false, observations: { billie: [{ id: 1, text: 'Server history' }] }, invites: [], language: 'en' };
const response = (data, status = 200) => ({ ok: status < 400, status, text: async () => JSON.stringify(data) });
const tick = () => new Promise(resolve => setImmediate(resolve));

function adapter({ local = {}, fetcher, confirm = () => true, enabled = true } = {}) {
  const storage = new Map(Object.entries(local));
  const calls = [], toasts = [], notices = [];
  const window = {
    DOGCARE_API: enabled ? '/api' : undefined,
    localStorage: { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) },
    showToast: text => toasts.push(text),
    confirm: text => { notices.push(text); return confirm(text); },
  };
  vm.runInNewContext(source, { window, fetch: async (url, options) => {
    const call = { url, ...options, payload: options.body && JSON.parse(options.body) };
    calls.push(call);
    return fetcher ? fetcher(call, calls) : response(serverState);
  } });
  return { api: window.DogCareAPI, storage, calls, toasts, notices };
}

test('flag off leaves storage and network untouched', () => {
  const h = adapter({ enabled: false });
  assert.equal(h.api, undefined);
  assert.equal(h.calls.length, 0);
});

test('failed hydration blocks all persistence', async () => {
  const h = adapter({ fetcher: async () => response({}, 503) });
  assert.equal(await h.api.ready, false);
  await h.api.saveObservations({ billie: [{ text: 'New note' }] });
  await h.api.saveInvites([]);
  await h.api.saveLanguage('fr');
  await tick();
  assert.equal(h.calls.length, 1);
});

test('interrupted response bodies resolve hydration failure', async () => {
  const h = adapter({ fetcher: async () => ({ ok: true, status: 200, text: async () => { throw Error('disconnected'); } }) });
  assert.equal(await h.api.ready, false);
});

test('failed import preserves authoritative data and leaves migration retryable', async () => {
  const local = { 'dogcare-observations': JSON.stringify({ billie: [{ text: 'Local history' }] }) };
  const h = adapter({ local, fetcher: async call => call.url.endsWith('/import') ? response({}, 503) : response(serverState) });
  assert.equal(await h.api.ready, false);
  assert.equal(h.api.getObservations().billie[0].text, 'Server history');
  assert.equal([...h.storage.keys()].filter(key => key.startsWith('dogcare-imported')).length, 0);
  assert.equal(h.storage.get('dogcare-observations'), local['dogcare-observations']);
});

test('partial migration imports invites and language without replacing absent observations', async () => {
  const h = adapter({ local: { 'dogcare-invites': '[{"email":"carer@example.com"}]', 'dogcare-language': 'fr' }, fetcher: async call => {
    if (call.url.endsWith('/import')) return response({ ...serverState, imported: true, invites: call.payload.invites, language: 'fr' });
    return response(serverState);
  } });
  assert.equal(await h.api.ready, true);
  const call = h.calls.find(call => call.url.endsWith('/import'));
  assert.ok(call);
  assert.equal(Object.hasOwn(call.payload, 'observations'), false);
  assert.equal(h.api.getLanguage(), 'fr');
  assert.equal(h.api.getObservations().billie[0].text, 'Server history');
  assert.equal(h.storage.get('dogcare-imported:1'), '1');
});

test('old global migration marker does not skip another business import', async () => {
  const h = adapter({ local: { 'dogcare-imported': '1', 'dogcare-language': 'fr' } });
  await h.api.ready;
  assert.ok(h.calls.some(call => call.url.endsWith('/import')));
});

test('closed server import eligibility prevents stale recording uploads', async () => {
  const h = adapter({ local: { 'dogcare-observations': '{"billie":[{"audio":{"url":"data:audio/webm;base64,YQ=="}}]}' }, fetcher: async () => response({ ...serverState, imported: true }) });
  assert.equal(await h.api.ready, true);
  assert.equal(h.calls.length, 1);
  assert.equal(h.notices.length, 0);
});

test('migration notices and extracts large parameterized audio before importing', async () => {
  const data = 'YWFh'.repeat(600000);
  const h = adapter({ local: { 'dogcare-observations': JSON.stringify({ billie: [{ id: 1, audio: { url: 'data:audio/webm;codecs=opus;base64,' + data } }] }) }, fetcher: async call => {
    if (call.url.endsWith('/blobs')) {
      assert.equal(h.notices.length, 1);
      assert.equal(call.payload.type, 'audio/webm;codecs=opus');
      assert.equal(call.payload.data, data);
      return response({ ok: true, ref: 'recording.webm' });
    }
    if (call.url.endsWith('/import')) {
      assert.equal(call.payload.observations.billie[0].audio.url, '/api/blobs/recording.webm');
      return response({ ...serverState, ...call.payload, imported: true });
    }
    return response(serverState);
  } });
  assert.equal(await h.api.ready, true);
  assert.equal(h.calls.filter(call => call.url.endsWith('/blobs')).length, 1);
  assert.match(h.notices[0], /business.*server/);
});

test('declining recording import transfers nothing and keeps the local snapshot', async () => {
  const h = adapter({ local: { 'dogcare-observations': '{"billie":[{"audio":{"url":"data:audio/webm;base64,YQ=="}}]}' }, confirm: () => false });
  assert.equal(await h.api.ready, false);
  assert.equal(h.calls.length, 1);
  assert.equal(h.storage.has('dogcare-observations'), true);
});

test('queued saves retain call order and reconcile uploaded references into app state', async () => {
  let release;
  const upload = new Promise(resolve => { release = resolve; });
  const h = adapter({ fetcher: async call => {
    if (call.url.endsWith('/blobs')) { await upload; return response({ ok: true, ref: 'recording.webm' }); }
    return response(serverState);
  } });
  await h.api.ready;
  const obs = { billie: [{ id: 1, text: 'First', audio: { url: 'data:audio/webm;base64,YQ==' } }] };
  const first = h.api.saveObservations(obs);
  await tick();
  obs.billie.unshift({ id: 2, text: 'Second' });
  const second = h.api.saveObservations(obs);
  await tick();
  assert.equal(h.calls.filter(call => call.method === 'PUT').length, 0);
  assert.equal(h.calls.filter(call => call.url.endsWith('/blobs')).length, 1);
  release();
  await Promise.all([first, second]);
  await tick();
  const writes = h.calls.filter(call => call.url.endsWith('/observations'));
  assert.deepEqual(writes.map(call => call.payload.observations.billie.length), [1, 2]);
  assert.equal(obs.billie[1].audio.url, '/api/blobs/recording.webm');
  assert.equal(h.api.getObservations().billie.length, 2);
  await h.api.saveObservations(obs);
  await tick();
  assert.equal(h.calls.filter(call => call.url.endsWith('/blobs')).length, 1);
});

test('upload failure prevents inline audio persistence and permits a later retry', async () => {
  let succeeds = false;
  const h = adapter({ fetcher: async call => call.url.endsWith('/blobs') ? response(succeeds ? { ref: 'retry.webm' } : {}, succeeds ? 200 : 503) : response(serverState) });
  await h.api.ready;
  const obs = { billie: [{ id: 1, audio: { url: 'data:audio/webm;base64,YQ==' } }] };
  await h.api.saveObservations(obs);
  await tick();
  assert.equal(h.calls.filter(call => call.method === 'PUT').length, 0);
  succeeds = true;
  await h.api.saveObservations(obs);
  await tick();
  assert.equal(obs.billie[0].audio.url, '/api/blobs/retry.webm');
});

test('interrupted write bodies show failure and the save queue recovers', async () => {
  let broken = true;
  const h = adapter({ fetcher: async call => call.method === 'PUT' && broken ? { ok: true, status: 200, text: async () => { throw Error('body lost'); } } : response(serverState) });
  await h.api.ready;
  await h.api.saveLanguage('fr');
  await tick();
  assert.equal(h.toasts.length, 1);
  broken = false;
  await h.api.saveLanguage('de');
  await tick();
  assert.equal(h.calls.filter(call => call.method === 'PUT').length, 2);
});

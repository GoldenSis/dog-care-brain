const assert = require('node:assert/strict');
const { test } = require('node:test');
const model = require('../daily-model.js');

const booking = (changes = {}) => ({ id: 'booking-1', dogId: 'dog-1', service: 'day', start: '2026-01-31', end: '2026-02-02', unitMinor: 1234, currency: 'CHF', ...changes });
function records(bookings = [booking()]) {
  return { ...model.empty(), clients: [{ id: 'client-1', name: 'Client fixture' }], dogs: [{ id: 'dog-1', name: 'Dog fixture', clientId: 'client-1' }], bookings };
}
const document = (changes = {}) => ({ id: 'document-1', dogId: 'dog-1', label: 'Proof fixture', renewal: '', type: 'application/pdf', name: 'proof.pdf', data: Buffer.from('%PDF-1.4\nfixture').toString('base64'), ...changes });

test('new records contain no invented clients, bookings, documents or prices', () => {
  const value = model.empty();
  assert.deepEqual(value, { version: 1, clients: [], dogs: [], bookings: [], rates: { currency: 'CHF', walk: null, day: null, night: null }, documents: [] });
  assert.equal(model.validateDaily(value), true);
  value.rates.day = 100;
  assert.equal(model.empty().rates.day, null);
});

test('daily dog identifiers retain mixed case, underscores and legacy care lengths', () => {
  for (const id of ['Dog_1', 'dog_1', 'legacy-' + 'x'.repeat(74)]) {
    const value = records([booking({ dogId: id })]);
    value.dogs[0].id = id;
    assert.equal(model.validateDaily(value), true);
    assert.equal(value.dogs[0].id, id);
  }
  for (const id of ['x'.repeat(82), '_dog', '../dog', 'dog\n']) {
    const value = records([booking({ dogId: id })]);
    value.dogs[0].id = id;
    assert.throws(() => model.validateDaily(value));
  }
});

test('calendar validation rejects normalized and ambiguous dates and handles leap years', () => {
  for (const valid of ['2024-02-29', '2000-02-29', '0001-01-01', '9999-12-31']) assert.equal(model.validDate(valid), true, valid);
  for (const invalid of ['2026-02-29', '1900-02-29', '2026-04-31', '2026-13-01', '2026-2-01', '0000-01-01', '2026-01-01T00:00Z', null, 20260101]) assert.equal(model.validDate(invalid), false, String(invalid));
});

test('walks and days include each date; nights exclude checkout', () => {
  for (const service of ['walk', 'day']) assert.deepEqual(model.serviceDates(booking({ service })), ['2026-01-31', '2026-02-01', '2026-02-02']);
  assert.deepEqual(model.serviceDates(booking({ service: 'night' })), ['2026-01-31', '2026-02-01']);
  assert.equal(model.units(booking({ end: '2026-01-31' })), 1);
  assert.throws(() => model.units(booking({ service: 'night', end: '2026-01-31' })));
});

test('calendar allocation is stable across leap days and both daylight-saving changes', () => {
  for (const [start, end, expected] of [
    ['2024-02-28', '2024-03-01', ['2024-02-28', '2024-02-29', '2024-03-01']],
    ['2026-03-28', '2026-03-30', ['2026-03-28', '2026-03-29', '2026-03-30']],
    ['2026-10-24', '2026-10-26', ['2026-10-24', '2026-10-25', '2026-10-26']],
  ]) assert.deepEqual(model.serviceDates(booking({ start, end })), expected);
});

test('invalid services, reversed dates and ranges over 366 service days are rejected', () => {
  for (const changes of [{ service: 'subscription' }, { end: '2026-01-30' }, { start: '2026-01-01', end: '2027-01-02' }, { end: 'invalid' }]) assert.throws(() => model.serviceDates(booking(changes)));
  assert.equal(model.units(booking({ start: '2024-01-01', end: '2024-12-31' })), 366);
  assert.equal(model.units(booking({ service: 'night', start: '2024-01-01', end: '2025-01-01' })), 366);
});

test('decimal amounts preserve exact cents, free prices and unknown prices', () => {
  for (const [input, expected] of [['', null], ['  ', null], ['0', 0], ['0.00', 0], ['0.29', 29], ['001.2', 120], [' 12,34 ', 1234], ['90071992547409.91', Number.MAX_SAFE_INTEGER]]) assert.equal(model.parseMinor(input), expected);
  for (const input of ['-1', '+1', '.5', '1.', '1.234', '1e3', '1,000.00', 'NaN', 'Infinity', '90071992547409.92', 12, null]) assert.throws(() => model.parseMinor(input), String(input));
  assert.equal(model.amount(booking()), 3702);
  assert.equal(model.amount(booking({ unitMinor: null })), null);
  assert.equal(model.amount(booking({ unitMinor: 0 })), 0);
  for (const unitMinor of [undefined, -1, 1.5, true, 100000001]) assert.throws(() => model.amount(booking({ unitMinor })));
});

test('monthly allocation reconciles amounts and units across month/year boundaries', () => {
  for (const service of ['walk', 'day', 'night']) {
    const item = booking({ service, start: '2025-12-30', end: '2026-02-02' });
    const value = records([item]);
    const rows = ['2025-12', '2026-01', '2026-02'].flatMap(month => model.monthlySummary(value, month));
    assert.equal(rows.reduce((sum, row) => sum + row.units, 0), model.units(item));
    assert.equal(rows.reduce((sum, row) => sum + row.knownMinor, 0), model.amount(item));
    assert.ok(rows.every(row => row.bookingCount === 1));
  }
  const january = model.monthlySummary(records(), '2026-01');
  assert.deepEqual(january, [{ clientId: 'client-1', clientName: 'Client fixture', service: 'day', currency: 'CHF', bookingCount: 1, units: 1, knownMinor: 1234, unknownUnits: 0 }]);
  assert.deepEqual(model.monthlySummary(records(), '2026-03'), []);
  assert.throws(() => model.monthlySummary(records(), '2026-13'));
});

test('monthly rows separate client, service and currency; unknown amounts stay explicit', () => {
  const value = records([
    booking(), booking({ id: 'unknown', unitMinor: null }), booking({ id: 'free', unitMinor: 0 }),
    booking({ id: 'eur', currency: 'EUR' }), booking({ id: 'walk', service: 'walk' }),
    booking({ id: 'other-client', dogId: 'dog-2' }),
  ]);
  value.clients.push({ id: 'client-2', name: 'Second fixture' });
  value.dogs.push({ id: 'dog-2', name: 'Second dog', clientId: 'client-2' });
  const rows = model.monthlySummary(value, '2026-02');
  assert.equal(rows.length, 4);
  assert.deepEqual(rows[0], { clientId: 'client-1', clientName: 'Client fixture', service: 'day', currency: 'CHF', bookingCount: 3, units: 6, knownMinor: 2468, unknownUnits: 2 });
  assert.equal(rows.find(row => row.currency === 'EUR').knownMinor, 2468);
});

test('extensions retain recorded agreement after configuration changes', () => {
  const value = records();
  value.rates.day = 9999;
  value.rates.currency = 'EUR';
  assert.deepEqual(model.extension(value.bookings[0], '2026-02-04'), { addedUnits: 2, addedMinor: 2468, totalUnits: 5, totalMinor: 6170 });
  assert.equal(model.monthlySummary(value, '2026-02')[0].knownMinor, 2468);
  assert.deepEqual(model.extension(booking({ unitMinor: null }), '2026-02-03'), { addedUnits: 1, addedMinor: null, totalUnits: 4, totalMinor: null });
  assert.deepEqual(model.extension(booking({ unitMinor: 0 }), '2026-02-02'), { addedUnits: 0, addedMinor: 0, totalUnits: 3, totalMinor: 0 });
  assert.throws(() => model.extension(booking(), '2026-02-01'));
  assert.deepEqual(value.bookings[0], booking());
});

test('document follow-up uses recorded dates and a 30-calendar-day display window', () => {
  for (const [renewal, expected] of [['', 'undated'], ['2026-02-27', 'overdue'], ['2026-02-28', 'due'], ['2026-03-30', 'due'], ['2026-03-31', 'later']]) assert.equal(model.documentStatus({ renewal }, '2026-02-28'), expected);
  assert.equal(model.documentStatus({ renewal: '2024-03-30' }, '2024-02-29'), 'due');
  assert.throws(() => model.documentStatus({ renewal: '2026-02-30' }, '2026-02-28'));
});

test('corrupt snapshots fail validation without modifying or replacing data', () => {
  const corruptions = [
    value => { value.version = 2; }, value => { value.clients = {}; },
    value => { value.clients.push({ ...value.clients[0] }); },
    value => { value.dogs[0].clientId = 'missing'; }, value => { value.bookings[0].dogId = 'missing'; },
    value => { value.bookings[0].currency = 'chf'; }, value => { value.bookings[0].unitMinor = '1234'; },
    value => { value.bookings[0].end = '2026-02-30'; }, value => { value.clients[0].name = ' '; },
    value => { value.clients[0].name = 'unsafe\nname'; }, value => { value.clients[0].name = 'x'.repeat(121); },
    value => { value.clients[0].id = '../client'; }, value => { value.rates.day = -1; },
    value => { value.bookings[0].completed = true; }, value => { delete value.rates.walk; },
    value => { value.documents = [document({ dogId: 'missing' })]; },
  ];
  for (const corrupt of corruptions) {
    const value = records();
    corrupt(value);
    const before = JSON.stringify(value);
    assert.throws(() => model.validateDaily(value));
    assert.equal(JSON.stringify(value), before);
  }
  for (const value of [null, [], 'records', {}]) assert.throws(() => model.validateDaily(value));
});

test('document validation permits private account references and validated static bytes', () => {
  const local = document();
  const account = { ...local, href: '/api/documents/document-1' };
  delete account.data;
  for (const item of [local, account]) {
    const value = records();
    value.documents.push(item);
    assert.equal(model.validateDaily(value), true);
  }
  for (const changes of [{ type: 'text/html' }, { data: 'not base64' }, { data: 'YWJjZA==' }, { href: 'https://external.example/file' }, { name: '' }, { renewal: '2026-02-30' }]) assert.throws(() => model.validateDocument(document(changes)));
  const external = { ...account, href: 'https://external.example/file' };
  assert.throws(() => model.validateDocument(external));
});

test('document size boundary is measured in decoded bytes', () => {
  const content = Buffer.alloc(5 * 1024 * 1024, 0);
  content.write('%PDF-1.4');
  assert.equal(model.validateDocument(document({ data: content.toString('base64') })), true);
  const oversized = Buffer.concat([content, Buffer.from([0])]);
  assert.throws(() => model.validateDocument(document({ data: oversized.toString('base64') })), /5 MiB/);
});

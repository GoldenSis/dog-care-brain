const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');

function fixture(count = 200) {
  const daily = { dogs: [], bookings: [], clients: [] };
  const portal = { quotes: {}, requests: [], updates: [], documents: [], members: [], extras: [] };
  for (let index = 0; index < count; index++) {
    const id = 'booking-' + index, dogId = 'dog-' + index;
    daily.dogs.push({ id: dogId, name: 'Dog ' + index, clientId: 'family' });
    daily.bookings.push({ id, dogId, service: 'day', start: '2026-11-01', end: '2026-11-01' });
    portal.quotes[id] = { units: 1, unitMinor: 100 + index, currency: 'CHF', totalMinor: 100 + index, extras: [] };
    portal.requests.push({ ...daily.bookings[index], status: 'requested', note: 'Request ' + index });
  }
  portal.extras.push({ id: 'template', label: 'Synthetic option', unitMinor: 789, currency: 'CHF' });
  const reads = { daily: 0, portal: 0 };
  const context = {
    Intl, Map, DailyModel: require('../daily-model.js'),
    state: { language: 'en', observations: {}, dog: 'dog-0' }, dogs: {},
    PortalCopy: { en: {} },
    escapeHtml: value => String(value), formatLocale: () => 'en', setHeader: () => {},
    localDay: () => '2026-11-01', t: key => key,
    document: { querySelectorAll: () => [] },
    DailyUI: { snapshot: () => structuredClone(daily), alerts: () => '', text: key => key },
    DogCareAPI: {
      getUser: () => ({ role: 'owner' }),
      getDaily: () => { reads.daily++; return structuredClone(daily); },
      getPortal: () => { reads.portal++; return structuredClone(portal); },
    },
  };
  context.window = context;
  vm.createContext(context);
  for (const file of ['portal-ui.js', 'quote-ui.js']) vm.runInContext(fs.readFileSync(require.resolve('../' + file), 'utf8'), context);
  return { context, daily, portal, reads };
}

test('booking quote rendering reads one snapshot and retains every booking', () => {
  const { context, portal, reads } = fixture();
  let rendered = context.QuoteUI.bookings();
  assert.equal(reads.portal, 1);
  assert.equal(reads.daily, 1);
  assert.equal((rendered.match(/class="quote-booking"/g) || []).length, 200);
  assert.equal((rendered.match(/data-quote=/g) || []).length, 200);
  assert.match(rendered, /Dog 199/);
  portal.quotes['booking-199'].extras.push({ label: 'Fresh agreed option', quantity: 1, unitMinor: 100, totalMinor: 100, currency: 'CHF' });
  rendered = context.QuoteUI.bookings();
  assert.equal(reads.portal, 2);
  assert.match(rendered, /Fresh agreed option/);
});

test('client reservations and owner requests reuse one daily and portal snapshot per pass', () => {
  const { context, reads } = fixture();
  const reservations = context.PortalUI.render('reservations');
  assert.equal(reads.portal, 1);
  assert.equal(reads.daily, 1);
  assert.equal((reservations.match(/class="portal-row"/g) || []).length, 400);
  assert.match(reservations, /Request 199/);
  const home = context.PortalUI.ownerHome();
  assert.equal(reads.portal, 2);
  assert.equal(reads.daily, 1);
  assert.equal((home.match(/data-quote=/g) || []).length, 200);
  assert.match(home, /Dog 199/);
});

test('quote binding uses one snapshot while reusable options and save retain the selected target', () => {
  const { context, reads } = fixture();
  const panels = Array.from({ length: 200 }, (_, index) => {
    const output = {};
    const elements = Object.fromEntries(['label', 'unitMinor', 'quantity', 'currency', 'template', 'id', 'reusable'].map(name => [name, { value: '', checked: false }]));
    elements.currency.value = 'CHF';
    elements.quantity.value = '1';
    const form = { elements, querySelector: () => output };
    return { dataset: { quote: 'booking-' + index }, form, output, querySelector: selector => selector === '.extra-form' ? form : null, querySelectorAll: () => [] };
  });
  context.document.querySelectorAll = () => panels;
  const saved = [];
  context.QuoteUI.bind((action, payload) => saved.push({ action, payload }));
  assert.equal(reads.portal, 1);
  const { form, output } = panels[199];
  form.elements.template.value = 'template';
  form.elements.template.onchange();
  assert.equal(form.elements.label.value, 'Synthetic option');
  assert.equal(form.elements.unitMinor.value, '7.89');
  assert.match(output.textContent, /7.89/);
  form.onsubmit({ preventDefault() {} });
  assert.equal(saved[0].action, 'extras');
  assert.equal(saved[0].payload.targetId, 'booking-199');
  assert.equal(saved[0].payload.unitMinor, 789);
  assert.equal(reads.portal, 1);
});

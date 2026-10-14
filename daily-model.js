/* Calendar and agreement calculations shared by the browser-only and account UI.
   Dates represent calendar days, never instants or local timezone offsets. */
(function (root, factory) {
  const model = factory();
  if (typeof module === 'object' && module.exports) module.exports = model;
  else root.DailyModel = model;
}(typeof window === 'undefined' ? globalThis : window, function () {
  'use strict';

  const DAY = 86400000;
  const SERVICES = ['walk', 'day', 'night'];
  const MAX_DOCUMENT_BYTES = 5 * 1024 * 1024;
  const ID = /^[A-Za-z0-9][A-Za-z0-9_-]{0,80}(?![\s\S])/;
  const CURRENCY = /^[A-Z]{3}$/;

  function requireValue(condition, message) {
    if (!condition) throw new Error(message);
  }

  function object(value) {
    return value !== null && typeof value === 'object' && !Array.isArray(value);
  }

  function text(value, maximum) {
    return typeof value === 'string' && value.trim().length > 0 && [...value].length <= maximum && !/[\x00-\x1f\x7f]/.test(value);
  }

  function fields(value, keys) {
    requireValue(object(value) && Object.keys(value).sort().join(' ') === keys.split(' ').sort().join(' '), 'Invalid record fields');
  }

  function validDate(value) {
    if (typeof value !== 'string' || !/^\d{4}-\d{2}-\d{2}$/.test(value) || value < '0001-01-01') return false;
    const parsed = new Date(value + 'T00:00:00.000Z');
    return Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === value;
  }

  function dayNumber(value) {
    requireValue(validDate(value), 'Invalid calendar date');
    return Date.parse(value + 'T00:00:00.000Z') / DAY;
  }

  function serviceDates(booking) {
    requireValue(object(booking) && SERVICES.includes(booking.service), 'Invalid service');
    const first = dayNumber(booking.start);
    const last = dayNumber(booking.end);
    const count = last - first + (booking.service === 'night' ? 0 : 1);
    requireValue(count > 0 && count <= 366, 'A booking must contain 1 to 366 service days');
    return Array.from({ length: count }, (_, index) => new Date((first + index) * DAY).toISOString().slice(0, 10));
  }

  function units(booking) { return serviceDates(booking).length; }

  function activeBooking(booking) { return booking.status !== 'cancelled'; }

  function validMinor(value) { return value === null || (Number.isSafeInteger(value) && value >= 0 && value <= 100000000); }

  function checkedMinor(value) {
    requireValue(Number.isSafeInteger(value) && value >= 0, 'Amount exceeds safe integer range');
    return value;
  }

  function amount(booking) {
    requireValue(validMinor(booking.unitMinor), 'Invalid agreed unit amount');
    const count = units(booking);
    return booking.unitMinor === null ? null : checkedMinor(booking.unitMinor * count);
  }

  function parseMinor(value) {
    requireValue(typeof value === 'string', 'Enter an amount as text');
    const input = value.trim();
    if (!input) return null;
    // A decimal comma is also accepted for French input; grouping is not accepted.
    requireValue(/^\d+(?:[.,]\d{1,2})?$/.test(input), 'Enter a nonnegative amount with at most two decimals');
    const [whole, fraction = ''] = input.split(/[.,]/);
    const minor = BigInt(whole) * 100n + BigInt(fraction.padEnd(2, '0'));
    requireValue(minor <= BigInt(Number.MAX_SAFE_INTEGER), 'Amount exceeds safe integer range');
    return Number(minor);
  }

  function empty() {
    return { version: 2, clients: [], dogs: [], bookings: [], rates: { currency: 'CHF', walk: null, day: null, night: null }, documents: [], walks: [] };
  }

  // Version 1 predates walk tariffs and walk attendance: it reads as dogs
  // without a tariff and no recorded walk. Other values are returned unchanged.
  function upgrade(daily) {
    if (!object(daily) || daily.version !== 1 || Object.hasOwn(daily, 'walks') || !Array.isArray(daily.dogs)) return daily;
    const dogs = daily.dogs.map(dog => object(dog) && !Object.hasOwn(dog, 'walkTariff') ? { ...dog, walkTariff: null } : dog);
    return { ...daily, version: 2, dogs, walks: [] };
  }

  function validTariff(tariff) {
    return tariff === null || (object(tariff) && Object.keys(tariff).sort().join(' ') === 'currency unitMinor' &&
      Number.isSafeInteger(tariff.unitMinor) && tariff.unitMinor >= 0 && tariff.unitMinor <= 100000000 &&
      typeof tariff.currency === 'string' && CURRENCY.test(tariff.currency));
  }

  function sameTariff(a, b) {
    return a === null || b === null ? a === b : a.unitMinor === b.unitMinor && a.currency === b.currency;
  }

  function records(value, kind) {
    requireValue(Array.isArray(value) && value.length <= 5000, 'Invalid ' + kind + ' list');
    const ids = new Set();
    for (const item of value) {
      requireValue(object(item) && typeof item.id === 'string' && ID.test(item.id) && !ids.has(item.id), 'Invalid or duplicate ' + kind + ' ID');
      ids.add(item.id);
    }
    return ids;
  }

  function validateDocument(document) {
    requireValue(object(document) && typeof document.id === 'string' && ID.test(document.id), 'Invalid document ID');
    requireValue(typeof document.dogId === 'string' && ID.test(document.dogId), 'Invalid document dog');
    requireValue(text(document.label, 120) && text(document.name, 180), 'Invalid document label or filename');
    requireValue(document.renewal === '' || validDate(document.renewal), 'Invalid recorded renewal date');
    requireValue(['application/pdf', 'image/jpeg', 'image/png'].includes(document.type), 'Unsupported document type');
    const hasData = Object.hasOwn(document, 'data');
    const hasHref = Object.hasOwn(document, 'href');
    requireValue(hasData !== hasHref, 'Document requires exactly one stored source');
    fields(document, 'id dogId label renewal type name ' + (hasData ? 'data' : 'href'));
    if (hasData) {
      const data = document.data;
      requireValue(typeof data === 'string' && data.length > 0 && data.length <= Math.ceil(MAX_DOCUMENT_BYTES / 3) * 4 && data.length % 4 === 0 && /^[A-Za-z0-9+/]*={0,2}$/.test(data), 'Invalid document data');
      const bytes = data.length / 4 * 3 - (data.endsWith('==') ? 2 : data.endsWith('=') ? 1 : 0);
      requireValue(bytes <= MAX_DOCUMENT_BYTES, 'Document exceeds 5 MiB');
      const prefix = atob(data.slice(0, 12));
      const signatures = { 'application/pdf': '%PDF-', 'image/jpeg': '\xff\xd8\xff', 'image/png': '\x89PNG\r\n\x1a\n' };
      requireValue(prefix.startsWith(signatures[document.type]), 'Invalid document contents');
    } else {
      requireValue(document.href === '/api/documents/' + document.id, 'Invalid private document URL');
    }
    return true;
  }

  function validateDaily(daily) {
    fields(daily, 'version clients dogs bookings rates documents walks');
    requireValue(object(daily) && daily.version === 2, 'Unsupported daily records format');
    const clients = records(daily.clients, 'client');
    const dogs = records(daily.dogs, 'dog');
    records(daily.bookings, 'booking');
    records(daily.documents, 'document');
    records(daily.walks, 'walk');
    for (const client of daily.clients) {
      fields(client, 'id name');
      requireValue(text(client.name, 120), 'Invalid client name');
    }
    for (const dog of daily.dogs) {
      fields(dog, 'id name clientId walkTariff');
      requireValue(text(dog.name, 120) && (dog.clientId === null || clients.has(dog.clientId)), 'Invalid dog name or client');
      requireValue(validTariff(dog.walkTariff), 'Invalid walk tariff');
    }
    fields(daily.rates, 'currency walk day night');
    requireValue(object(daily.rates) && typeof daily.rates.currency === 'string' && CURRENCY.test(daily.rates.currency), 'Invalid rate currency');
    for (const service of SERVICES) requireValue(validMinor(daily.rates[service]), 'Invalid base rate');
    const dogClients = new Map(daily.dogs.map(d => [d.id, d.clientId]));
    const totals = new Map();
    for (const booking of daily.bookings) {
      fields(booking, 'id dogId service start end unitMinor currency' + (Object.hasOwn(booking, 'status') ? ' status' : ''));
      requireValue(!Object.hasOwn(booking, 'status') || ['planned', 'cancelled'].includes(booking.status), 'Invalid booking status');
      requireValue(dogs.has(booking.dogId), 'Booking references an unknown dog');
      requireValue(clients.has(dogClients.get(booking.dogId)), 'Booking needs a recorded client');
      requireValue(typeof booking.currency === 'string' && CURRENCY.test(booking.currency), 'Invalid agreement currency');
      const total = amount(booking);
      if (total !== null) totals.set(booking.currency, checkedMinor((totals.get(booking.currency) || 0) + total));
    }
    for (const document of daily.documents) {
      validateDocument(document);
      requireValue(dogs.has(document.dogId), 'Document references an unknown dog');
    }
    const walked = new Set();
    for (const walk of daily.walks) {
      fields(walk, 'id dogId date tariff');
      requireValue(dogs.has(walk.dogId), 'Walk references an unknown dog');
      requireValue(validDate(walk.date), 'Invalid walk date');
      requireValue(validTariff(walk.tariff), 'Invalid walk tariff');
      const key = JSON.stringify([walk.dogId, walk.date]);
      requireValue(!walked.has(key), 'A dog has one recorded walk per day');
      walked.add(key);
    }
    return true;
  }

  function bookingClientId(booking, dog, associations = {}) {
    return Object.hasOwn(associations, booking.id) ? associations[booking.id] : dog?.clientId ?? null;
  }

  function monthlySummary(daily, month, associations = {}) {
    validateDaily(daily);
    requireValue(typeof month === 'string' && /^\d{4}-\d{2}$/.test(month) && validDate(month + '-01'), 'Invalid summary month');
    const dogs = new Map(daily.dogs.map(dog => [dog.id, dog]));
    const clients = new Map(daily.clients.map(client => [client.id, client]));
    const rows = new Map();
    for (const booking of daily.bookings) {
      if (!activeBooking(booking)) continue;
      const count = serviceDates(booking).filter(date => date.slice(0, 7) === month).length;
      if (!count) continue;
      const clientId = bookingClientId(booking, dogs.get(booking.dogId), associations);
      const client = clients.get(clientId);
      const key = JSON.stringify([clientId, booking.service, booking.currency]);
      if (!rows.has(key)) rows.set(key, { clientId, clientName: client?.name || '', service: booking.service, currency: booking.currency, bookingCount: 0, units: 0, knownMinor: 0, unknownUnits: 0 });
      const row = rows.get(key);
      row.bookingCount++;
      row.units += count;
      if (booking.unitMinor === null) row.unknownUnits += count;
      else row.knownMinor = checkedMinor(row.knownMinor + booking.unitMinor * count);
    }
    return Array.from(rows.values());
  }

  // Walk tariffs use the currency already used in Comptabilité: that of the
  // most recently dated entry with a currency, or euros when there is none.
  function accountingCurrency(entries) {
    const used = (Array.isArray(entries) ? entries : []).filter(e => object(e) && typeof e.currency === 'string' && CURRENCY.test(e.currency));
    used.sort((a, b) => String(a.date || '').localeCompare(String(b.date || '')));
    return used.length ? used[used.length - 1].currency : 'EUR';
  }

  // A walk records attendance, never a booking, invoice or payment. It keeps
  // the dog's tariff in force when it was recorded; later tariff changes do
  // not reprice it.
  function recordWalk(dog, date, walkId) {
    requireValue(object(dog) && validTariff(dog.walkTariff) && validDate(date), 'Invalid walk');
    return { id: walkId, dogId: dog.id, date, tariff: dog.walkTariff === null ? null : { ...dog.walkTariff } };
  }

  // Month-end information per dog: walk count and the amounts of the tariffs
  // recorded on those walks. Unpriced walks are counted, never valued; currencies
  // are never combined.
  function walkSummary(daily, month) {
    validateDaily(daily);
    requireValue(typeof month === 'string' && /^\d{4}-\d{2}$/.test(month) && validDate(month + '-01'), 'Invalid summary month');
    const rows = new Map();
    const totals = {};
    let count = 0, unpriced = 0;
    for (const walk of [...daily.walks].sort((a, b) => a.date.localeCompare(b.date))) {
      if (walk.date.slice(0, 7) !== month) continue;
      if (!rows.has(walk.dogId)) {
        const dog = daily.dogs.find(d => d.id === walk.dogId);
        rows.set(walk.dogId, { dogId: walk.dogId, dogName: dog.name, count: 0, unpriced: 0, lines: [], totals: {} });
      }
      const row = rows.get(walk.dogId);
      row.count++; count++;
      if (walk.tariff === null) { row.unpriced++; unpriced++; continue; }
      let line = row.lines.find(l => sameTariff(l.tariff, walk.tariff));
      if (!line) row.lines.push(line = { tariff: { ...walk.tariff }, count: 0, totalMinor: 0 });
      line.count++;
      line.totalMinor = checkedMinor(line.totalMinor + walk.tariff.unitMinor);
      row.totals[walk.tariff.currency] = checkedMinor((row.totals[walk.tariff.currency] || 0) + walk.tariff.unitMinor);
      totals[walk.tariff.currency] = checkedMinor((totals[walk.tariff.currency] || 0) + walk.tariff.unitMinor);
    }
    return { rows: Array.from(rows.values()), count, unpriced, totals };
  }

  function extension(booking, end) {
    const previousUnits = units(booking);
    const previousAmount = amount(booking);
    requireValue(validDate(end) && end >= booking.end, 'An extension cannot shorten a booking');
    const extended = { ...booking, end };
    const totalUnits = units(extended);
    const totalMinor = amount(extended);
    return { addedUnits: totalUnits - previousUnits, addedMinor: totalMinor === null ? null : totalMinor - previousAmount, totalUnits, totalMinor };
  }

  function documentStatus(document, today) {
    const current = dayNumber(today);
    if (document.renewal === '') return 'undated';
    const renewal = dayNumber(document.renewal);
    if (renewal < current) return 'overdue';
    return renewal <= current + 30 ? 'due' : 'later';
  }

  return { empty, upgrade, validTariff, sameTariff, accountingCurrency, recordWalk, walkSummary, validDate, serviceDates, units, activeBooking, amount, parseMinor, bookingClientId, monthlySummary, extension, documentStatus, validateDaily, validateDocument };
}));

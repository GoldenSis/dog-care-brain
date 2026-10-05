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
    return { version: 1, clients: [], dogs: [], bookings: [], rates: { currency: 'CHF', walk: null, day: null, night: null }, documents: [] };
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
    fields(daily, 'version clients dogs bookings rates documents');
    requireValue(object(daily) && daily.version === 1, 'Unsupported daily records format');
    const clients = records(daily.clients, 'client');
    const dogs = records(daily.dogs, 'dog');
    records(daily.bookings, 'booking');
    records(daily.documents, 'document');
    for (const client of daily.clients) {
      fields(client, 'id name');
      requireValue(text(client.name, 120), 'Invalid client name');
    }
    for (const dog of daily.dogs) {
      fields(dog, 'id name clientId');
      requireValue(text(dog.name, 120) && clients.has(dog.clientId), 'Invalid dog name or client');
    }
    fields(daily.rates, 'currency walk day night');
    requireValue(object(daily.rates) && typeof daily.rates.currency === 'string' && CURRENCY.test(daily.rates.currency), 'Invalid rate currency');
    for (const service of SERVICES) requireValue(validMinor(daily.rates[service]), 'Invalid base rate');
    const totals = new Map();
    for (const booking of daily.bookings) {
      fields(booking, 'id dogId service start end unitMinor currency');
      requireValue(dogs.has(booking.dogId), 'Booking references an unknown dog');
      requireValue(typeof booking.currency === 'string' && CURRENCY.test(booking.currency), 'Invalid agreement currency');
      const total = amount(booking);
      if (total !== null) totals.set(booking.currency, checkedMinor((totals.get(booking.currency) || 0) + total));
    }
    for (const document of daily.documents) {
      validateDocument(document);
      requireValue(dogs.has(document.dogId), 'Document references an unknown dog');
    }
    return true;
  }

  function monthlySummary(daily, month) {
    validateDaily(daily);
    requireValue(typeof month === 'string' && /^\d{4}-\d{2}$/.test(month) && validDate(month + '-01'), 'Invalid summary month');
    const dogs = new Map(daily.dogs.map(dog => [dog.id, dog]));
    const clients = new Map(daily.clients.map(client => [client.id, client]));
    const rows = new Map();
    for (const booking of daily.bookings) {
      const count = serviceDates(booking).filter(date => date.slice(0, 7) === month).length;
      if (!count) continue;
      const client = clients.get(dogs.get(booking.dogId).clientId);
      const key = JSON.stringify([client.id, booking.service, booking.currency]);
      if (!rows.has(key)) rows.set(key, { clientId: client.id, clientName: client.name, service: booking.service, currency: booking.currency, bookingCount: 0, units: 0, knownMinor: 0, unknownUnits: 0 });
      const row = rows.get(key);
      row.bookingCount++;
      row.units += count;
      if (booking.unitMinor === null) row.unknownUnits += count;
      else row.knownMinor = checkedMinor(row.knownMinor + booking.unitMinor * count);
    }
    return Array.from(rows.values());
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

  return { empty, validDate, serviceDates, units, amount, parseMinor, monthlySummary, extension, documentStatus, validateDaily, validateDocument };
}));

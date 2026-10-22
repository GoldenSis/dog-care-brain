/* Instance brand. The API injects DOGCARE_BRAND only for a non-default instance; static mode is the default. */
(function (w) {
  const base = 'Le Bus des Toutous', given = w.DOGCARE_BRAND || {};
  const name = String(given.name || base), custom = name !== base;
  const owner = custom ? String(given.owner || '') : 'Adine-Sophie', instagram = custom ? String(given.instagram || '') : 'bus_destoutous';
  const text = s => !custom || typeof s !== 'string' ? s : s.split('Adine-Sophie').join(owner || name).split('@bus_destoutous').join(instagram ? '@' + instagram : name).split(base).join(name);
  const map = value => typeof value === 'string' ? text(value) : Array.isArray(value) ? value.map(map) : value && typeof value === 'object' ? (Object.keys(value).forEach(k => { value[k] = map(value[k]); }), value) : value;
  // DC_BRAND_MARK=sun: a plain sixteen-ray sun drawn here, in place of the paw.
  const ray = (r, a) => (16 + r * Math.cos(a)).toFixed(1) + ' ' + (16 + r * Math.sin(a)).toFixed(1);
  const markSvg = custom && given.mark === 'sun' ? `<svg viewBox="0 0 32 32" width="26" height="26" fill="currentColor"><path d="${Array.from({length:16}, (_, i) => { const a = i * Math.PI / 8; return `M${ray(8.5, a - .2)}L${ray(i % 2 ? 13 : 15.5, a)}L${ray(8.5, a + .2)}Z`; }).join('')}"/><circle cx="16" cy="16" r="6" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="16" cy="16" r="2"/></svg>` : '';
  const mark = w.document?.querySelector('.workspace-mark');
  if (mark && markSvg) mark.innerHTML = markSvg;
  w.DogCareBrand = Object.freeze({ name, tagline: custom ? String(given.tagline || '') : '', owner, instagram, custom, markSvg, text, map });
})(window);

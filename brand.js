/* Instance brand. The API injects DOGCARE_BRAND only for a non-default instance; static mode is the default. */
(function (w) {
  const base = 'Le Bus des Toutous', given = w.DOGCARE_BRAND || {};
  const name = String(given.name || base), custom = name !== base;
  const owner = custom ? String(given.owner || '') : 'Adine-Sophie', instagram = custom ? String(given.instagram || '') : 'bus_destoutous';
  const text = s => !custom || typeof s !== 'string' ? s : s.split('Adine-Sophie').join(owner || name).split('@bus_destoutous').join(instagram ? '@' + instagram : name).split(base).join(name);
  const map = value => typeof value === 'string' ? text(value) : Array.isArray(value) ? value.map(map) : value && typeof value === 'object' ? (Object.keys(value).forEach(k => { value[k] = map(value[k]); }), value) : value;
  // DC_BRAND_MARK=sun: a plain sixteen-ray sun drawn here, in place of the paw.
  const ray = (r, a) => (16 + r * Math.cos(a)).toFixed(1) + ' ' + (16 + r * Math.sin(a)).toFixed(1);
  const sunSvg = `<svg viewBox="0 0 32 32" width="26" height="26" fill="currentColor"><path d="${Array.from({length:16}, (_, i) => { const a = i * Math.PI / 8; return `M${ray(8.5, a - .2)}L${ray(i % 2 ? 13 : 15.5, a)}L${ray(8.5, a + .2)}Z`; }).join('')}"/><circle cx="16" cy="16" r="6" fill="none" stroke="currentColor" stroke-width="2"/><circle cx="16" cy="16" r="2"/></svg>`;
  // DC_BRAND_MARK=dog: an original dog-head silhouette in profile. DC_BRAND_LOGO (served at given.logo) wins over both.
  const dogSvg = '<svg viewBox="0 0 32 32" width="26" height="26" fill="currentColor"><path fill-rule="evenodd" d="M6 30Q7.5 24 7 19Q5.8 13 9.6 9.4L10.2 2.8Q10.4 1.8 11.2 2.4L15.6 7.2Q18.4 7.2 20.4 9.6Q23 11.2 26.6 11.6Q29.4 12 29.2 14.6Q29 17 26.6 17.2L23 17.4Q21.8 20.4 18.6 21.2Q17.6 25 18.4 30ZM7.4 10.6L6.2 4.6Q6.2 3.6 7 4.2L9.2 7.4ZM16.4 12.4a1 1 0 1 0 .01 0Z"/></svg>';
  const logo = custom && typeof given.logo === 'string' && given.logo.startsWith('/') ? given.logo : '';
  const markSvg = !custom ? '' : logo ? `<img src="${logo}" alt="" width="26" height="26">` : given.mark === 'sun' ? sunSvg : given.mark === 'dog' ? dogSvg : '';
  const mark = w.document?.querySelector('.workspace-mark');
  if (mark && markSvg) mark.innerHTML = markSvg;
  const content = custom && given.content && typeof given.content === 'object' ? given.content : {};
  w.DogCareBrand = Object.freeze({ name, short: custom ? String(given.short || '') || name : name, tagline: custom ? String(given.tagline || '') : '', owner, instagram, custom, markSvg, content, text, map });
})(window);

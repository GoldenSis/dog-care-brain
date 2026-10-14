/* Private experience contract. Sourced guides live separately in knowledge-content.js. */
(function (w) {
  'use strict';
  const empty = () => ({version:1,experiences:[]});
  const object = value => value !== null && typeof value === 'object' && !Array.isArray(value);
  const fields = (value, keys) => object(value) && Object.keys(value).sort().join(' ') === keys.split(' ').sort().join(' ');
  const text = (value, limit, optional=false, multiline=false) => typeof value === 'string' &&
    [...value].length <= limit && (optional || value.trim().length > 0) &&
    !(multiline ? /[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/ : /[\x00-\x1f\x7f]/).test(value);
  function validLink(value) {
    if (!text(value,2000,true) || /\s|\\/.test(value)) return false;
    if (!value) return true;
    if(!/^https?:\/\//i.test(value))return false;
    try { const u=new URL(value);return ['http:','https:'].includes(u.protocol) && !!u.hostname && !u.username && !u.password; }
    catch { return false; }
  }
  function validate(value) {
    if(!fields(value,'version experiences') || value.version!==1 || !Array.isArray(value.experiences) || value.experiences.length>1000)throw Error('Invalid experience format');
    const ids=new Set();
    for(const item of value.experiences) {
      if(!fields(item,'id title body category author url status') || typeof item.id!=='string' ||
        !/^[A-Za-z0-9][A-Za-z0-9_-]{0,80}(?![\s\S])/.test(item.id) || ids.has(item.id) ||
        !text(item.title,120) || !text(item.body,4000,false,true) || !text(item.author,120,true) ||
        !validLink(item.url) || !['traditional','colleague'].includes(item.category) || item.status!=='draft')throw Error('Invalid private experience');
      ids.add(item.id);
    }
    return true;
  }
  w.KnowledgeModel={empty,validate,validLink};
}(window));

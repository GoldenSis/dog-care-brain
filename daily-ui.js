/* Daily work: views and explicit saves shared by static and account mode. */
(function (w) {
  'use strict';
  const M = w.DailyModel, KEY = 'dogcare-daily-v1';
  let daily = M.empty(), loadError = false, month = localDate().slice(0, 7), editing = null;
  const text = key => (w.DailyCopy[state.language] || w.DailyCopy.en)[key] || w.DailyCopy.en[key] || key;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function localDate() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }
  const id = () => crypto.randomUUID();
  const money = (minor, currency) => minor === null ? `${text('unknown')} (${currency})` : new Intl.NumberFormat(state.language,{style:'currency',currency,currencyDisplay:'code'}).format(minor / 100);
  const date = value => value ? new Intl.DateTimeFormat(state.language,{dateStyle:'medium',timeZone:'UTC'}).format(new Date(`${value}T12:00:00Z`)) : text('noDate');
  const client = dog => daily.clients.find(c => c.id === dog?.clientId)?.name || '';
  const label = (key, input) => `<label class="daily-field">${esc(text(key))}${input}</label>`;
  const input = (name, type='text', value='', extra='') => `<input name="${name}" type="${type}" value="${esc(value)}" ${extra}>`;
  const errorBox = () => `<p class="daily-error" role="alert" hidden></p>`;
  const storage = () => w.DogCareAPI ? '' : `<p class="daily-storage">${esc(text('browserOnly'))}</p>`;
  function unavailable() { return loadError ? `<p class="daily-error" role="alert">${esc(text('loadError'))}</p>` : ''; }
  function setError(form, key='saveError') { const e=form.querySelector('.daily-error'); e.hidden=false;e.textContent=text(key);e.scrollIntoView({block:'nearest'}); }
  function syncDogs() {
    for (const dog of daily.dogs) {
      const existing=Object.hasOwn(dogs,dog.id) ? dogs[dog.id] : null;
      dogs[dog.id]={...(existing || {emoji:'🐕',age:'Profile to complete',breed:'Breed to confirm',last:'',health:'Add current health and medication instructions.',behaviour:'Add routine, triggers and favourite rewards.',vet:'Add preferred vet and emergency contact',vets:[],needs:{energy:'Confirm with owner',movement:'Set a daily movement target',enrichment:'Add favourite enrichment',sensitivities:'Add sensitivities and recovery needs'},colour:''}),name:dog.name,owner:client(dog)};
      if (!Object.hasOwn(state.observations,dog.id)) state.observations[dog.id]=[];
    }
  }
  function load() {
    try {
      const raw=w.DogCareAPI ? w.DogCareAPI.getDaily() : JSON.parse(localStorage.getItem(KEY) || 'null');
      const candidate=raw || M.empty(); M.validateDaily(candidate); daily=candidate; syncDogs();
    } catch { loadError=true; }
  }
  async function save(next, button) {
    if(loadError)return false;
    try { M.validateDaily(next); } catch { return false; }
    const ok=await persistChange(async()=>{
      if(w.DogCareAPI)return w.DogCareAPI.saveDaily(next);
      try {localStorage.setItem(KEY,JSON.stringify(next));return true;} catch {return false;}
    },button);
    if(ok) { daily=w.DogCareAPI ? structuredClone(w.DogCareAPI.getDaily()) : next; syncDogs(); }
    return ok;
  }
  function ensureDog(next, dogId, name, clientName) {
    const clean=clientName.trim();
    if(!clean || !name.trim())throw Error('missing');
    let c=next.clients.find(c=>c.name.toLocaleLowerCase()===clean.toLocaleLowerCase());
    if(!c){c={id:id(),name:clean};next.clients.push(c);}
    let dog=next.dogs.find(d=>d.id===dogId);
    if(dog){ if(dog.clientId!==c.id)throw Error('client changed'); return dog; }
    dog={id:dogId || id(),name:name.trim(),clientId:c.id};next.dogs.push(dog);return dog;
  }
  function dogOptions(selected=state.dog) {return Object.entries(dogs).map(([key,d])=>`<option value="${esc(key)}" ${key===selected?'selected':''}>${esc(d.name)}</option>`).join('');}
  function followups() {
    const due=daily.documents.filter(d=>['due','overdue'].includes(M.documentStatus(d,localDate()))).sort((a,b)=>a.renewal.localeCompare(b.renewal));
    return `<section class="daily-followups"><h2>${esc(text('followup'))}</h2><p>${esc(text('followupHelp'))}</p>${due.length ? due.map(d=>`<button class="daily-record" data-document-dog="${esc(d.dogId)}"><span><strong>${esc(daily.dogs.find(x=>x.id===d.dogId)?.name)} · ${esc(d.label)}</strong><small>${esc(text(M.documentStatus(d,localDate())))} · ${esc(date(d.renewal))}</small></span><span aria-hidden="true">↗</span></button>`).join('') : `<p class="daily-empty">${esc(text('noFollowup'))}</p>`}</section>`;
  }
  function home() {
    return `${unavailable()}<section class="daily-home"><div><h2>${esc(text('dailyWork'))}</h2><p>${esc(text('dailyIntro'))}</p></div><div class="daily-shortcuts"><button class="primary" data-go="schedule">${esc(text('planning'))} ↗</button><button class="ghost" data-go="business">${esc(text('monthly'))} ↗</button><button class="ghost" data-go="dogs">${esc(text('documents'))} ↗</button></div></section>${followups()}`;
  }
  function bookingCard(b) {
    const dog=daily.dogs.find(d=>d.id===b.dogId);
    return `<article class="daily-record" data-booking-id="${esc(b.id)}"><div><strong>${esc(dog?.name)} · ${esc(client(dog))}</strong><p>${esc(text(b.service))} · ${esc(date(b.start))}${b.end!==b.start ? ` → ${esc(date(b.end))}` : ''}</p><small>${M.units(b)} ${esc(text('units'))} · ${esc(money(M.amount(b),b.currency))} · ${esc(text('planned'))}</small></div><button class="ghost" data-edit-booking="${esc(b.id)}">${esc(text('edit'))}</button></article>`;
  }
  function bookingForm() {
    const old=editing && daily.bookings.find(b=>b.id===editing), b=old || {dogId:state.dog,service:'day',start:localDate(),end:localDate()};
    const dog=daily.dogs.find(d=>d.id===b.dogId);
    return `<form id="booking-form" class="card daily-form" ${loadError?'inert':''}><h2 tabindex="-1">${esc(text(old?'editBooking':'newBooking'))}</h2><div class="daily-fields">${label('dog',`<select name="dogId" required>${dogOptions(b.dogId)}<option value="new">${esc(text('newDog'))}</option></select>`)}${label('client',`${input('client','text',dog?client(dog):dogs[b.dogId]?.owner || '','required maxlength="120" list="known-clients"')}<datalist id="known-clients">${daily.clients.map(c=>`<option value="${esc(c.name)}"></option>`).join('')}</datalist>`)}<label class="daily-field" id="new-dog-field" hidden>${esc(text('dogName'))}${input('dogName','text','','maxlength="120"')}</label>${label('service',`<select name="service">${['walk','day','night'].map(s=>`<option value="${s}" ${s===b.service?'selected':''}>${esc(text(s))}</option>`).join('')}</select>`)}${label('start',input('start','date',b.start,'required min="2000-01-01" max="2199-12-31"'))}${label('end',input('end','date',b.end,'required min="2000-01-01" max="2199-12-31"'))}${label('agreedRate',input('unitMinor','text',old ? (old.unitMinor===null?'':(old.unitMinor/100).toFixed(2)) : (daily.rates[b.service]===null?'':(daily.rates[b.service]/100).toFixed(2)),'inputmode="decimal" maxlength="12"'))}</div><p class="daily-help">${esc(text('fillUnknownRateHint'))}</p><p class="daily-help" id="unit-explanation"></p><div class="daily-quote" id="booking-quote" aria-live="polite"></div><p class="daily-help">${esc(text('agreementHelp'))}</p>${errorBox()}<div class="daily-actions"><button class="primary" type="submit">${esc(text('saveBooking'))}</button><button class="ghost" type="button" id="cancel-booking">${esc(text('cancel'))}</button></div></form>`;
  }
  function schedule() {
    const visible=daily.bookings.filter(b=>M.serviceDates(b).some(d=>d.startsWith(month))).sort((a,b)=>a.start.localeCompare(b.start));
    return `${storage()}${unavailable()}<div class="daily-toolbar"><button class="primary" id="new-booking" ${loadError?'disabled':''}>＋ ${esc(text('newBooking'))}</button></div><div id="booking-editor"></div>${monthControl()}<p class="daily-help">${esc(text('plannedHelp'))}</p><div id="booking-list">${visible.length?visible.map(bookingCard).join(''):`<p class="daily-empty">${esc(text('noBookings'))}</p>`}</div>${followups()}<p class="daily-help">${esc(text('ratesLink'))} <button class="link-button" data-go="business">${esc(text('rates'))} ↗</button></p>`;
  }
  function monthControl() { return `<div class="daily-month"><button class="ghost" data-month-step="-1" aria-label="${esc(text('previousMonth'))}">←</button>${label('month',input('month','month',month,'id="daily-month" required min="2000-01" max="2199-12"'))}<button class="ghost" data-month-step="1" aria-label="${esc(text('nextMonth'))}">→</button></div>`; }
  function business() {
    const rows=M.monthlySummary(daily,month);
    const totals={}; rows.forEach(r=>{totals[r.currency]??={known:0,unknown:0,knownUnits:0};totals[r.currency].known+=r.knownMinor;totals[r.currency].unknown+=r.unknownUnits;totals[r.currency].knownUnits+=r.units-r.unknownUnits;});
    return `${storage()}${unavailable()}${monthControl()}<p class="daily-help">${esc(text('summaryHelp'))}</p><div class="daily-summary">${rows.length?rows.map(r=>`<article class="daily-record"><div><strong>${esc(r.clientName)} · ${esc(text(r.service))}</strong><p>${r.bookingCount} ${esc(text('bookings'))} · ${r.units} ${esc(text('units'))}</p><small>${r.units===r.unknownUnits?'':`${esc(text(r.unknownUnits?'knownSubtotal':'knownAmount'))}: `}${esc(money(r.units===r.unknownUnits?null:r.knownMinor,r.currency))}${r.unknownUnits?` · ${r.unknownUnits} ${esc(text('unknownUnits'))}`:''}</small></div></article>`).join(''):`<p class="daily-empty">${esc(text('noBookings'))}</p>`}</div>${Object.entries(totals).map(([currency,total])=>`<p class="daily-total">${esc(text('knownSubtotal'))}: <strong>${esc(money(total.knownUnits?total.known:null,currency))}</strong>${total.unknown?` · ${total.unknown} ${esc(text('unknownUnits'))}`:''}</p>`).join('')}<details class="daily-help"><summary>${esc(text('calculation'))}</summary><p>${esc(text('allocationHelp'))}</p></details><form id="rates-form" class="card daily-form"><h2>${esc(text('rates'))}</h2><p>${esc(text('ratesHelp'))}</p><div class="daily-fields">${label('currency',`<select name="currency">${['CHF','EUR','GBP','USD'].map(c=>`<option ${c===daily.rates.currency?'selected':''}>${c}</option>`).join('')}</select>`)}${['walk','day','night'].map(s=>label(s,input(s,'text',daily.rates[s]===null?'':(daily.rates[s]/100).toFixed(2),'inputmode="decimal" maxlength="12" placeholder="—"'))).join('')}</div>${errorBox()}<button class="primary" ${loadError?'disabled':''}>${esc(text('saveRates'))}</button><p role="status" id="rates-saved"></p></form>`;
  }
  function documents(dogId) {
    const docs=daily.documents.filter(d=>d.dogId===dogId);
    return `<section class="card daily-documents" id="dog-documents"><h2>${esc(text('documents'))}</h2>${storage()}${unavailable()}<p class="daily-help">${esc(text('documentHelp'))}</p>${docs.map(d=>`<article class="daily-document" data-document-id="${esc(d.id)}"><strong>${esc(d.label)}</strong><p>${esc(text(M.documentStatus(d,localDate())))}${d.renewal?` · ${esc(date(d.renewal))}`:''}</p><div class="daily-actions"><button class="ghost" data-open-document="${esc(d.id)}">${esc(text('openDocument'))}</button></div><details><summary>${esc(text('editRenewal'))}</summary><form data-renewal="${esc(d.id)}" class="daily-form">${label('renewal',input('renewal','date',d.renewal,'min="2000-01-01" max="2199-12-31"'))}${errorBox()}<button class="ghost">${esc(text('saveDate'))}</button></form></details></article>`).join('') || `<p class="daily-empty">${esc(text('noDocuments'))}</p>`}<form id="document-form" class="daily-form"><div class="daily-fields">${label('documentLabel',input('label','text','','required maxlength="120"'))}${label('renewal',input('renewal','date','','min="2000-01-01" max="2199-12-31"'))}${label('file',input('file','file','','required accept="application/pdf,image/jpeg,image/png"'))}</div><p class="daily-help">PDF, JPEG, PNG · 5 MiB ${esc(text('maximum'))}</p>${errorBox()}<button class="primary" ${loadError?'disabled':''}>${esc(text('saveDocument'))}</button></form></section>`;
  }
  function quote(form) {
    const data=new FormData(form), old=editing && daily.bookings.find(b=>b.id===editing), service=data.get('service');
    const same=old && old.service===service;
    return {id:old?.id || id(),dogId:data.get('dogId'),service,start:data.get('start'),end:data.get('end'),unitMinor:same&&old.unitMinor!==null?old.unitMinor:M.parseMinor(data.get('unitMinor')),currency:same?old.currency:daily.rates.currency};
  }
  function updateQuote(form) {
    const panel=form.querySelector('#booking-quote'), old=editing && daily.bookings.find(x=>x.id===editing);
    try {
      const b=quote(form);
      form.querySelector('#unit-explanation').textContent=text(b.service==='night'?'nightHelp':'dayHelp');
      const units=M.units(b);
      panel.innerHTML=`<strong>${units} ${esc(text('units'))} · ${esc(money(M.amount(b),b.currency))}</strong><p>${esc(text('unitRate'))}: ${esc(money(b.unitMinor,b.currency))}</p>`;
      if(old && b.service===old.service && b.start===old.start && b.end>old.end){ const e=M.extension({...old,unitMinor:b.unitMinor},b.end);panel.innerHTML+=`<p>${esc(text('extension'))}: +${e.addedUnits} ${esc(text('units'))} · ${esc(money(e.addedMinor,b.currency))}<br>${esc(text('revisedTotal'))}: ${esc(money(e.totalMinor,b.currency))}</p>`; }
    } catch {panel.textContent=text('invalidDates');}
  }
  function editBooking(bookingId) {
    editing=bookingId;
    document.querySelector('.daily-toolbar').hidden=true;
    const editor=document.querySelector('#booking-editor');editor.innerHTML=bookingForm();
    const form=document.querySelector('#booking-form');
    function selectDog(){const choice=form.elements.dogId.value, registered=daily.dogs.find(d=>d.id===choice);form.querySelector('#new-dog-field').hidden=choice!=='new';form.elements.dogName.required=choice==='new';form.elements.client.value=registered?client(registered):dogs[choice]?.owner || '';form.elements.client.readOnly=!!registered;}
    form.elements.dogId.onchange=selectDog;selectDog();
    const old=editing && daily.bookings.find(b=>b.id===editing);
    function selectService(){const same=old && old.service===form.elements.service.value, amount=same?old.unitMinor:daily.rates[form.elements.service.value];form.elements.unitMinor.value=amount===null?'':(amount/100).toFixed(2);form.elements.unitMinor.readOnly=!!(same&&old.unitMinor!==null);}
    form.elements.service.onchange=selectService;selectService();
    form.addEventListener('input',()=>updateQuote(form));form.addEventListener('change',()=>updateQuote(form));updateQuote(form);
    form.querySelector('#cancel-booking').onclick=()=>{editor.innerHTML='';editing=null;document.querySelector('.daily-toolbar').hidden=false;document.querySelector('#new-booking').focus();};
    form.onsubmit=async e=>{
      e.preventDefault();const button=form.querySelector('[type="submit"]');
      try {
        const b=quote(form), next=structuredClone(daily), newDog=form.elements.dogId.value==='new';
        const dog=ensureDog(next,newDog?null:b.dogId,newDog?form.elements.dogName.value:dogs[b.dogId].name,form.elements.client.value);
        b.dogId=dog.id;M.units(b);
        const at=next.bookings.findIndex(x=>x.id===b.id);if(at<0)next.bookings.push(b);else next.bookings[at]=b;
        if(!await save(next,button)){setError(form);return;}
        month=b.start.slice(0,7);editing=null;navigate('schedule');showToast(text('saved'));
      }catch{setError(form,'invalidBooking');}
    };
    form.querySelector('h2').focus();form.scrollIntoView({block:'start'});
  }
  async function fileData(file) {
    if(!file || file.size===0 || file.size>5*1024*1024 || !['application/pdf','image/png','image/jpeg'].includes(file.type) || file.name.length>180)throw Error('file');
    const bytes=new Uint8Array(await file.arrayBuffer());
    const valid=file.type==='application/pdf'?String.fromCharCode(...bytes.slice(0,5))==='%PDF-':file.type==='image/png'?[137,80,78,71,13,10,26,10].every((x,i)=>bytes[i]===x):bytes[0]===255&&bytes[1]===216&&bytes[2]===255;
    if(!valid)throw Error('file');
    let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));return btoa(binary);
  }
  async function openDocument(doc, button) {
    try {
      let blob;
      if(w.DogCareAPI){blob=await w.DogCareAPI.getDocument(doc.id);if(!blob)throw Error('load');}
      else {const binary=atob(doc.data);blob=new Blob([Uint8Array.from(binary,c=>c.charCodeAt(0))],{type:doc.type});}
      const url=URL.createObjectURL(blob), link=document.createElement('a');link.href=url;link.download=doc.name;link.click();setTimeout(()=>URL.revokeObjectURL(url),60000);
    }catch{showToast(text('documentError'));button.focus();}
  }
  function bind() {
    document.querySelector('#new-booking')?.addEventListener('click',()=>editBooking(null));
    document.querySelectorAll('[data-edit-booking]').forEach(b=>b.onclick=()=>editBooking(b.dataset.editBooking));
    document.querySelectorAll('[data-document-dog]').forEach(b=>b.onclick=()=>{state.dog=b.dataset.documentDog;navigate('dogs');document.querySelector('#dog-documents')?.scrollIntoView({block:'start'});});
    document.querySelectorAll('[data-month-step]').forEach(b=>b.onclick=()=>{const [y,m]=month.split('-').map(Number), d=new Date(Date.UTC(y,m-1+Number(b.dataset.monthStep),1));const value=d.toISOString().slice(0,7);if(value>='2000-01'&&value<='2199-12'){month=value;navigate(state.page);document.querySelector('#daily-month')?.focus();}});
    document.querySelector('#daily-month')?.addEventListener('change',e=>{if(/^20\d\d-\d\d$|^21\d\d-\d\d$/.test(e.target.value)){month=e.target.value;navigate(state.page);}});
    const rates=document.querySelector('#rates-form');if(rates)rates.onsubmit=async e=>{e.preventDefault();try{const next=structuredClone(daily);next.rates={currency:rates.elements.currency.value,...Object.fromEntries(['walk','day','night'].map(s=>[s,M.parseMinor(rates.elements[s].value)]))};if(!await save(next,rates.querySelector('button'))){setError(rates);return;}rates.querySelector('.daily-error').hidden=true;document.querySelector('#rates-saved').textContent=text('saved');}catch{setError(rates,'invalidRate');}};
    document.querySelectorAll('[data-open-document]').forEach(b=>b.onclick=()=>openDocument(daily.documents.find(d=>d.id===b.dataset.openDocument),b));
    document.querySelectorAll('[data-renewal]').forEach(form=>form.onsubmit=async e=>{e.preventDefault();const next=structuredClone(daily);next.documents.find(d=>d.id===form.dataset.renewal).renewal=form.elements.renewal.value;if(!await save(next,form.querySelector('button'))){setError(form);return;}navigate('dogs');document.querySelector('#dog-documents').scrollIntoView({block:'start'});});
    const form=document.querySelector('#document-form');if(form)form.onsubmit=async e=>{
      e.preventDefault();const button=form.querySelector('button'), file=form.elements.file.files[0];let data;
      try{data=await fileData(file);}catch{setError(form,'invalidFile');return;}
      const next=structuredClone(daily), profile=dogs[state.dog];
      try{ensureDog(next,state.dog,profile.name,profile.owner);}catch{setError(form,'clientRequired');return;}
      if(!daily.dogs.some(d=>d.id===state.dog) && !await save(next,button)){setError(form);return;}
      const doc={dogId:state.dog,label:form.elements.label.value.trim(),renewal:form.elements.renewal.value,name:file.name,type:file.type,data};
      let ok;
      if(w.DogCareAPI){ok=await persistChange(()=>w.DogCareAPI.saveDocument(doc),button);if(ok){daily=structuredClone(w.DogCareAPI.getDaily());syncDogs();}}
      else {next.documents.push({...doc,id:id()});ok=await save(next,button);}
      if(!ok){setError(form);return;}navigate('dogs');document.querySelector('#dog-documents').scrollIntoView({block:'start'});showToast(text('saved'));
    };
  }
  w.DailyUI={text,load,home,schedule,business,documents,bind};
})(window);

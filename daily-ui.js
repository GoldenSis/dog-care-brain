/* Daily work: views and explicit saves shared by static and account mode. */
(function (w) {
  'use strict';
  const M = w.DailyModel, KEY = 'dogcare-daily-v1', CREATE_DOG = ':new';
  let daily = M.empty(), loadError = false, month = localDate().slice(0, 7), editing = null;
  let localSnapshot = null, localStale = false;
  let dogDraft = null, dogListOpen = false, walkDate = localDate();
  const text = key => (w.DailyCopy[state.language] || w.DailyCopy.en)[key] || w.DailyCopy.en[key] || key;
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  function localDate() { const d = new Date(); return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`; }
  const id = () => crypto.randomUUID();
  const money = (minor, currency) => minor === null ? `${text('unknown')} (${currency})` : new Intl.NumberFormat(formatLocale(Intl.NumberFormat),{style:'currency',currency,currencyDisplay:'code',minimumFractionDigits:2,maximumFractionDigits:2}).format(minor / 100);
  const date = value => value ? new Intl.DateTimeFormat(formatLocale(Intl.DateTimeFormat),{dateStyle:'medium',timeZone:'UTC'}).format(new Date(`${value}T12:00:00Z`)) : text('noDate');
  const client = dog => daily.clients.find(c => c.id === dog?.clientId)?.name || '';
  const carer = () => w.DogCareAPI?.getUser()?.role === 'trusted-carer';
  const fill = (key, values) => text(key).replace(/\{(\w+)\}/g, (_, name) => values[name]);
  const tariffText = tariff => tariff ? `${money(tariff.unitMinor,tariff.currency)} ${text('perWalk')}` : text('noTariff');
  const currencyChoices = selected => { const list=['CHF','EUR','GBP','USD']; if(!list.includes(selected))list.push(selected); return list.map(c=>`<option value="${esc(c)}" ${c===selected?'selected':''}>${esc(c)}</option>`).join(''); };
  const label = (key, input) => `<label class="daily-field">${esc(text(key))}${input}</label>`;
  const input = (name, type='text', value='', extra='') => `<input name="${name}" type="${type}" value="${esc(value)}" ${extra}>`;
  const errorBox = () => `<p class="daily-error" role="alert" hidden></p>`;
  const storage = () => w.DogCareAPI ? '' : `<p class="daily-storage">${esc(text('browserOnly'))}</p>`;
  function unavailable() { return loadError ? `<p class="daily-error" role="alert">${esc(text('loadError'))}</p>` : ''; }
  function setError(form, key='saveError') {
    if(key==='saveError' && !w.DogCareAPI)key=localStale?'staleSave':!w.navigator.locks?'storageUnavailable':key;
    const e=form.querySelector('.daily-error');e.hidden=false;e.textContent=text(key);e.scrollIntoView({block:'nearest'});
  }
  function syncDogs() {
    const profiles=new Map((w.DogCareAPI?.getDogs() || []).map(dog=>[dog.slug,{id:dog.slug,name:dog.name}]));
    for (const dog of daily.dogs) profiles.set(dog.id,{...dog,owner:client(dog)});
    if(w.DogCareAPI){
      for(const key of Object.keys(dogs))if(!profiles.has(key))delete dogs[key];
    }
    for (const dog of profiles.values()) {
      const existing=Object.hasOwn(dogs,dog.id) ? dogs[dog.id] : null;
      dogs[dog.id]={...(existing || {emoji:'🐕',age:'Profile to complete',breed:'Breed to confirm',last:'',health:'Add current health and medication instructions.',behaviour:'Add routine, triggers and favourite rewards.',vet:'Add preferred vet and emergency contact',vets:[],needs:{energy:'Confirm with owner',movement:'Set a daily movement target',enrichment:'Add favourite enrichment',sensitivities:'Add sensitivities and recovery needs'},colour:''}),name:dog.name,owner:dog.owner ?? existing?.owner ?? ''};
      if (!Object.hasOwn(state.observations,dog.id)) state.observations[dog.id]=[];
    }
  }
  function load() {
    try {
      if(!w.DogCareAPI)localSnapshot=localStorage.getItem(KEY);
      const raw=w.DogCareAPI ? w.DogCareAPI.getDaily() : JSON.parse(localSnapshot || 'null');
      const candidate=!w.DogCareAPI && localSnapshot===null ? M.empty() : M.upgrade(raw); M.validateDaily(candidate); daily=candidate;
    } catch { loadError=true; }
    syncDogs();
    if(!Object.hasOwn(dogs,state.dog))state.dog=Object.keys(dogs)[0] || '';
  }
  async function commitDaily(next) {
    if(loadError)return false;
    try { M.validateDaily(next); } catch { return false; }
    const ok=await (async()=>{
      if(w.DogCareAPI)return w.DogCareAPI.saveDaily(next);
      if(localStale || !w.navigator.locks)return false;
      try {
        return await w.navigator.locks.request(KEY,()=>{
          if(localStorage.getItem(KEY)!==localSnapshot){localStale=true;return false;}
          const serialized=JSON.stringify(next);
          localStorage.setItem(KEY,serialized);
          localSnapshot=serialized;
          return true;
        });
      } catch {return false;}
    })();
    if(ok) { daily=w.DogCareAPI ? structuredClone(w.DogCareAPI.getDaily()) : next; syncDogs(); }
    return ok;
  }
  function save(next, button) { return persistChange(()=>commitDaily(next),button); }
  function ensureDog(next, dogId, name, clientName, requireClient=false, clientId) {
    const registered=next.dogs.find(d=>d.id===dogId);
    if(registered && (!requireClient || registered.clientId))return registered;
    if(!name.trim())throw Error('missing');
    let c;
    if(clientId===':new'){
      if(!clientName.trim())throw Error('missing');
      c={id:id(),name:clientName};next.clients.push(c);
    }else{c=next.clients.find(c=>c.id===clientId);if(!c)throw Error('missing');}
    if(registered){registered.clientId=c.id;return registered;}
    const dog={id:dogId || id(),name,clientId:c.id,walkTariff:null};next.dogs.push(dog);return dog;
  }
  function rememberDogDraft() {
    const form=document.querySelector('#dog-form');
    if(form && dogDraft)for(const key of ['dogName','clientId','clientName'])dogDraft[key]=form.elements[key].value;
  }
  function dogControls() {
    const showList=dogListOpen || !Object.keys(dogs).length;
    return `${unavailable()}<div class="daily-toolbar dog-toolbar"><button class="primary" id="new-dog" aria-expanded="${!!dogDraft}" aria-controls="dog-editor" ${loadError?'disabled':''}>＋ ${esc(text('newDog'))}</button><button class="ghost" id="dog-list-toggle" aria-expanded="${showList}" aria-controls="dog-directory">${esc(text('allDogs'))}</button></div><div id="dog-directory" ${showList?'':'hidden'}>${showList?`<div class="dog-directory">${Object.entries(dogs).map(([key,d])=>`<button class="ghost" data-select-profile="${esc(key)}" aria-pressed="${key===state.dog}"><strong translate="no">${esc(d.name)}</strong>${d.owner?`<small translate="no">${esc(d.owner)}</small>`:''}${w.PortalUI.owner()?`<small>${esc(tariffText(daily.dogs.find(x=>x.id===key)?.walkTariff ?? null))}</small>`:''}</button>`).join('') || `<p class="daily-empty">${esc(text('noDogs'))}</p>`}</div>`:''}</div><div id="dog-editor">${dogDraft?dogForm():''}</div>`;
  }
  function dogForm() {
    return `<form id="dog-form" class="card daily-form"><h2>${esc(text('newDog'))}</h2><p class="daily-help">${esc(text('dogFormHelp'))}</p><div class="daily-fields">${label('dogName',input('dogName','text',dogDraft.dogName,'required pattern="[\\s\\S]{0,120}" autocomplete="off"'))}${label('optionalOwner',`<select name="clientId"><option value="">${esc(text('ownerLater'))}</option>${daily.clients.map(c=>`<option translate="no" value="${esc(c.id)}" ${dogDraft.clientId===c.id?'selected':''}>${esc(c.name)}</option>`).join('')}<option value=":new" ${dogDraft.clientId===':new'?'selected':''}>${esc(text('newOwner'))}</option></select>`)}<label class="daily-field" id="dog-owner-field" ${dogDraft.clientId===':new'?'':'hidden'}>${esc(text('ownerName'))}${input('clientName','text',dogDraft.clientName,'pattern="[\\s\\S]{0,120}" autocomplete="off"')}</label></div><p class="daily-help">${esc(text('dogDraftHelp'))}</p><p class="daily-error" role="alert" ${dogDraft.error?'':'hidden'}>${dogDraft.error?esc(text(dogDraft.error)):''}</p><div class="daily-actions"><button class="primary" type="submit">${esc(text('saveDog'))}</button><button class="ghost" type="button" id="cancel-dog">${esc(text('cancel'))}</button></div></form>`;
  }
  function bindDogRegistration() {
    document.querySelector('#new-dog')?.addEventListener('click',()=>{
      rememberDogDraft();dogDraft??={id:id(),dogName:'',clientId:'',clientName:'',error:null};navigate('dogs');document.querySelector('#dog-form [name="dogName"]').focus();
    });
    document.querySelector('#dog-list-toggle')?.addEventListener('click',()=>{dogListOpen=!dogListOpen;navigate('dogs');document.querySelector('#dog-list-toggle').focus();});
    document.querySelectorAll('[data-select-profile]').forEach(b=>b.onclick=()=>{state.dog=b.dataset.selectProfile;dogListOpen=false;navigate('dogs');document.querySelector('#page-title').focus();});
    const form=document.querySelector('#dog-form');if(!form)return;
    function ownerChoice(){const active=form.elements.clientId.value===':new';form.querySelector('#dog-owner-field').hidden=!active;form.elements.clientName.disabled=!active;form.elements.clientName.required=active;}
    ownerChoice();form.elements.clientId.addEventListener('change',ownerChoice);
    form.addEventListener('input',rememberDogDraft);form.addEventListener('change',rememberDogDraft);
    form.querySelector('#cancel-dog').onclick=()=>{dogDraft=null;navigate('dogs');document.querySelector('#new-dog').focus();};
    form.onsubmit=async event=>{
      event.preventDefault();if(savePending || loadError)return;rememberDogDraft();
      const draft=dogDraft, next=structuredClone(daily);let clientId=draft.clientId || null;
      try {
        if(clientId===':new'){clientId=id();next.clients.push({id:clientId,name:draft.clientName});}
        next.dogs.push({id:draft.id,name:draft.dogName,clientId,walkTariff:null});M.validateDaily(next);
      }catch{draft.error='invalidDog';setError(form,'invalidDog');return;}
      if(!await save(next,form.querySelector('[type="submit"]'))){draft.error='saveError';setError(form);return;}
      dogDraft=null;state.dog=draft.id;dogListOpen=false;navigate('dogs');document.querySelector('#page-title').focus();showToast(text('saved'));
    };
  }
  // A care profile without a daily record is registered on its first tariff or
  // walk, with no owner: only the facts entered are recorded.
  function registeredDog(next, dogId) {
    let dog=next.dogs.find(d=>d.id===dogId);
    if(!dog){dog={id:dogId,name:dogs[dogId].name,clientId:null,walkTariff:null};next.dogs.push(dog);}
    return dog;
  }
  function tariff(dogId) {
    if(!w.PortalUI.owner())return '';
    const current=daily.dogs.find(d=>d.id===dogId)?.walkTariff ?? null;
    return `<form id="tariff-form" class="card daily-form" ${loadError?'inert':''}><h2>${esc(text('walkTariff'))}</h2><p class="daily-help">${esc(text('walkTariffHelp'))}</p><div class="daily-fields">${label('walkTariff',input('tariff','text',current?(current.unitMinor/100).toFixed(2):'','inputmode="decimal" maxlength="12" placeholder="—" autocomplete="off"'))}${label('currency',`<select name="currency">${currencyChoices(current?.currency || daily.rates.currency)}</select>`)}</div>${errorBox()}<div class="daily-actions"><button class="primary" type="submit">${esc(text('saveTariff'))}</button></div><p role="status" id="tariff-saved"></p></form>`;
  }
  function walkChecklist() {
    const done=new Set(daily.walks.filter(x=>x.date===walkDate).map(x=>x.dogId));
    const list=Object.entries(dogs).sort(([,a],[,b])=>a.name.localeCompare(b.name,formatLocale(Intl.Collator)));
    const priced=w.PortalUI.owner();
    return `<section class="card daily-form daily-walks" id="walk-checklist" ${loadError?'inert':''}><h2>${esc(text('walkChecklist'))}</h2><p class="daily-help">${esc(text('walkChecklistHelp'))}</p><form id="walk-form"><div class="daily-fields">${label('walkDate',input('date','date',walkDate,`id="walk-date" required min="2000-01-01" max="${localDate()}"`))}</div>${list.length?`<fieldset class="walk-list"><legend class="sr-only">${esc(text('walkDogs'))}</legend>${list.map(([key,d])=>{const record=daily.dogs.find(x=>x.id===key), owner=client(record);return `<label class="walk-dog"><input type="checkbox" name="walked" value="${esc(key)}" ${done.has(key)?'checked':''}><span><strong translate="no">${esc(d.name)}</strong>${owner?`<small translate="no">${esc(owner)}</small>`:''}${priced?`<small>${esc(tariffText(record?.walkTariff ?? null))}</small>`:''}</span></label>`;}).join('')}</fieldset><p class="daily-help" id="walk-count" aria-live="polite">${esc(fill('walkCount',{count:done.size}))}</p>${errorBox()}<div class="daily-actions"><button class="primary" type="submit">${esc(text('saveWalks'))}</button>${priced?`<button class="ghost" type="button" data-go="business" data-finance-walks>${esc(text('walkTotalsLink'))} ↗</button>`:''}</div>`:`<p class="daily-empty">${esc(text('noWalkDogs'))}</p>`}</form></section>`;
  }
  function walkMonth() {
    const summary=M.walkSummary(daily,month), current=new Map(daily.dogs.map(d=>[d.id,d.walkTariff]));
    const amounts=totals=>Object.entries(totals).map(([currency,minor])=>money(minor,currency)).join(' · ');
    const rows=summary.rows.sort((a,b)=>a.dogName.localeCompare(b.dogName,formatLocale(Intl.Collator)));
    return `${storage()}${unavailable()}<section class="daily-walk-month" id="walk-month"><h2>${esc(text('monthWalks'))}</h2>${monthControl()}<p class="daily-help">${esc(text('monthWalksHelp'))}</p>${rows.length?rows.map(r=>{
      const tariffNow=current.get(r.dogId);
      const lines=[...r.lines.map(l=>`${l.count} × ${money(l.tariff.unitMinor,l.tariff.currency)} = ${money(l.totalMinor,l.tariff.currency)}`),...(r.unpriced?[fill('unpricedWalks',{count:r.unpriced})]:[])];
      return `<article class="daily-record" data-walk-dog="${esc(r.dogId)}"><div><strong translate="no">${esc(r.dogName)}</strong><p>${esc(fill('walksCount',{count:r.count}))}</p><small>${lines.map(esc).join('<br>')}</small>${r.unpriced&&tariffNow&&!carer()?`<div class="daily-actions"><button class="ghost" data-apply-tariff="${esc(r.dogId)}">${esc(fill('applyTariff',{price:money(tariffNow.unitMinor,tariffNow.currency),count:r.unpriced}))}</button></div>`:''}</div><strong class="walk-amount">${esc(amounts(r.totals) || '—')}</strong></article>`;
    }).join(''):`<p class="daily-empty">${esc(text('noMonthWalks'))}</p>`}${rows.length?`<p class="daily-total">${esc(text('monthTotal'))} · ${esc(fill('walksCount',{count:summary.count}))}${summary.unpriced?` · ${esc(fill('unpricedWalks',{count:summary.unpriced}))}`:''}: <strong>${esc(amounts(summary.totals) || '—')}</strong></p>`:''}${errorBox()}</section>`;
  }
  function bindWalks() {
    const form=document.querySelector('#walk-form');
    if(form){
      const count=()=>{form.querySelector('#walk-count').textContent=fill('walkCount',{count:form.querySelectorAll('[name="walked"]:checked').length});};
      form.querySelectorAll('[name="walked"]').forEach(box=>box.onchange=count);
      form.elements.date.onchange=()=>{
        if(!M.validDate(form.elements.date.value) || form.elements.date.value>localDate())return;
        walkDate=form.elements.date.value;
        document.querySelector('#walk-checklist').outerHTML=walkChecklist();bindWalks();
        document.querySelector('#walk-date').focus();
      };
      form.onsubmit=async event=>{
        event.preventDefault();if(savePending || loadError)return;
        const day=form.elements.date.value;
        if(!M.validDate(day) || day>localDate()){setError(form,'walkFuture');return;}
        const ticked=new Set([...form.querySelectorAll('[name="walked"]:checked')].map(box=>box.value));
        const next=structuredClone(daily);
        next.walks=next.walks.filter(x=>x.date!==day || ticked.has(x.dogId));
        for(const dogId of ticked){
          if(next.walks.some(x=>x.date===day && x.dogId===dogId))continue;
          next.walks.push(M.recordWalk(registeredDog(next,dogId),day,id()));
        }
        if(!await save(next,form.querySelector('[type="submit"]'))){setError(form);return;}
        walkDate=day;navigate('schedule');document.querySelector('#walk-date')?.focus();showToast(text('walksSaved'));
      };
    }
    const prices=document.querySelector('#tariff-form'), dogId=state.dog;
    if(prices){
      const saved=prices.querySelector('#tariff-saved');
      prices.addEventListener('input',()=>{saved.textContent='';});
      prices.onsubmit=async event=>{
        event.preventDefault();if(savePending || loadError)return;saved.textContent='';
        let unitMinor;
        try{unitMinor=M.parseMinor(prices.elements.tariff.value);}catch{setError(prices,'invalidTariff');return;}
        const next=structuredClone(daily);
        registeredDog(next,dogId).walkTariff=unitMinor===null?null:{unitMinor,currency:prices.elements.currency.value};
        if(!await save(next,prices.querySelector('[type="submit"]'))){setError(prices);return;}
        prices.querySelector('.daily-error').hidden=true;saved.textContent=text('saved');
      };
    }
    document.querySelectorAll('[data-apply-tariff]').forEach(button=>button.onclick=async()=>{
      if(savePending || loadError || !w.confirm(text('applyTariffConfirm')))return;
      const next=structuredClone(daily), dog=next.dogs.find(d=>d.id===button.dataset.applyTariff);
      for(const walk of next.walks)if(walk.dogId===dog.id && walk.tariff===null && walk.date.startsWith(month))walk.tariff={...dog.walkTariff};
      if(!await save(next,button)){setError(document.querySelector('#walk-month'));return;}
      navigate('business');showToast(text('saved'));
    });
  }
  function dogOptions(selected=state.dog) {return Object.entries(dogs).map(([key,d])=>`<option translate="no" value="${esc(key)}" ${key===selected?'selected':''}>${esc(d.name)}</option>`).join('');}
  function followups() {
    const due=daily.documents.filter(d=>['due','overdue'].includes(M.documentStatus(d,localDate()))).sort((a,b)=>a.renewal.localeCompare(b.renewal));
    return `<section class="daily-followups"><h2>${esc(text('followup'))}</h2><p>${esc(text('followupHelp'))}</p>${due.length ? due.map(d=>`<button class="daily-record" data-document-dog="${esc(d.dogId)}"><span><strong translate="no">${esc(daily.dogs.find(x=>x.id===d.dogId)?.name)} · ${esc(d.label)}</strong><small>${esc(text(M.documentStatus(d,localDate())))} · ${esc(date(d.renewal))}</small></span><span aria-hidden="true">↗</span></button>`).join('') : `<p class="daily-empty">${esc(text('noFollowup'))}</p>`}</section>`;
  }
  function home() {
    return `${unavailable()}<section class="daily-home"><div><h2>${esc(text('dailyWork'))}</h2><p>${esc(text('dailyIntro'))}</p></div><div class="daily-shortcuts"><button class="primary" data-go="schedule">${esc(text('planning'))} ↗</button><button class="ghost" data-go="business" data-finance-rates>${esc(text('monthly'))} ↗</button><button class="ghost" data-go="dogs">${esc(text('documents'))} ↗</button></div></section>${followups()}`;
  }
  function bookingCard(b, associations, dogIndex, clientIndex) {
    const dog=dogIndex.get(b.dogId), clientId=M.bookingClientId(b,dog,associations);
    const family=clientIndex.get(clientId)?.name || text('unknown');
    return `<article class="daily-record" data-booking-id="${esc(b.id)}"><div><strong translate="no">${esc(dog?.name)} · ${esc(family)}</strong><p>${esc(text(b.service))} · ${esc(date(b.start))}${b.end!==b.start ? ` → ${esc(date(b.end))}` : ''}</p><small>${M.units(b)} ${esc(text('units'))} · ${esc(money(M.amount(b),b.currency))} · ${esc(text(M.activeBooking(b)?'planned':'cancelled'))}</small></div>${M.activeBooking(b)?`<div class="daily-actions"><button class="ghost" data-edit-booking="${esc(b.id)}">${esc(text('edit'))}</button>${w.PortalUI.owner()?`<button class="ghost" data-cancel-booking="${esc(b.id)}">${esc(text('cancelSavedBooking'))}</button>`:''}</div>`:''}</article>`;
  }
  function ownerControls(name='',choose=false) {
    return `${label('client',`<select name="clientId" required>${choose?`<option value="">${esc(text('chooseOwner'))}</option>`:''}<option value=":new">${esc(text('newOwner'))}</option>${daily.clients.map(c=>`<option translate="no" value="${esc(c.id)}">${esc(c.name)}</option>`).join('')}</select>`)}${label('ownerName',input('client','text',name,'required pattern="[\\s\\S]{0,120}"'))}`;
  }
  function bindOwnerChoice(form,initial,fallback='') {
    function selectOwner(){const choice=form.elements.clientId.value,c=daily.clients.find(c=>c.id===choice);form.elements.client.value=c?.name ?? fallback;form.elements.client.readOnly=!!c;form.elements.client.disabled=!choice;}
    form.elements.clientId.value=initial;form.elements.clientId.onchange=selectOwner;selectOwner();
  }
  function bookingForm() {
    const old=editing && daily.bookings.find(b=>b.id===editing), b=old || {dogId:state.dog,service:'day',start:localDate(),end:localDate()};
    const dog=daily.dogs.find(d=>d.id===b.dogId);
    return `<form id="booking-form" class="card daily-form" ${loadError?'inert':''}><h2 tabindex="-1">${esc(text(old?'editBooking':'newBooking'))}</h2><div class="daily-fields">${label('dog',`<select name="dogId" required>${dogOptions(b.dogId)}<option value="${CREATE_DOG}">${esc(text('newDog'))}</option></select>`)}${ownerControls(dog?client(dog):dogs[b.dogId]?.owner || '')}<label class="daily-field" id="new-dog-field" hidden>${esc(text('dogName'))}${input('dogName','text','','pattern="[\\s\\S]{0,120}"')}</label>${label('service',`<select name="service">${['walk','day','night'].map(s=>`<option value="${s}" ${s===b.service?'selected':''}>${esc(text(s))}</option>`).join('')}</select>`)}${label('start',input('start','date',b.start,'required min="2000-01-01" max="2199-12-31"'))}${label('end',input('end','date',b.end,'required min="2000-01-01" max="2199-12-31"'))}${label('agreedRate',input('unitMinor','text',old ? (old.unitMinor===null?'':(old.unitMinor/100).toFixed(2)) : (daily.rates[b.service]===null?'':(daily.rates[b.service]/100).toFixed(2)),'inputmode="decimal" maxlength="12"'))}</div><p class="daily-help">${esc(text(carer()?'carerRateHint':'fillUnknownRateHint'))}</p><p class="daily-help" id="unit-explanation"></p><div class="daily-quote" id="booking-quote" aria-live="polite"></div>${carer()?'':`<p class="daily-help">${esc(text('agreementHelp'))}</p>`}${errorBox()}<div class="daily-actions"><button class="primary" type="submit">${esc(text('saveBooking'))}</button><button class="ghost" type="button" id="cancel-booking">${esc(text('cancel'))}</button></div></form>`;
  }
  function schedule() {
    const associations=w.DogCareAPI?.getPortal()?.bookingClients || {},dogIndex=new Map(daily.dogs.map(d=>[d.id,d])),clientIndex=new Map(daily.clients.map(c=>[c.id,c]));
    const visible=daily.bookings.filter(b=>M.serviceDates(b).some(d=>d.startsWith(month))).sort((a,b)=>a.start.localeCompare(b.start));
    const active=visible.filter(M.activeBooking),cancelled=visible.filter(b=>!M.activeBooking(b));
    return `${storage()}${unavailable()}${walkChecklist()}<div class="daily-toolbar"><button class="primary" id="new-booking" ${loadError?'disabled':''}>＋ ${esc(text('newBooking'))}</button></div><div id="booking-editor"></div>${monthControl()}<p class="daily-help">${esc(text('plannedHelp'))}</p><div id="booking-list">${active.length?active.map(b=>bookingCard(b,associations,dogIndex,clientIndex)).join(''):`<p class="daily-empty">${esc(text('noBookings'))}</p>`}</div>${cancelled.length?`<details id="cancelled-bookings"><summary>${esc(text('cancelledBookings'))} (${cancelled.length})</summary>${cancelled.map(b=>bookingCard(b,associations,dogIndex,clientIndex)).join('')}</details>`:''}${followups()}${carer()?'':`<p class="daily-help">${esc(text('ratesLink'))} <button class="link-button" data-go="business" data-finance-rates>${esc(text('rates'))} ↗</button></p>`}`;
  }
  function monthControl() { return `<div class="daily-month"><button class="ghost" data-month-step="-1" aria-label="${esc(text('previousMonth'))}">←</button>${label('month',input('month','month',month,'id="daily-month" required min="2000-01" max="2199-12"'))}<button class="ghost" data-month-step="1" aria-label="${esc(text('nextMonth'))}">→</button></div>`; }
  function business() {
    const currencies=['CHF','EUR','GBP','USD'];
    if(!currencies.includes(daily.rates.currency))currencies.push(daily.rates.currency);
    const rows=M.monthlySummary(daily,month,w.DogCareAPI?.getPortal()?.bookingClients);
    const totals={}; rows.forEach(r=>{totals[r.currency]??={known:0,unknown:0,knownUnits:0};totals[r.currency].known+=r.knownMinor;totals[r.currency].unknown+=r.unknownUnits;totals[r.currency].knownUnits+=r.units-r.unknownUnits;});
    return `${storage()}${unavailable()}${monthControl()}<p class="daily-help">${esc(text('summaryHelp'))}</p><div class="daily-summary">${rows.length?rows.map(r=>`<article class="daily-record"><div><strong><span translate="no">${esc(r.clientName || text('unknown'))}</span> · ${esc(text(r.service))}</strong><p>${r.bookingCount} ${esc(text('bookings'))} · ${r.units} ${esc(text('units'))}</p><small>${r.units===r.unknownUnits?'':`${esc(text(r.unknownUnits?'knownSubtotal':'knownAmount'))}: `}${esc(money(r.units===r.unknownUnits?null:r.knownMinor,r.currency))}${r.unknownUnits?` · ${r.unknownUnits} ${esc(text('unknownUnits'))}`:''}</small></div></article>`).join(''):`<p class="daily-empty">${esc(text('noBookings'))}</p>`}</div>${Object.entries(totals).map(([currency,total])=>`<p class="daily-total">${esc(text('knownSubtotal'))}: <strong>${esc(money(total.knownUnits?total.known:null,currency))}</strong>${total.unknown?` · ${total.unknown} ${esc(text('unknownUnits'))}`:''}</p>`).join('')}<details class="daily-help"><summary>${esc(text('calculation'))}</summary><p>${esc(text('allocationHelp'))}</p></details><form id="rates-form" class="card daily-form"><h2>${esc(text('rates'))}</h2><p>${esc(text('ratesHelp'))}</p><div class="daily-fields">${label('currency',`<select name="currency">${currencies.map(c=>`<option value="${esc(c)}" ${c===daily.rates.currency?'selected':''}>${esc(c)}</option>`).join('')}</select>`)}${['walk','day','night'].map(s=>label(s,input(s,'text',daily.rates[s]===null?'':(daily.rates[s]/100).toFixed(2),'inputmode="decimal" maxlength="12" placeholder="—"'))).join('')}</div>${errorBox()}<button class="primary" ${loadError?'disabled':''}>${esc(text('saveRates'))}</button><p role="status" id="rates-saved"></p></form>`;
  }
  function documents(dogId) {
    const docs=daily.documents.filter(d=>d.dogId===dogId),registered=daily.dogs.some(d=>d.id===dogId);
    return `<section class="card daily-documents" id="dog-documents"><h2>${esc(text('documents'))}</h2>${storage()}${unavailable()}<p class="daily-help">${esc(text('documentHelp'))}</p>${docs.map(d=>`<article class="daily-document" data-document-id="${esc(d.id)}"><strong translate="no">${esc(d.label)}</strong><p>${esc(text(M.documentStatus(d,localDate())))}${d.renewal?` · ${esc(date(d.renewal))}`:''}</p><div class="daily-actions"><button class="ghost" data-open-document="${esc(d.id)}">${esc(text('openDocument'))}</button></div><details><summary>${esc(text('editRenewal'))}</summary><form data-renewal="${esc(d.id)}" class="daily-form">${label('renewal',input('renewal','date',d.renewal,'min="2000-01-01" max="2199-12-31"'))}${errorBox()}<button class="ghost">${esc(text('saveDate'))}</button></form></details></article>`).join('') || `<p class="daily-empty">${esc(text('noDocuments'))}</p>`}<form id="document-form" class="daily-form"><div class="daily-fields">${registered?'':ownerControls(dogs[dogId]?.owner || '',true)}${label('documentLabel',input('label','text','','required pattern="[\\s\\S]{0,120}"'))}${label('renewal',input('renewal','date','','min="2000-01-01" max="2199-12-31"'))}${label('file',input('file','file','','required accept="application/pdf,image/jpeg,image/png"'))}</div><p class="daily-help">PDF, JPEG, PNG · 5 MiB ${esc(text('maximum'))}</p>${errorBox()}<button class="primary" ${loadError?'disabled':''}>${esc(text('saveDocument'))}</button></form></section>`;
  }
  function quote(form, preview=false) {
    const data=new FormData(form), old=editing && daily.bookings.find(b=>b.id===editing), service=form.elements.service.value;
    const same=old && old.service===service;
    if(carer())return {id:old?.id || id(),dogId:form.elements.dogId.value,service,start:data.get('start'),end:data.get('end'),unitMinor:old?old.unitMinor:preview?daily.rates[service]:null,currency:old?.currency || daily.rates.currency};
    return {id:old?.id || id(),dogId:data.get('dogId'),service,start:data.get('start'),end:data.get('end'),unitMinor:same&&old.unitMinor!==null?old.unitMinor:M.parseMinor(data.get('unitMinor')),currency:same?old.currency:daily.rates.currency};
  }
  function updateQuote(form) {
    const panel=form.querySelector('#booking-quote'), old=editing && daily.bookings.find(x=>x.id===editing);
    try {
      const b=quote(form,true);
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
    function selectDog(){const choice=form.elements.dogId.value, registered=daily.dogs.find(d=>d.id===choice);form.querySelector('#new-dog-field').hidden=choice!==CREATE_DOG;form.elements.dogName.required=choice===CREATE_DOG;form.elements.dogName.disabled=choice!==CREATE_DOG;form.elements.clientId.disabled=!!registered?.clientId;bindOwnerChoice(form,registered?.clientId || ':new',registered?'':dogs[choice]?.owner || '');}
    form.elements.dogId.onchange=selectDog;selectDog();
    const old=editing && daily.bookings.find(b=>b.id===editing);
    if(old && carer()){form.elements.dogId.disabled=true;form.elements.service.disabled=true;}
    function selectService(){const same=old && old.service===form.elements.service.value, amount=old&&(same||carer())?old.unitMinor:daily.rates[form.elements.service.value];form.elements.unitMinor.value=amount===null?'':(amount/100).toFixed(2);form.elements.unitMinor.readOnly=carer()||!!(same&&old.unitMinor!==null);}
    form.elements.service.onchange=selectService;selectService();
    form.addEventListener('input',()=>updateQuote(form));form.addEventListener('change',()=>updateQuote(form));updateQuote(form);
    form.querySelector('#cancel-booking').onclick=()=>{editor.innerHTML='';editing=null;document.querySelector('.daily-toolbar').hidden=false;document.querySelector('#new-booking').focus();};
    form.onsubmit=async e=>{
      e.preventDefault();const button=form.querySelector('[type="submit"]');
      try {
        const b=quote(form), next=structuredClone(daily), newDog=form.elements.dogId.value===CREATE_DOG;
        const dog=ensureDog(next,newDog?null:b.dogId,newDog?form.elements.dogName.value:dogs[b.dogId].name,form.elements.client.value,true,form.elements.clientId.value);
        b.dogId=dog.id;M.units(b);
        const at=next.bookings.findIndex(x=>x.id===b.id);if(at<0)next.bookings.push(b);else next.bookings[at]=b;
        if(!await save(next,button)){setError(form);return;}
        month=b.start.slice(0,7);editing=null;navigate('schedule');showToast(text('saved'));
      }catch{setError(form,'invalidBooking');}
    };
    form.querySelector('h2').focus();form.scrollIntoView({block:'start'});
  }
  async function fileData(file) {
    if(!file || file.size===0 || file.size>5*1024*1024 || !['application/pdf','image/png','image/jpeg'].includes(file.type) || [...file.name].length>180)throw Error('file');
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
    bindDogRegistration();bindWalks();
    document.querySelector('#new-booking')?.addEventListener('click',()=>editBooking(null));
    document.querySelectorAll('[data-edit-booking]').forEach(b=>b.onclick=()=>editBooking(b.dataset.editBooking));
    document.querySelectorAll('[data-cancel-booking]').forEach(button=>button.onclick=async()=>{
      if(savePending || !w.PortalUI.owner() || !w.confirm(text('cancelBookingConfirm')))return;
      const bookingId=button.dataset.cancelBooking;
      let ok;
      if(w.DogCareAPI){
        ok=await persistChange(()=>w.DogCareAPI.savePortal('cancel-booking',{id:bookingId}),button);
        if(ok)load();
      }else{
        const next=structuredClone(daily);next.bookings.find(b=>b.id===bookingId).status='cancelled';ok=await save(next,button);
      }
      if(!ok){showToast(text('saveError'));return;}
      editing=null;navigate('schedule');showToast(text('cancelled'));
    });
    document.querySelectorAll('[data-document-dog]').forEach(b=>b.onclick=()=>{state.dog=b.dataset.documentDog;navigate('dogs');document.querySelector('#dog-documents')?.scrollIntoView({block:'start'});});
    document.querySelectorAll('[data-month-step]').forEach(b=>b.onclick=()=>{const [y,m]=month.split('-').map(Number), d=new Date(Date.UTC(y,m-1+Number(b.dataset.monthStep),1));const value=d.toISOString().slice(0,7);if(value>='2000-01'&&value<='2199-12'){month=value;navigate(state.page);document.querySelector('#daily-month')?.focus();}});
    document.querySelector('#daily-month')?.addEventListener('change',e=>{if(/^20\d\d-\d\d$|^21\d\d-\d\d$/.test(e.target.value)){month=e.target.value;navigate(state.page);}});
    const rates=document.querySelector('#rates-form');if(rates){
      const clearSaved=()=>{rates.querySelector('#rates-saved').textContent='';};
      rates.addEventListener('input',clearSaved);rates.addEventListener('change',clearSaved);
      rates.onsubmit=async e=>{e.preventDefault();clearSaved();try{const next=structuredClone(daily);next.rates={currency:rates.elements.currency.value,...Object.fromEntries(['walk','day','night'].map(s=>[s,M.parseMinor(rates.elements[s].value)]))};if(!await save(next,rates.querySelector('button'))){setError(rates);return;}rates.querySelector('.daily-error').hidden=true;rates.querySelector('#rates-saved').textContent=text('saved');}catch{setError(rates,'invalidRate');}};
    }
    document.querySelectorAll('[data-open-document]').forEach(b=>b.onclick=()=>openDocument(daily.documents.find(d=>d.id===b.dataset.openDocument),b));
    document.querySelectorAll('[data-renewal]').forEach(form=>form.onsubmit=async e=>{e.preventDefault();const next=structuredClone(daily);next.documents.find(d=>d.id===form.dataset.renewal).renewal=form.elements.renewal.value;if(!await save(next,form.querySelector('button'))){setError(form);return;}navigate('dogs');document.querySelector('#dog-documents').scrollIntoView({block:'start'});});
    const form=document.querySelector('#document-form'), dogId=state.dog;
    if(form?.elements.clientId)bindOwnerChoice(form,'',dogs[dogId]?.owner || '');
    if(form)form.onsubmit=async e=>{
      e.preventDefault();
      if(savePending || loadError)return;
      const button=form.querySelector('button'), file=form.elements.file.files[0], profile={...dogs[dogId]};
      const label=form.elements.label.value, renewal=form.elements.renewal.value, clientId=form.elements.clientId?.value, clientName=form.elements.client?.value;
      const ok=await persistChange(async()=>{
        let data;
        try{data=await fileData(file);}catch{setError(form,'invalidFile');return false;}
        const next=structuredClone(daily);
        try{ensureDog(next,dogId,profile.name,clientName,false,clientId);}catch{setError(form,'clientRequired');return false;}
        const doc={dogId,label,renewal,name:file.name,type:file.type,data};
        let saved;
        if(w.DogCareAPI){
          if(!daily.dogs.some(d=>d.id===dogId) && !await commitDaily(next)){setError(form);return false;}
          saved=await w.DogCareAPI.saveDocument(doc);
          if(saved){daily=structuredClone(w.DogCareAPI.getDaily());syncDogs();}
        }else{next.documents.push({...doc,id:id()});saved=await commitDaily(next);}
        if(!saved)setError(form);
        return saved;
      },button);
      if(!ok)return;state.dog=dogId;navigate('dogs');document.querySelector('#dog-documents').scrollIntoView({block:'start'});showToast(text('saved'));
    };
  }
  w.DailyUI={text,load,snapshot:()=>loadError?null:structuredClone(daily),alerts:()=>unavailable()+followups(),home,schedule,business,walkMonth,tariff,documents,dogControls,rememberDogDraft,bind};
})(window);

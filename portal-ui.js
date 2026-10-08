/* Client screens use only the server's client projection; staff actions are explicit. */
(function (w) {
  const text = key => (w.PortalCopy[state.language] || w.PortalCopy.en)[key] || key;
  const esc = value => escapeHtml(value ?? '');
  const literal = value => `<span translate="no">${esc(value)}</span>`;
  const data = () => w.DogCareAPI.getPortal();
  const daily = () => w.DogCareAPI.getDaily();
  const client = () => w.DogCareAPI?.getUser()?.role === 'client';
  const professional = () => w.DogCareAPI?.getUser()?.role === 'professional';
  const staff = () => !w.DogCareAPI || ['owner','trusted-carer'].includes(w.DogCareAPI.getUser()?.role);
  const owner = () => !w.DogCareAPI || w.DogCareAPI.getUser()?.role === 'owner';
  const error = () => '<p class="portal-error" role="alert" hidden></p>';
  const dogNames = d => new Map(d.dogs.map(dog=>[dog.id,dog.name]));
  const dogName = (id,names) => names.get(id) || '';
  const date = value => new Intl.DateTimeFormat(formatLocale(Intl.DateTimeFormat),{dateStyle:'medium',timeZone:'UTC'}).format(new Date(value+'T12:00:00Z'));
  const range = item => date(item.start)+(item.end!==item.start?' – '+date(item.end):'');
  function field(key, html) { return `<label>${esc(text(key))}${html}</label>`; }
  function dogChoice(d=daily()) {return `<select name="dogId" required>${d.dogs.filter(d=>d.clientId).map(d=>`<option value="${esc(d.id)}">${esc(d.name)}</option>`).join('')}</select>`;}
  function rows(items, portal, names, status=false) {
    return items.map(item=>`<article class="portal-row"><div><strong>${esc(dogName(item.dogId,names))} · ${esc(text(item.service))}</strong><p>${esc(range(item))}</p>${item.note?`<p>${esc(item.note)}</p>`:''}${QuoteUI.summary(portal.quotes?.[item.id])}</div><span class="portal-tag">${esc(text(item.status==='cancelled'?'cancelled':status?item.status:'booked'))}</span></article>`).join('');
  }
  function reservationForm(d) {
    let service='day';try{const v=sessionStorage.getItem('dogcare-request-service');if(['day','night','walk'].includes(v))service=v;}catch{}
    return `<form id="client-request-form" class="portal-form"><div class="portal-fields">${field('dog',dogChoice(d))}${field('service',`<select name="service">${['day','night','walk'].map(key=>`<option value="${key}" ${service===key?'selected':''}>${esc(text(key))}</option>`).join('')}</select>`)}${field('start','<input name="start" type="date" required>')}${field('end','<input name="end" type="date" required>')}</div>${field('note','<textarea name="note" maxlength="2000" rows="2"></textarea>')}<p id="request-details"></p><div id="request-estimate" aria-live="polite"></div>${error()}<button class="primary">${esc(text('send'))}</button></form>`;
  }
  function render(page) {
    const d=daily(), p=data(), names=dogNames(d), bookedIds=new Set(d.bookings.map(b=>b.id));setHeader('', text('workspace'),true);
    if(!d.dogs.length && (page!=='reservations'||!p.requests.length))return `<section class="portal-card"><p>${esc(text('noDogs'))}</p></section>`;
    if(page==='reservations')return `${d.dogs.length?`<section class="portal-card"><h2>${esc(text('request'))}</h2>${reservationForm(d)}</section>`:''}<section class="portal-card"><h2>${esc(text('reservations'))}</h2>${rows(d.bookings,p,names) || `<p>${esc(text('noBookings'))}</p>`}${rows(p.requests.filter(r=>r.status!=='accepted'&&(r.status!=='cancelled'||!bookedIds.has(r.id))),p,names,true)}</section>`;
    if(page==='news')return `<section class="portal-card"><h2>${esc(text('news'))}</h2>${p.updates.map(u=>`<article class="portal-row"><div><strong>${esc(dogName(u.dogId,names))}</strong><p class="portal-message">${esc(u.text)}</p></div></article>`).join('') || `<p>${esc(text('noUpdates'))}</p>`}</section>`;
    if(page==='documents')return `<section class="portal-card"><h2>${esc(text('documents'))}</h2>${p.documents.map(d=>`<a class="portal-row" href="/api/client-documents/${encodeURIComponent(d.id)}"><span><strong>${esc(d.label)}</strong><small>${esc(dogName(d.dogId,names))}</small></span><span aria-hidden="true">↗</span></a>`).join('') || `<p>${esc(text('noDocuments'))}</p>`}</section>`;
    const next=d.bookings.filter(b=>DailyModel.activeBooking(b)&&b.end>=localDay()).sort((a,b)=>a.start.localeCompare(b.start))[0];
    return `<div class="portal-grid"><section class="portal-card"><h2>${d.dogs.map(d=>esc(d.name)).join(' · ')}</h2>${next?`<p class="portal-kicker">${esc(text('next'))}</p>${rows([next],p,names)}`:`<p>${esc(text('noBookings'))}</p>`}<button class="primary" data-go="reservations">${esc(text('request'))} ↗</button></section><section class="portal-card"><h2>${esc(text('news'))}</h2>${p.updates[0]?`<p class="portal-message">${esc(p.updates[0].text)}</p><button class="link-button" data-go="news">${esc(text('open'))} ↗</button>`:`<p>${esc(text('noUpdates'))}</p>`}</section></div><section class="portal-card portal-document-strip"><h2>${esc(text('documents'))}</h2><button class="link-button" data-go="documents">${esc(text('open'))} ↗</button></section>`;
  }
  function professionalView() {
    const d=daily(), records=data().sharedRecords || [];
    setHeader('',text('sharedCare'),true);
    return `<section class="portal-card"><p>${esc(text('professionalReadOnly'))}</p>${d.dogs.length?d.dogs.map(dog=>`<section class="professional-dog"><h2>${literal(dog.name)}</h2>${records.filter(r=>r.dogId===dog.id).map(r=>`<article class="portal-row"><div><h3>${r.label?literal(r.label):esc(text('notes'))}</h3>${r.kind==='note'?`<small>${literal(r.date)} · ${esc(text('sharedVersion'))}</small><p class="portal-message">${literal(r.text)}</p>`:r.kind==='media'?`${r.mime.startsWith('image/')?`<img class="professional-media" src="${esc(r.href)}" alt="${esc(r.label)}">`:`<video class="professional-media" src="${esc(r.href)}" controls preload="metadata"></video>`}<a href="${esc(r.href)}" download>${esc(text('download'))}</a>`:`<a href="${esc(r.href)}">${esc(text('open'))} ↗</a>`}</div></article>`).join('') || `<p>${esc(text('noSharedCare'))}</p>`}</section>`).join(''):`<p>${esc(text('noDogs'))}</p>`}</section>`;
  }
  function professionalAccess(loaded=false) {
    if(!loaded)return `<div id="professional-access"><p role="status">${esc(text('loadingRecords'))}</p></div>`;
    const p=data(), catalog=p.shareCatalog || [], names=dogNames(daily());
    return `<section class="portal-card"><h2>${esc(text('professionalAccess'))}</h2><p>${esc(text('professionalScope'))}</p><form id="professional-form" class="portal-form">${field('email','<input name="email" type="email" maxlength="255" autocomplete="off" required>')}<div class="professional-selection">${daily().dogs.map(dog=>`<fieldset><legend><label><input type="checkbox" name="dogIds" value="${esc(dog.id)}"> ${literal(dog.name)}</label></legend>${catalog.filter(r=>r.dogId===dog.id).map(r=>`<label class="professional-record"><input type="checkbox" name="recordKeys" value="${esc(r.key)}" data-share-dog="${esc(dog.id)}" disabled><span>${r.label?literal(r.label):esc(text('notes'))}${r.kind==='note'?`<small>${literal(r.date)} · ${literal(r.text)}</small>`:`<small>${esc(r.kind==='media'?text('sharedImages'):text('documents'))}</small>`}</span></label>`).join('') || `<p>${esc(text('noSharedCare'))}</p>`}</fieldset>`).join('')}</div>${error()}<button class="primary" ${daily().dogs.length?'':'disabled'}>${esc(text('saveProfessional'))}</button></form><div class="professional-members">${(p.professionals || []).map(m=>`<article class="portal-row"><div><strong>${literal(m.email)}</strong><p>${m.dogIds.map(id=>literal(names.get(id)||id)).join(' · ')} · ${m.recordKeys.length} ${esc(text('sharedItems'))}</p><details><summary>${esc(text('sharedVersion'))}</summary>${(m.sharedRecords||[]).map(r=>`<p class="portal-message"><strong>${literal(r.label)}</strong>${r.kind==='note'?`<br>${literal(r.text)}`:`<br><a href="${esc(r.href)}">${esc(text('open'))}</a>`}</p>`).join('')}</details></div><div class="portal-row-actions"><button class="ghost" data-edit-professional="${m.id}">${esc(text('reviewAccess'))}</button><button class="ghost" data-revoke="${m.id}">${esc(text('revoke'))}</button></div></article>`).join('')}</div></section>`;
  }
  function ownerHome() {
    const d=DailyUI.snapshot() || DailyModel.empty(),next=d.bookings.filter(b=>DailyModel.activeBooking(b)&&b.end>=localDay()).sort((a,b)=>a.start.localeCompare(b.start))[0];
    setHeader('',text('dayHeading'),true);
    const p=w.DogCareAPI?data():null,names=dogNames(d);
    const requestRows=p?p.requests.filter(r=>r.status==='requested'):[];
    const latest=state.observations[state.dog]?.[0];
    const recent=latest?`<div class="activity-list"><button class="activity-row" data-evidence-id="${esc(latest.id)}" data-evidence-dog="${esc(state.dog)}"><span class="activity-time">${esc(latest.time)}<small>${esc(observationDateLabel(latest))}</small></span><span class="activity-copy"><strong>${esc(t(latest.title))}</strong><span class="activity-preview">${esc(t(latest.text))}</span></span><span aria-hidden="true">↗</span></button></div>`:'';
    const dogCards=Object.entries(dogs).map(([id,d])=>`<button class="dog-card" data-dog="${esc(id)}">${w.MediaUI?.avatar(id,d.name) || ''}<span class="dog-name" translate="no">${esc(d.name)}</span><span aria-hidden="true">↗</span></button>`).join('');
    return `${DailyUI.alerts()}<div class="portal-grid"><section class="portal-card"><p class="portal-kicker">${esc(text('next'))}</p><h2>${next?esc(dogName(next.dogId,names)):esc(text('noBookings'))}</h2>${next?`<p>${esc(text(next.service))} · ${esc(range(next))}</p>`:''}<button class="primary" data-go="schedule">${esc(text('plan'))} ↗</button>${owner()?`<button class="link-button" data-go="business" data-finance-rates>${esc(DailyUI.text('rates'))} ↗</button>`:''}</section><section class="portal-card portal-shortcuts"><p class="portal-kicker">${esc(text('quick'))}</p>${[['assistant','Muse assistant'],['story','Daily story'],['handoff','Handoff']].map(([page,label])=>`<button data-go="${page}"><span>${esc(t(label))}</span><span aria-hidden="true">↗</span></button>`).join('')}</section></div>${requestRows.length?`<section class="portal-card"><h2>${esc(text('pending'))}</h2>${requestRows.map(r=>`<article class="portal-row"><div><strong>${esc(dogName(r.dogId,names))} · ${esc(text(r.service))}</strong><p>${esc(range(r))}</p><p>${esc(r.note)}</p>${QuoteUI.summary(p.quotes?.[r.id])}${owner()?QuoteUI.editor(r.id,p):''}</div><div class="portal-row-actions"><button class="primary" data-request-id="${esc(r.id)}" data-decision="accepted">${esc(text('accept'))}</button><button class="ghost" data-request-id="${esc(r.id)}" data-decision="declined">${esc(text('decline'))}</button></div></article>`).join('')}</section>`:''}<section class="portal-card"><div class="portal-document-strip"><h2>${esc(t('The dogs'))}</h2><button class="link-button" data-go="dogs">${esc(text('open'))} ↗</button></div><div class="workspace-dog-list">${dogCards}</div></section><section class="portal-card"><div class="portal-document-strip"><h2>${esc(text('notes'))}</h2><button class="link-button" data-go="capture">${esc(t('Capture update'))} +</button></div>${recent}</section>`;
  }
  function sharedTools() {
    if(!w.DogCareAPI || !staff() || !DailyUI.snapshot())return '';
    return `<details class="portal-card portal-sharing"><summary>${esc(text('shared'))}</summary><p>${esc(text('privateBoundary'))}</p><form id="client-update-form" class="portal-form"><h2>${esc(text('update'))}</h2>${field('dog',dogChoice())}${field('message','<textarea name="text" maxlength="4000" rows="3" required></textarea>')}${error()}<button class="primary">${esc(text('publish'))}</button></form><form id="client-document-form" class="portal-form"><h2>${esc(text('clientFiles'))}</h2>${field('dog',dogChoice())}${field('label','<input name="label" maxlength="120" required>')}${field('file','<input name="file" type="file" accept="application/pdf,image/jpeg,image/png" required>')}<p>PDF, JPEG, PNG · 5 MiB</p>${error()}<button class="primary">${esc(text('upload'))}</button></form></details>`;
  }
  function access() {
    if(!w.DogCareAPI || !owner() || !DailyUI.snapshot())return '';
    return `<section class="portal-card"><h2>${esc(text('members'))}</h2><p>${esc(text('accessNotice'))} ${esc(text('accessNext'))}</p>${daily().clients.length?'':`<p>${esc(text('noFamily'))}</p><button class="ghost" data-go="dogs">${esc(text('dogs'))}</button>`}<form id="member-form" class="portal-form"><div class="portal-fields">${field('email','<input name="email" type="email" maxlength="255" autocomplete="off" required>')}${field('role',`<select name="role"><option value="client">${esc(text('client'))}</option><option value="trusted-carer">${esc(text('carer'))}</option></select>`)}${field('family',`<select name="clientId" required>${daily().clients.map(c=>`<option value="${esc(c.id)}">${esc(c.name)}</option>`).join('')}</select>`)}</div>${error()}<button class="primary">${esc(text('grant'))}</button></form><div id="member-list">${data().members.map(m=>`<article class="portal-row"><div><strong>${esc(m.email)}</strong><p>${esc(text(m.role==='client'?'client':'carer'))}</p></div><button class="ghost" data-revoke="${m.id}">${esc(text('revoke'))}</button></article>`).join('')}</div></section>`;
  }
  function settings() {
    return `<section class="portal-card"><h2>${esc(text('account'))}</h2><p>${esc(w.DogCareAPI.getUser()?.email || '')}</p><div class="daily-actions"><button class="ghost" data-go="invite">${esc(text('members'))}</button><button class="ghost" data-go="business">${esc(DailyUI.text('rates'))}</button></div></section>`;
  }
  function bind() {
    async function save(action,payload,form) {
      const button=form?.querySelector('button');
      const ok=await persistChange(()=>w.DogCareAPI.savePortal(action,payload),button);
      if(ok){if(staff())DailyUI.load();navigate(state.page);showToast(text('saved'));}
      else if(form){const e=form.querySelector('.portal-error');e.textContent=text('saveError');e.hidden=false;}
      return ok;
    }
    const request=document.querySelector('#client-request-form');
    if(request)QuoteUI.bindEstimate(request);
    if(request)request.onsubmit=e=>{e.preventDefault();const payload=Object.fromEntries(new FormData(request));try{DailyModel.units(payload);}catch{const error=request.querySelector('.portal-error');error.textContent=text('datesError');error.hidden=false;return;}save('requests',payload,request);};
    QuoteUI.bind(save);
    const update=document.querySelector('#client-update-form');if(update)update.onsubmit=e=>{e.preventDefault();save('updates',Object.fromEntries(new FormData(update)),update);};
    const fileForm=document.querySelector('#client-document-form');
    if(fileForm)fileForm.onsubmit=async e=>{e.preventDefault();const form=new FormData(fileForm),file=form.get('file');try{if(file.size>5*1024*1024)throw Error('size');const bytes=new Uint8Array(await file.arrayBuffer());let binary='';for(let i=0;i<bytes.length;i+=8192)binary+=String.fromCharCode(...bytes.subarray(i,i+8192));await save('documents',{dogId:form.get('dogId'),label:form.get('label'),renewal:'',name:file.name,type:file.type,data:btoa(binary)},fileForm);}catch{const error=fileForm.querySelector('.portal-error');error.textContent=text('saveError');error.hidden=false;}};
    const member=document.querySelector('#member-form');
    if(member){const role=member.elements.role,group=member.elements.clientId;role.onchange=()=>{group.disabled=role.value!=='client';group.required=!group.disabled;};member.onsubmit=e=>{e.preventDefault();save('members',{email:member.elements.email.value,role:role.value,clientId:group.disabled?null:group.value},member);};}
    const professionalAccessRoot=document.querySelector('#professional-access');
    if(professionalAccessRoot){
      async function loadSelection(){
        professionalAccessRoot.innerHTML=`<p role="status">${esc(text('loadingRecords'))}</p>`;
        const ok=await w.DogCareAPI.reloadPortal();
        if(!professionalAccessRoot.isConnected)return;
        if(!ok){
          professionalAccessRoot.innerHTML=`<p role="alert">${esc(text('loadRecordsError'))}</p><button class="ghost">${esc(text('retry'))}</button>`;
          professionalAccessRoot.querySelector('button').onclick=loadSelection;
          return;
        }
        professionalAccessRoot.innerHTML=professionalAccess(true);
        localizeContent();
        bindSelection(professionalAccessRoot);
      }
      loadSelection();
    }
    function bindSelection(root){
      const professionalForm=root.querySelector('#professional-form');
      if(professionalForm){
        const dogs=[...professionalForm.querySelectorAll('[name=dogIds]')], records=[...professionalForm.querySelectorAll('[name=recordKeys]')];
        function sync(){const selected=new Set(dogs.filter(x=>x.checked).map(x=>x.value));records.forEach(x=>{x.disabled=!selected.has(x.dataset.shareDog);if(x.disabled)x.checked=false;});}
        dogs.forEach(x=>x.onchange=sync);
        professionalForm.onsubmit=e=>{e.preventDefault();const d=new FormData(professionalForm);save('professionals',{email:d.get('email'),dogIds:d.getAll('dogIds'),recordKeys:d.getAll('recordKeys')},professionalForm);};
        root.querySelectorAll('[data-edit-professional]').forEach(b=>b.onclick=()=>{const m=data().professionals.find(m=>m.id===Number(b.dataset.editProfessional));professionalForm.elements.email.value=m.email;dogs.forEach(x=>x.checked=m.dogIds.includes(x.value));sync();records.forEach(x=>x.checked=!x.disabled&&m.recordKeys.includes(x.value));professionalForm.scrollIntoView({block:'start'});professionalForm.elements.email.focus({preventScroll:true});});
      }
      root.querySelectorAll('[data-revoke]').forEach(b=>b.onclick=()=>save('revoke',{userId:Number(b.dataset.revoke)}));
    }
    document.querySelectorAll('[data-revoke]').forEach(b=>b.onclick=()=>save('revoke',{userId:Number(b.dataset.revoke)}));
    document.querySelectorAll('[data-request-id]').forEach(b=>b.onclick=()=>save('decide',{id:b.dataset.requestId,status:b.dataset.decision}));
  }
  w.PortalUI={text,client,professional,staff,owner,render,professionalView,professionalAccess,ownerHome,sharedTools,access,settings,bind};
})(window);

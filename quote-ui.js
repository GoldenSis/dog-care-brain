/* Quoted client prices, never accounting originals or payment actions. */
(function(w){
  const text=k=>PortalUI.text(k), esc=s=>escapeHtml(s??'');
  const money=(minor,currency)=>minor===null?text('totalUnknown'):new Intl.NumberFormat(formatLocale(Intl.NumberFormat),{style:'currency',currency,minimumFractionDigits:2,maximumFractionDigits:2}).format(minor/100);
  const data=()=>w.DogCareAPI?.getPortal();
  const field=(label,html)=>`<label>${esc(text(label))}${html}</label>`;
  const input=(name,value,attrs='')=>`<input name="${name}" value="${esc(value)}" ${attrs}>`;
  function summary(q){
    if(!q)return '';
    return `<div class="quote-summary"><p>${q.units} × ${q.unitMinor===null?esc(text('priceUnknown')):esc(money(q.unitMinor,q.currency))}</p>${q.extras.map(e=>`<p>${esc(e.label)} · ${e.quantity} × ${esc(money(e.unitMinor,e.currency))} <strong>${esc(money(e.totalMinor,e.currency))}</strong></p>`).join('')}<p class="quoted-total"><strong>${esc(text('quote'))} · ${esc(money(q.totalMinor,q.currency))}</strong></p></div>`;
  }
  function editor(id,portal=data()){
    const q=portal?.quotes?.[id];if(!q || !PortalUI.owner())return '';
    return `<details class="quote-editor" data-quote="${esc(id)}"><summary>${esc(text('extras'))}</summary>${q.unitMinor===null?`<form class="portal-form base-price-form"><h3>${esc(text('confirmPrice'))}</h3><div class="portal-fields">${field('unitPrice',input('unitMinor','','required inputmode="decimal" maxlength="12"'))}${field('currency',input('currency',q.currency,'required pattern="[A-Z]{3}" maxlength="3"'))}</div><p class="portal-error" role="alert" hidden></p><button class="primary">${esc(text('save'))}</button></form>`:''}${q.extras.map(e=>`<div class="quote-option"><span>${esc(e.label)} · ${e.quantity} × ${esc(money(e.unitMinor,e.currency))}</span><div><button type="button" class="link-button" data-edit-extra="${esc(e.id)}">${esc(text('edit'))}</button><button type="button" class="link-button" data-remove-extra="${esc(e.id)}">${esc(text('remove'))}</button></div></div>`).join('')}<form class="portal-form extra-form"><h3>${esc(text('extra'))}</h3>${portal.extras?.length?field('savedOptions',`<select name="template"><option value="">${esc(text('customOption'))}</option>${portal.extras.filter(e=>e.currency===q.currency).map(e=>`<option value="${esc(e.id)}">${esc(e.label)} · ${esc(money(e.unitMinor,e.currency))}</option>`).join('')}</select>`):''}<input name="id" type="hidden" value="">${field('extraLabel',input('label','','required maxlength="160"'))}<div class="portal-fields">${field('unitPrice',input('unitMinor','','required inputmode="decimal" maxlength="12"'))}${field('currency',input('currency',q.currency,`required pattern="[A-Z]{3}" maxlength="3" ${q.unitMinor!==null || q.extras.length?'readonly':''}`))}${field('quantity',input('quantity',1,'required type="number" min="1" max="10000" step="1"'))}</div><output class="extra-total" aria-live="polite"></output><label class="quote-reuse"><input type="checkbox" name="reusable">${esc(text('reuse'))}</label><p class="portal-error" role="alert" hidden></p><button class="primary">${esc(text('save'))}</button></form><p class="portal-error quote-action-error" role="alert" hidden></p></details>`;
  }
  function bookings(){
    if(!w.DogCareAPI || !PortalUI.owner() || !DailyUI.snapshot())return '';
    const d=w.DogCareAPI.getDaily();if(!d.bookings.length)return '';
    const portal=data(),names=new Map(d.dogs.map(d=>[d.id,d.name]));
    return `<section class="portal-card"><h2>${esc(text('extras'))}</h2>${d.bookings.map(b=>`<article class="quote-booking"><h3>${esc(names.get(b.dogId))} · ${esc(text(b.service))} · ${esc(b.start)}${DailyModel.activeBooking(b)?'':` · ${esc(text('cancelled'))}`}</h3>${summary(portal.quotes?.[b.id])}${DailyModel.activeBooking(b)?editor(b.id,portal):''}</article>`).join('')}</section>`;
  }
  function bind(save){
    const panels=document.querySelectorAll('[data-quote]');if(!panels.length)return;
    const portal=data(),templates=new Map((portal.extras || []).map(e=>[e.id,e]));
    panels.forEach(panel=>{
      const id=panel.dataset.quote,q=portal.quotes[id],form=panel.querySelector('.extra-form');
      function preview(){let amount=null;try{const n=DailyModel.parseMinor(form.elements.unitMinor.value),count=Number(form.elements.quantity.value);if(n!==null&&Number.isInteger(count)&&count>=1&&count<=10000)amount=n*count;}catch{}let display=text('totalUnknown');try{display=money(amount,form.elements.currency.value || q.currency);}catch{}form.querySelector('output').textContent=text('lineTotal')+' · '+display;}
      function fill(e){form.elements.label.value=e.label;form.elements.unitMinor.value=(e.unitMinor/100).toFixed(2);form.elements.quantity.value=e.quantity||1;preview();}
      form.oninput=preview;preview();
      if(form.elements.template)form.elements.template.onchange=()=>{const e=templates.get(form.elements.template.value);if(e){form.elements.id.value='';fill(e);}};
      panel.querySelectorAll('[data-edit-extra]').forEach(b=>b.onclick=()=>{const e=q.extras.find(e=>e.id===b.dataset.editExtra);form.elements.id.value=e.id;fill(e);form.elements.label.focus();});
      panel.querySelectorAll('[data-remove-extra]').forEach(b=>b.onclick=async()=>{if(!await save('extra-remove',{targetId:id,id:b.dataset.removeExtra})){const e=panel.querySelector('.quote-action-error');e.textContent=text('saveError');e.hidden=false;}});
      form.onsubmit=e=>{e.preventDefault();try{const payload={targetId:id,id:form.elements.id.value,label:form.elements.label.value,unitMinor:DailyModel.parseMinor(form.elements.unitMinor.value),currency:form.elements.currency.value,quantity:Number(form.elements.quantity.value),reusable:form.elements.reusable.checked};if(payload.unitMinor===null)throw Error('amount');save('extras',payload,form);}catch{const e=form.querySelector('.portal-error');e.textContent=text('saveError');e.hidden=false;}};
      const base=panel.querySelector('.base-price-form');if(base)base.onsubmit=e=>{e.preventDefault();try{save('quote',{targetId:id,unitMinor:DailyModel.parseMinor(base.elements.unitMinor.value),currency:base.elements.currency.value},base);}catch{const e=base.querySelector('.portal-error');e.textContent=text('saveError');e.hidden=false;}};
    });
  }
  function bindEstimate(form){
    let sequence=0;
    async function update(){
      const current=++sequence,service=form.elements.service.value;
      document.querySelector('#request-details').textContent=text('detail'+service[0].toUpperCase()+service.slice(1));
      const output=document.querySelector('#request-estimate');
      const values=Object.fromEntries(['dogId','service','start','end'].map(k=>[k,form.elements[k].value]));
      try{DailyModel.units(values);}catch{output.textContent=text('totalUnknown');return;}
      const quote=await w.DogCareAPI.estimateRequest(values);
      if(sequence!==current || !output.isConnected)return;
      output.innerHTML=quote?summary(quote):`<p role="status">${esc(text('estimateError'))}</p>`;
    }
    form.addEventListener('change',update);update();
  }
  w.QuoteUI={summary,editor,bookings,bind,bindEstimate};
})(window);

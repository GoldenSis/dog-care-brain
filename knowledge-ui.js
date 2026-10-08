/* Educational browsing and private draft experiences; no automatic publication. */
(function (w) {
  'use strict';
  const M=w.KnowledgeModel, C=w.KnowledgeContent, KEY='dogcare-knowledge-v1';
  let records=M.empty(), baseline=null, loadError=false, stale=false;
  let category='all', query='', topic='', selected=null, draft=null, editing=false, saved=false;
  const copy=key => (w.KnowledgeCopy[state.language] || w.KnowledgeCopy.en)[key];
  const esc=value => String(value ?? '').replace(/[&<>"'\r]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;','\r':'&#13;'}[c]));
  const guideCopy=g => g.copy[state.language] || g.copy.fr;
  const normalize=value => value.normalize('NFD').replace(/[\u0300-\u036f]/g,'').toLocaleLowerCase();
  const language=code => new Intl.DisplayNames([formatLocale(Intl.DisplayNames)],{type:'language'}).of(code);
  const external=(url,label,extra='') => `<a href="${esc(url)}" target="_blank" rel="noopener noreferrer" ${extra}>${esc(label)} ↗</a>`;
  function load() {
    try {
      if(!w.DogCareAPI)baseline=localStorage.getItem(KEY);
      const value=w.DogCareAPI ? w.DogCareAPI.getKnowledge() : JSON.parse(baseline || 'null');
      const candidate=value || M.empty();M.validate(candidate);records=candidate;
    } catch {loadError=true;}
  }
  async function commit(next) {
    if(loadError || stale)return false;
    try {
      M.validate(next);
      if(w.DogCareAPI) {
        if(!await w.DogCareAPI.saveKnowledge(next))return false;
        records=w.DogCareAPI.getKnowledge();return true;
      }
      if(!w.navigator.locks)return false;
      return await w.navigator.locks.request(KEY,()=>{
        if(localStorage.getItem(KEY)!==baseline){stale=true;return false;}
        const serialized=JSON.stringify(next);localStorage.setItem(KEY,serialized);
        baseline=serialized;records=next;return true;
      });
    } catch {return false;}
  }
  function rememberDraft() {
    const form=document.querySelector('#experience-form');
    if(!form)return;
    const data=new FormData(form), body=data.get('body');
    draft={id:draft.id,status:'draft',title:data.get('title'),body:body===draft.body.replace(/\r\n?/g,'\n')?draft.body:body,author:data.get('author'),url:data.get('url'),category:data.get('category')};
  }
  function video(v) {
    return `<article class="knowledge-video"><strong>${esc(v.title)}</strong><p>${esc(v.provider)} · ${esc(language(v.language))} · ${esc(v.duration)}</p>${external(v.url,copy('watch'),'class="knowledge-link" data-video-link')}</article>`;
  }
  function detail() {
    const g=selected.kind==='guide' ? C.guides.find(item=>item.id===selected.id) : null;
    const item=g || records.experiences.find(item=>item.id===selected.id);
    if(!item){selected=null;return view();}
    const text=g?guideCopy(g):item;
    return `<div class="knowledge-view"><button class="ghost" id="knowledge-back">← ${esc(copy('back'))}</button><article class="card knowledge-detail" ${g?'': 'data-private-experience'}><span class="knowledge-badge">${esc(copy(g?'guide':'draft'))}</span><h2 tabindex="-1" ${g?'':'translate="no"'}>${esc(text.title)}</h2>${g?`<p>${esc(text.summary)}</p><h3>${esc(copy('steps'))}</h3><ol>${text.steps.map(step=>`<li>${esc(step)}</li>`).join('')}</ol><h3>${esc(copy('sources'))}</h3><ul class="knowledge-sources">${g.sources.map(id=>{const s=C.sources.find(source=>source.id===id);return `<li>${external(s.url,s.provider+' — '+s.title)} <small>${esc(language(s.language))}</small></li>`;}).join('')}</ul><p class="daily-help">${esc(copy('checked'))} ${new Intl.DateTimeFormat(formatLocale(Intl.DateTimeFormat),{dateStyle:'medium',timeZone:'UTC'}).format(new Date(C.checked+'T12:00:00Z'))}</p>${g.videos.length?`<h3>${esc(copy('videos'))}</h3>${g.videos.map(id=>video(C.videos.find(v=>v.id===id))).join('')}`:''}`:`<p class="daily-help">${esc(copy('draftHelp'))}</p><p class="knowledge-experience-body" translate="no">${esc(item.body)}</p>${item.author?`<p translate="no">${esc(item.author)}</p>`:''}${item.url?external(item.url,copy('sourceProvided'),'class="knowledge-link"'):''}<button class="ghost" data-edit-experience="${esc(item.id)}">${esc(copy('edit'))}</button>`}</article></div>`;
  }
  function form() {
    const label=(key,field)=>`<label class="daily-field">${esc(copy(key))}${field}</label>`;
    return `<form class="card daily-form knowledge-form" id="experience-form"><h2 tabindex="-1">${esc(copy(records.experiences.some(x=>x.id===draft.id)?'edit':'add'))}</h2><p class="daily-help">${esc(copy('draftHelp'))}</p><p class="daily-help">${esc(copy('unsavedHelp'))}</p>${label('experienceTitle',`<input name="title" translate="no" required>`)}${label('category',`<select name="category">${['colleague','traditional'].map(c=>`<option value="${c}" ${c===draft.category?'selected':''}>${esc(copy(c))}</option>`).join('')}</select>`)}${label('body',`<textarea name="body" translate="no" required rows="6"></textarea>`)}${label('author',`<input name="author" translate="no">`)}${label('link',`<input name="url" type="url" maxlength="2000" placeholder="https://…" value="${esc(draft.url)}">`)}<p class="daily-error" role="alert" hidden></p><div class="daily-actions"><button type="submit" class="primary">${esc(copy('save'))}</button><button type="button" class="ghost" id="cancel-experience">${esc(copy('cancel'))}</button></div></form>`;
  }
  function results() {
    if(category==='videos') {
      const videos=C.videos.filter(v=>normalize(v.title+' '+v.provider).includes(normalize(query)));
      return videos.length?videos.map(video).join(''):`<p class="daily-empty">${esc(copy('noResults'))}</p>`;
    }
    const topics={observe:['observation','body-language'],gesture:['cooperative-handling','paws-and-grooming-check','teeth-care'],visit:['vet-conversation-prep']};
    const guides=['all','practices'].includes(category)?C.guides.filter(g=>(!topic || topics[topic].includes(g.topic)) && normalize(Object.values(guideCopy(g)).flat().join(' ')).includes(normalize(query))):[];
    const experiences=['all','traditional','colleague'].includes(category)?records.experiences.filter(e=>(category==='all'||e.category===category) && normalize([e.title,e.body,e.author,copy(e.category)].join(' ')).includes(normalize(query))):[];
    return [...guides.map(g=>{const text=guideCopy(g);return `<article class="card knowledge-card"><span class="knowledge-badge">${esc(copy('guide'))}</span><h2>${esc(text.title)}</h2><p>${esc(text.summary)}</p><button class="ghost" data-guide="${esc(g.id)}" aria-label="${esc(copy('read')+' : '+text.title)}">${esc(copy('read'))}</button></article>`;}),...experiences.map(e=>`<article class="card knowledge-card" data-private-experience><span class="knowledge-badge">${esc(copy('draft'))}</span><h2 translate="no">${esc(e.title)}</h2><p translate="no">${esc(e.body.slice(0,160))}${e.body.length>160?'…':''}</p><button class="ghost" data-guide="${esc(e.id)}" data-private-open aria-label="${esc(e.title)}">${esc(copy('readExperience'))}</button><button class="link-button" data-edit-experience="${esc(e.id)}">${esc(copy('edit'))}</button></article>`)].join('') || `<p class="daily-empty">${esc(copy(['traditional','colleague'].includes(category)&&!query?'empty':'noResults'))}</p>`;
  }
  function view() {
    if(selected && !editing)return detail();
    return `<div class="knowledge-view"><p class="knowledge-intro">${esc(copy('intro'))}</p><p class="daily-storage">${esc(copy(w.DogCareAPI?'accountStorage':'browserStorage'))}</p>${loadError?`<p role="alert" class="daily-error">${esc(copy('loadError'))}</p>`:''}${saved?`<p role="status" tabindex="-1" class="knowledge-saved">${esc(copy('saved'))}</p>`:''}${editing?form():`<div class="knowledge-actions"><button class="primary" id="add-experience" ${loadError?'disabled':''}>＋ ${esc(copy('add'))}</button></div><details class="knowledge-guide-picker" ${topic?'open':''}><summary>${esc(copy('guided'))}</summary><div>${['observe','gesture','visit'].map(key=>`<button class="ghost" data-topic="${key}" aria-pressed="${topic===key}">${esc(copy(key))}</button>`).join('')}</div><p class="daily-help">${esc(copy('learning'))}</p></details><label class="daily-field knowledge-search">${esc(copy('search'))}<input id="knowledge-search" type="search" value="${esc(query)}"></label><div class="knowledge-filters" role="group" aria-label="${esc(copy('category'))}">${['all','practices','traditional','colleague','videos'].map(key=>`<button class="ghost" data-knowledge-filter="${key}" aria-pressed="${category===key}">${esc(copy(key))}</button>`).join('')}</div><div class="knowledge-grid" id="knowledge-results">${results()}</div>`}</div>`;
  }
  function refresh(focus) {
    content.innerHTML=view();localizeContent();bind();window.scrollTo({top:0,behavior:'instant'});
    if(focus){const el=content.querySelector(focus);if(el){el.focus({preventScroll:true});el.scrollIntoView({block:'nearest'});}}
  }
  function edit(id) {
    selected=null;saved=false;editing=true;
    draft=id?structuredClone(records.experiences.find(e=>e.id===id)):{id:crypto.randomUUID(),title:'',body:'',author:'',url:'',category:category==='traditional'?'traditional':'colleague',status:'draft'};
    refresh('#experience-form h2');
  }
  function bindCards() {
    content.querySelectorAll('[data-guide]').forEach(button=>button.onclick=()=>{selected={id:button.dataset.guide,kind:button.hasAttribute('data-private-open')?'experience':'guide'};saved=false;refresh('.knowledge-detail h2');});
    content.querySelectorAll('[data-edit-experience]').forEach(button=>button.onclick=()=>edit(button.dataset.editExperience));
  }
  function bind() {
    bindCards();
    const back=content.querySelector('#knowledge-back');if(back)back.onclick=()=>{selected=null;refresh('#knowledge-search');};
    const add=content.querySelector('#add-experience');if(add)add.onclick=()=>edit();
    const search=content.querySelector('#knowledge-search');if(search)search.oninput=()=>{query=search.value;content.querySelector('#knowledge-results').innerHTML=results();bindCards();};
    content.querySelectorAll('[data-knowledge-filter]').forEach(button=>button.onclick=()=>{category=button.dataset.knowledgeFilter;topic='';saved=false;refresh(`[data-knowledge-filter="${category}"]`);});
    content.querySelectorAll('[data-topic]').forEach(button=>button.onclick=()=>{topic=button.dataset.topic;category='practices';query='';saved=false;refresh(`[data-topic="${topic}"]`);});
    const f=content.querySelector('#experience-form');
    if(f) {
      for(const name of ['title','body','author'])f.elements[name].value=draft[name];
      f.oninput=()=>{rememberDraft();saved=false;f.querySelector('.daily-error').hidden=true;};
      f.onsubmit=async event=>{
        event.preventDefault();rememberDraft();const next=structuredClone(records),item={...draft,url:draft.url.trim()};
        const index=next.experiences.findIndex(e=>e.id===item.id);if(index<0)next.experiences.unshift(item);else next.experiences[index]=item;
        let error='';try {M.validate(next);}catch {error='invalid';}
        if(!error && !await persistChange(()=>commit(next),f.querySelector('[type="submit"]')))error=stale?'stale':!w.DogCareAPI&&!w.navigator.locks?'locking':'saveError';
        if(error){const alert=f.querySelector('.daily-error');alert.hidden=false;alert.textContent=copy(error);alert.scrollIntoView({block:'nearest'});return;}
        editing=false;draft=null;saved=true;category='all';topic='';query='';selected=null;refresh('[role="status"]');
      };
      content.querySelector('#cancel-experience').onclick=()=>{editing=false;draft=null;selected=null;refresh('#add-experience');};
    }
  }
  w.KnowledgeUI={load,view,bind,rememberDraft,text:copy};
}(window));

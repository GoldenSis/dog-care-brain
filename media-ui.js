(function (w) {
  let media={items:[],covers:{},branding:{hero:null,services:{}}};
  let busy=false;
  const text=key=>(w.MediaCopy[state.language] || w.MediaCopy.fr)[key] || key;
  const esc=value=>escapeHtml(value ?? '');
  const photos='image/jpeg,image/png,image/webp';
  const formats=photos+',video/mp4,video/quicktime,video/webm';
  const defaults={day:'terrier',night:'pug',walk:'dalmatian'};
  const canEdit=()=>['owner','client'].includes(w.DogCareAPI?.getUser()?.role);
  function prepare() { if(w.DogCareAPI)media=w.DogCareAPI.getMedia(); }
  function avatar(dogId,name) {
    const item=media.items.find(item=>item.id===media.covers[dogId]);
    return item?`<div class="dog-avatar"><img src="${esc(item.url)}" alt="${esc(name)}" loading="lazy"></div>`:'';
  }
  function controls(target,label,accept= formats,camera=false) {
    return `<label class="media-picker">${esc(text(label))}<input type="file" ${target} accept="${accept}" ${camera?'capture="environment"':'multiple'}></label>`;
  }
  function status() { return '<p class="media-status" role="status"></p><progress class="media-progress" max="100" value="0" hidden></progress><p class="media-error" role="alert" hidden></p>'; }
  function tile(item) {
    const video=item.mime.startsWith('video/'),cover=media.covers[item.dogId]===item.id;
    return `<article class="album-item" data-media-id="${esc(item.id)}"><button class="media-thumb" data-media-open="${esc(item.id)}" aria-label="${esc(text('open')+' '+item.name)}">${video?`<video src="${esc(item.url)}" muted playsinline preload="metadata" aria-hidden="true"></video><span class="media-play" aria-hidden="true">▶</span>`:`<img src="${esc(item.url)}" alt="${esc(item.name)}" loading="lazy">`}</button><strong class="media-name">${esc(item.name)}</strong>${cover?`<span class="media-cover-label">${esc(text('selected'))}</span>`:''}<div class="media-actions">${canEdit() && !video && !cover?`<button class="ghost" data-media-cover="${esc(item.id)}">${esc(text('cover'))}</button>`:''}${canEdit()?`<button class="ghost" data-media-delete="${esc(item.id)}">${esc(text('remove'))}</button>`:''}</div></article>`;
  }
  function album(dogId,name) {
    if(!w.DogCareAPI || !canEdit())return '';
    const items=media.items.filter(item=>item.purpose==='dog' && item.dogId===dogId);
    return `<section class="portal-card private-album" data-album="${esc(dogId)}"><div class="media-heading">${avatar(dogId,name)}<h2>${esc(name)} · ${esc(text('album'))}</h2></div><p>${esc(text('privacy'))}</p>${canEdit()?`<div class="media-actions">${controls(`data-media-upload="${esc(dogId)}"`,'add')}${controls(`data-media-upload="${esc(dogId)}"`,'camera',photos,true)}</div><p class="media-help">${esc(text('limits'))}</p>`:''}${status()}<div class="album-grid">${items.map(tile).join('') || `<p>${esc(text('empty'))}</p>`}</div></section>`;
  }
  function gallery() {
    if(!w.DogCareAPI || !canEdit())return '';
    const registered=new Map(Object.entries(dogs).map(([id,dog])=>[id,{id,name:dog.name}]));
    for(const dog of w.DogCareAPI.getDaily()?.dogs || [])registered.set(dog.id,dog);
    return [...registered.values()].map(dog=>album(dog.id,dog.name)).join('');
  }
  function settings() {
    if(w.DogCareAPI?.getUser()?.role!=='owner')return '';
    const branding=media.branding,hero=media.items.find(item=>item.id===branding.hero?.mediaId),images=media.items.filter(item=>item.purpose==='branding');
    return `<section class="portal-card media-settings"><h2>${esc(text('homepage'))}</h2><p>${esc(text('publicNotice'))}</p><form id="media-branding-form"><div class="media-hero-editor"><div class="media-hero-preview"><img id="media-hero-preview" src="${esc(hero?.url || 'assets/photos/good-company.jpg')}" alt="${esc(text('preview'))}" style="object-fit:${branding.hero?.fit || 'cover'};object-position:50% ${branding.hero?.position ?? 65}%"></div><div class="media-fields"><label class="media-picker">${esc(text('change'))}<input id="media-hero-file" type="file" accept="${photos}"></label><label>${esc(text('preview'))}<select id="media-hero-choice"><option value="">${esc(text('reset'))}</option>${images.map(item=>`<option value="${esc(item.id)}" ${hero?.id===item.id?'selected':''}>${esc(item.name)}</option>`).join('')}</select></label><label>${esc(text('fit'))}<select id="media-fit"><option value="contain" ${branding.hero?.fit==='contain'?'selected':''}>${esc(text('contain'))}</option><option value="cover" ${branding.hero?.fit!=='contain'?'selected':''}>${esc(text('crop'))}</option></select></label><label>${esc(text('position'))}<input id="media-position" type="range" min="0" max="100" value="${branding.hero?.position ?? 65}"></label></div></div><h2>${esc(text('artwork'))}</h2><div class="media-service-choices">${Object.keys(defaults).map(service=>{const art=branding.services?.[service] || {face:defaults[service]};return `<label><span>${esc(PortalUI.text(service))}</span><span data-service-preview="${service}">${art.mediaId?`<img class="service-dog" src="${esc(media.items.find(item=>item.id===art.mediaId)?.url || '')}" alt="">`:WelcomeUI.face(art.face)}</span><select data-service-art="${service}">${Object.values(defaults).map(face=>`<option value="face:${face}" ${art.face===face?'selected':''}>${esc(text(face))}</option>`).join('')}${images.map(item=>`<option value="media:${esc(item.id)}" ${art.mediaId===item.id?'selected':''}>${esc(item.name)}</option>`).join('')}</select></label>`;}).join('')}</div><label class="media-picker">${esc(text('uploadArt'))}<input id="media-art-file" type="file" accept="${photos}" multiple></label><p class="media-help">${esc(text('limits'))}</p>${status()}<div class="media-actions"><button class="primary" id="media-brand-save">${esc(text('publish'))}</button><button class="ghost" id="media-brand-reset" type="button">${esc(text('reset'))}</button></div></form>${images.length?`<details class="media-brand-drafts"><summary>${esc(text('drafts'))}</summary>${images.map(item=>`<div class="media-draft-row"><img src="${esc(item.url)}" alt=""><span>${esc(item.name)}</span><button class="ghost" data-media-delete="${esc(item.id)}">${esc(text('remove'))}</button></div>`).join('')}</details>`:''}</section>`;
  }
  function showError(root,error) { const el=root.querySelector('.media-error');if(el){el.textContent=error.message || String(error);el.hidden=false;} }
  async function action(root,job,refresh=true) {
    if(busy || savePending)return;
    busy=true;
    savePending=true;
    const controls=[...document.querySelectorAll('#app-content button,#app-content input,#app-content select')], disabled=controls.map(el=>el.disabled);
    controls.forEach(el=>el.disabled=true);
    const error=root.querySelector('.media-error');if(error)error.hidden=true;
    try { await job();savePending=false;if(refresh)navigate(state.page);showToast(text(refresh?'saved':'draftSaved')); }
    catch(error) {showError(root,error);}
    finally {busy=false;savePending=false;controls.forEach((el,index)=>el.disabled=disabled[index]);}
  }
  async function validatePreview(file) {
    const image=file.type.startsWith('image/'),element=document.createElement(image?'img':'video'),source=URL.createObjectURL(file);
    try {
      await new Promise((resolve,reject)=>{
        const timer=setTimeout(()=>reject(Error(text(image?'imageError':'videoError'))),15000);
        element[image?'onload':'onloadeddata']=()=>{clearTimeout(timer);resolve();};
        element.onerror=()=>{clearTimeout(timer);reject(Error(text(image?'imageError':'videoError')));};
        if(!image){element.preload='auto';element.muted=true;}
        element.src=source;
      });
    } finally {element.removeAttribute('src');if(!image)element.load();URL.revokeObjectURL(source);}
  }
  async function upload(file,target,root) {
    const image=file.type.startsWith('image/'),allowed=formats.split(',');
    if(!allowed.includes(file.type))throw Error('Format non pris en charge. Choisissez JPEG, PNG, WebP, MP4/MOV H.264 ou WebM VP8/VP9. HEIC et HEVC ne sont pas pris en charge.');
    if(!file.size || file.size>(image?12:80)*1024*1024)throw Error(image?'Photo vide ou supérieure à 12 Mio.':'Vidéo vide ou supérieure à 80 Mio.');
    await validatePreview(file);
    const progress=root.querySelector('.media-progress'),label=root.querySelector('.media-status');
    progress.hidden=false;progress.value=0;label.textContent=text('uploading')+' · '+file.name;
    try {
      const result=await w.DogCareAPI.uploadMedia(file,target,percent=>{progress.value=percent;label.textContent=percent===100?text('checking'):text('uploading')+' · '+file.name+' · '+percent+' %';});
      media=result.media;label.textContent=text(target.purpose==='branding'?'draftSaved':'saved')+' · '+file.name;
      return media.items.find(item=>item.id===result.uploadedId);
    } finally {progress.hidden=true;}
  }
  function open(id) {
    const item=media.items.find(item=>item.id===id);if(!item)return;
    const dialog=document.createElement('dialog');dialog.className='media-lightbox';
    const video=item.mime.startsWith('video/');
    dialog.innerHTML=`<div class="media-lightbox-heading"><strong>${esc(item.name)}</strong><button class="ghost" autofocus>${esc(text('close'))} ×</button></div>${video?`<video controls playsinline preload="metadata" src="${esc(item.url)}"></video>`:`<img src="${esc(item.url)}" alt="${esc(item.name)}">`}<p class="media-error" hidden></p><a class="ghost" href="${esc(item.url)}" download="${esc(item.name)}">${esc(text('download'))} ↗</a>`;
    const close=()=>{dialog.querySelector('video')?.pause();dialog.remove();};
    dialog.querySelector('button').onclick=()=>dialog.close();dialog.onclose=close;
    dialog.querySelector(video?'video':'img').onerror=()=>{const error=dialog.querySelector('.media-error');error.hidden=false;error.textContent=text(video?'videoError':'imageError');};
    document.body.append(dialog);dialog.showModal();
  }
  function bind() {
    if(!w.DogCareAPI)return;
    document.querySelectorAll('.media-thumb video').forEach(video=>{const seek=()=>{if(video.duration>0)video.currentTime=Math.min(.05,video.duration/2);};if(video.readyState>=1)seek();else video.onloadedmetadata=seek;});
    document.querySelectorAll('[data-media-open]').forEach(button=>button.onclick=()=>open(button.dataset.mediaOpen));
    document.querySelectorAll('[data-media-upload]').forEach(input=>input.onchange=()=>{
      const root=input.closest('.private-album'),files=[...input.files];
      if(!files.length)return;
      action(root,async()=>{try{for(const file of files)await upload(file,{dogId:input.dataset.mediaUpload},root);}finally{const grid=root.querySelector('.album-grid');grid.innerHTML=media.items.filter(item=>item.dogId===input.dataset.mediaUpload).map(tile).join('');bind();input.value='';}});
    });
    document.querySelectorAll('[data-media-cover]').forEach(button=>button.onclick=()=>action(button.closest('.private-album'),async()=>{const item=media.items.find(item=>item.id===button.dataset.mediaCover);media=await w.DogCareAPI.saveMedia('cover',{dogId:item.dogId,mediaId:item.id});}));
    document.querySelectorAll('[data-media-delete]').forEach(button=>button.onclick=()=>{if(!w.confirm(text('confirm')))return;action(button.closest('.private-album,.media-settings'),async()=>{media=await w.DogCareAPI.saveMedia('delete',{id:button.dataset.mediaDelete});});});
    bindBranding();
  }
  function bindBranding() {
    const form=document.querySelector('#media-branding-form');if(!form)return;
    const choice=form.querySelector('#media-hero-choice'),fit=form.querySelector('#media-fit'),position=form.querySelector('#media-position'),preview=form.querySelector('#media-hero-preview');
    const redraw=()=>{const hero=media.items.find(item=>item.id===choice.value);preview.src=hero?.url || 'assets/photos/good-company.jpg';preview.style.objectFit=hero?fit.value:'cover';preview.style.objectPosition='50% '+(hero?position.value:65)+'%';};
    choice.onchange=()=>{fit.value='contain';position.value='50';redraw();};fit.onchange=position.oninput=redraw;
    const option=(select,item,value)=>{const el=document.createElement('option');el.value=value;el.textContent=item.name;select.append(el);};
    async function add(files,isHero) {
      await action(form,async()=>{
        for(const file of files){const item=await upload(file,{purpose:'branding'},form);option(choice,item,item.id);form.querySelectorAll('[data-service-art]').forEach(select=>option(select,item,'media:'+item.id));if(isHero){choice.value=item.id;fit.value='contain';position.value='50';redraw();}}
      },false);
    }
    form.querySelector('#media-hero-file').onchange=event=>{const files=[...event.target.files];event.target.value='';if(files.length)add(files,true);};
    form.querySelector('#media-art-file').onchange=event=>{const files=[...event.target.files];event.target.value='';if(files.length)add(files,false);};
    form.querySelectorAll('[data-service-art]').forEach(select=>select.onchange=()=>{const [kind,id]=select.value.split(':');form.querySelector(`[data-service-preview="${select.dataset.serviceArt}"]`).innerHTML=kind==='face'?WelcomeUI.face(id):`<img class="service-dog" src="${esc(media.items.find(item=>item.id===id)?.url || '')}" alt="">`;});
    form.onsubmit=event=>{event.preventDefault();action(form,async()=>{const services={};form.querySelectorAll('[data-service-art]').forEach(select=>{const [kind,id]=select.value.split(':');services[select.dataset.serviceArt]=kind==='face'?{face:id}:{mediaId:id};});media=await w.DogCareAPI.saveMedia('branding',{hero:choice.value?{mediaId:choice.value,fit:fit.value,position:Number(position.value)}:null,services});});};
    form.querySelector('#media-brand-reset').onclick=()=>action(form,async()=>{media=await w.DogCareAPI.saveMedia('branding',{...media.branding,hero:null});});
  }
  w.MediaUI={prepare,avatar,album,gallery,settings,bind};
})(window);

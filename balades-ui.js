/* Balades: record or import a walk track, mark spots on the map, link it to a walk in Planning. */
(function(w){
  'use strict';
  const M=w.BaladesModel, S=w.BaladesStore, STYLE='https://tiles.openfreemap.org/styles/liberty';
  const ICONS={pause:'💧',danger:'⚠️',interdit:'⛔',laisse:'🦮',tolere:'🤝'};
  let view='list', current=null, link=null, pending=null, spot=null, placing=false, confirmDelete=false, editing=false;
  let ready=false, message=null, retry=null, busy=false, draftFound=null, draftSaved=null, draftWarning=false, rec=null, map=null, mapLib=null, mapFailed=false, markers=[];
  let operation=0, drawing=0, mapReady=null, mapBox=null, trackVersion=-1, trackCache=[];
  const text=key=>(w.BaladesCopy[state.language]||w.BaladesCopy.fr)[key]??w.BaladesCopy.fr[key]??key;
  const fill=(key,values)=>text(key).replace(/\{(\w+)\}/g,(_,name)=>values[name]??'');
  const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const localDate=(d=new Date())=>`${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
  const dayText=v=>new Intl.DateTimeFormat(formatLocale(Intl.DateTimeFormat),{dateStyle:'medium',timeZone:'UTC'}).format(new Date(`${v}T12:00:00Z`));
  const km=m=>m<1000?`${Math.round(m)} m`:`${new Intl.NumberFormat(formatLocale(Intl.NumberFormat),{maximumFractionDigits:m<10000?2:1}).format(m/1000)} km`;
  const clock=s=>{if(s===null||s===undefined)return '—';const h=Math.floor(s/3600),m=Math.floor(s%3600/60);return h?`${h} h ${String(m).padStart(2,'0')}`:m?`${m} min`:`${s % 60} s`;};
  const dogName=id=>(typeof dogs!=='undefined'&&dogs[id]?.name)||text('unknownDog');
  const dogList=ids=>ids.length?ids.map(dogName).join(', '):text('noDogs');
  const tracks=()=>{if(trackVersion!==S.version()){trackCache=S.snapshot().tracks;trackVersion=S.version();}return trackCache;};
  const track=id=>tracks().find(t=>t.id===id)||null;
  const linked=(date,dogId)=>tracks().find(t=>t.walkRefs.some(r=>r.date===date&&r.dogId===dogId))||null;
  const uid=()=>crypto.randomUUID();
  const $=sel=>document.querySelector(sel);
  const onPage=()=>state.page==='balades'&&$('#balades-root');

  // ---- map (loaded on first use, only on this page) ----
  async function library(){
    if(mapLib)return mapLib;
    if(!document.querySelector('link[data-balades-map]')){const css=document.createElement('link');css.rel='stylesheet';css.href='assets/vendor/balades/maplibre-gl/maplibre-gl.css';css.setAttribute('data-balades-map','');document.head.append(css);}
    return mapLib=await import(new URL('assets/vendor/balades/maplibre-gl/maplibre-gl.mjs',document.baseURI).href);
  }
  function mapNote(key){const note=$('#balades-map-note');if(note){note.hidden=!key;note.textContent=key?text(key):'';}}
  function ensureMap(){
    const box=$('#balades-map');if(!box||mapFailed)return null;
    if(mapBox===box&&mapReady)return mapReady;
    if(map){map.remove();map=null;}
    mapBox=box;
    return mapReady=(async()=>{try{
      const lib=await library();if(!box.isConnected||mapBox!==box)return null;
      const created=new lib.Map({container:box,style:STYLE,center:[2.13,48.80],zoom:12,attributionControl:{compact:true},cooperativeGestures:false});
      map=created;
      created.on('error',()=>{if(map===created)mapNote('tilesError');});
      created.on('click',e=>{if(placing)openSpot({lat:e.lngLat.lat,lon:e.lngLat.lng});});
      await new Promise(resolve=>{created.once('load',resolve);created.once('remove',resolve);});
      if(map!==created)return null;
      created.addSource('balade',{type:'geojson',data:line([])});
      created.addLayer({id:'balade-casing',type:'line',source:'balade',paint:{'line-color':'#ffffff','line-width':7},layout:{'line-cap':'round','line-join':'round'}});
      created.addLayer({id:'balade-line',type:'line',source:'balade',paint:{'line-color':'#c4580b','line-width':4},layout:{'line-cap':'round','line-join':'round'}});
      return created;
    }catch{if(mapBox===box){mapFailed=true;mapNote('mapUnavailable');}return null;}})();
  }
  const line=points=>({type:'Feature',properties:{},geometry:{type:'LineString',coordinates:points.map(p=>[p[1],p[0]])}});
  async function drawMap(fit=true){
    const draw=++drawing;
    const box=$('#balades-map');if(!box)return;
    const points=view==='record'?rec?.points||[]:pending&&view==='save'?pending.points:current&&track(current)?track(current).points:[];
    const spots=view==='record'||view==='save'?pending?.spots||[]:track(current)?.spots||[];
    const visible=['record','save','track','spot'].includes(view);box.hidden=!visible;$('#balades-root').dataset.view=view;$('#balades-legend')?.toggleAttribute('hidden',!visible);
    if(!visible)return;
    const m=await ensureMap();if(!m||!onPage()||draw!==drawing||m!==map)return;
    m.resize();m.getSource('balade')?.setData(line(points));
    markers.forEach(x=>x.remove());markers=spots.map(s=>{
      const el=document.createElement('button');el.type='button';el.className=`balade-marker balade-${s.type}`;
      el.setAttribute('aria-label',`${text(s.type)}${s.note?' : '+s.note:''}`);el.title=el.getAttribute('aria-label');
      el.innerHTML=`<span aria-hidden="true">${ICONS[s.type]}</span>`;
      el.onclick=e=>{e.stopPropagation();const item=document.getElementById('spot-'+s.id);if(item){item.scrollIntoView({block:'nearest'});item.focus();}};
      return new mapLib.Marker({element:el}).setLngLat([s.lon,s.lat]).addTo(m);
    });
    m.getCanvas().style.cursor=placing?'crosshair':'';
    if(!fit)return;
    const all=[...points.map(p=>[p[1],p[0]]),...spots.map(s=>[s.lon,s.lat])];
    if(all.length===1)m.jumpTo({center:all[0],zoom:16});
    else if(all.length>1){const lons=all.map(p=>p[0]),lats=all.map(p=>p[1]);m.fitBounds([[Math.min(...lons),Math.min(...lats)],[Math.max(...lons),Math.max(...lats)]],{padding:40,maxZoom:17,duration:0});}
  }

  // ---- saving: a change is a function of the latest snapshot, so a conflict can reload and replay it ----
  function abandon(){operation++;if(retry){message=null;retry=null;const el=$('#balades-message');if(el)el.outerHTML=messageHtml();}}
  const target=(next,id)=>{const t=next.tracks.find(x=>x.id===id);if(!t)throw new M.BaladeError('missingTrack');return t;};
  async function commit(change,done,cleanup=null,reload=false){
    if(busy)return false;const started=operation;busy=true;setBusy(true);
    try{
      if(reload){const ok=await S.reload();if(started!==operation)return false;if(!ok)throw new M.BaladeError('loadError');}
      const next=S.snapshot();change(next);
      const result=await S.save(next);
      if(result==='ok'){
        await cleanup?.();
        if(started===operation){message=null;retry=null;await done?.();}else{render(false);refreshPlanning();}
        return true;
      }
      if(started!==operation)return false;
      message={key:result==='conflict'?'conflict':result==='invalid'?'tooLarge':'saveError',error:true};
      retry=result==='conflict'?{change,done,cleanup}:null;render();return false;
    }catch(error){
      if(started===operation){message={key:error instanceof M.BaladeError?error.code:'saveError',error:true};if(message.key!=='loadError')retry=null;render(false);}return false;
    }finally{busy=false;setBusy(false);}
  }
  function setBusy(on){document.querySelectorAll('#balades-panel button,#balades-panel input,#balades-panel textarea').forEach(el=>{if(on){if(!Object.hasOwn(el.dataset,'busy'))el.dataset.busy=el.disabled?'1':'';el.disabled=true;}else if(Object.hasOwn(el.dataset,'busy')){el.disabled=el.dataset.busy==='1';delete el.dataset.busy;}});}
  const replay=()=>retry&&commit(retry.change,retry.done,retry.cleanup,true);

  // ---- recording ----
  function stats(){
    if(!rec)return;
    const set=(id,value)=>{const el=document.getElementById(id);if(el)el.textContent=value;};
    set('rec-distance',km(M.distance(rec.points)));set('rec-time',clock(Math.round((Date.now()-rec.startedAt)/1000)));
    set('rec-points',String(rec.points.length));set('rec-accuracy',rec.accuracy===null?'—':`± ${Math.round(rec.accuracy)} m`);
  }
  const draftHtml=()=>`<p id="balades-draft-warning" class="daily-error" role="alert" ${draftWarning?'':'hidden'}>${draftWarning?esc(text('draftError')):''}</p>`;
  const draftStatus=()=>{const el=$('#balades-draft-warning');if(el)el.outerHTML=draftHtml();};
  async function persist(){
    if(!rec)return;
    const recording=rec,value={id:recording.id,token:uid(),startedAt:recording.startedAt,points:recording.points.slice(),savedAt:Date.now()};draftFound=value;
    return recording.write=(recording.write||Promise.resolve()).then(async()=>{
      const ok=await S.draft(value,recording.saved)===true;if(ok)recording.saved=draftSaved=value;
      if(draftFound!==value)return;draftWarning=!ok;draftStatus();
    });
  }
  async function clearDraft(previous){const result=await S.draft(null,previous);if(result===true||result?.conflict){draftFound=draftSaved=result===true?null:result.draft;draftWarning=false;}else draftWarning=true;draftStatus();}
  async function wake(){
    const recording=rec;if(!recording||recording.stopped||recording.waking||recording.lock&&!recording.lock.released)return;
    recording.waking=true;
    try{
      const lock=await navigator.wakeLock.request('screen');
      if(rec!==recording||recording.stopped||document.hidden){await lock.release();return;}
      recording.lock=lock;recording.lockState='wakeOn';lock.addEventListener?.('release',()=>{if(rec===recording&&recording.lock===lock){recording.lock=null;recording.lockState='wakeOff';status();}});
    }catch{if(rec===recording)recording.lockState='wakeOff';}
    finally{recording.waking=false;if(rec===recording)status();}
  }
  function status(){const el=$('#rec-wake');if(el&&rec)el.textContent=text(rec.lockState||'wakeOff');const g=$('#rec-gps');if(g&&rec)g.textContent=rec.gps?text(rec.gps):'';}
  const visible=()=>{if(rec&&!document.hidden)wake();};
  function start(resume){
    if(rec||(!resume&&draftFound))return;
    if(!navigator.geolocation){message={key:'noGps',error:true};render();return;}
    if(!resume&&tracks().length>=M.LIMITS.tracks){message={key:'tooManyTracks',error:true};render();return;}
    rec={id:resume?.id||uid(),saved:resume?draftSaved:null,startedAt:resume?.startedAt||Date.now(),points:resume?.points.slice()||[],accuracy:null,lock:null,lockState:'wakeOff',gps:'gpsWaiting'};
    message=null;confirmDelete=false;pending={spots:[]};
    rec.watch=navigator.geolocation.watchPosition(fix,gpsError,{enableHighAccuracy:true,maximumAge:0,timeout:30000});
    rec.tick=setInterval(stats,1000);rec.save=setInterval(persist,10000);persist();
    document.addEventListener('visibilitychange',visible);
    view='record';render();wake();
  }
  function fix(position){
    if(!rec)return;
    const c=position.coords,last=rec.points[rec.points.length-1];rec.accuracy=c.accuracy;rec.gps=c.accuracy>M.LIMITS.maxAccuracy?'gpsWeak':'gpsOk';
    if(M.accept({lat:c.latitude,lon:c.longitude,accuracy:c.accuracy},last)){
      if(rec.points.length>=M.LIMITS.points){finish('pointsFull');return;}
      rec.points.push([Math.round(c.latitude*1e6)/1e6,Math.round(c.longitude*1e6)/1e6,Math.floor((position.timestamp||Date.now())/1000)]);
      if(onPage()&&view==='record')drawMap(rec.points.length<3).then(()=>{if(map&&rec?.points.length>=3){const p=rec.points[rec.points.length-1];map.setCenter([p[1],p[0]]);}});
    }
    stats();status();
  }
  function gpsError(error){
    if(!rec)return;
    rec.gps=error.code===1?'gpsDenied':'gpsWaiting';status();
    if(error.code===1){message={key:'gpsDenied',error:true};const el=$('#balades-message');if(el)el.outerHTML=messageHtml();}
  }
  function halt(){
    if(!rec)return;
    rec.stopped=true;
    navigator.geolocation.clearWatch(rec.watch);clearInterval(rec.tick);clearInterval(rec.save);
    document.removeEventListener('visibilitychange',visible);rec.lock?.release?.().catch(()=>{});
  }
  async function finish(reason){
    if(!rec||busy)return;busy=true;setBusy(true);
    try{
      halt();await persist();
      const done=rec;rec=null;
      if(done.points.length<2){message={key:'tooShort',error:true};view='list';render();return;}
      pending={id:done.id,draft:done.saved,source:'record',points:done.points,spots:[],durationSec:Math.min(604800,Math.round((Date.now()-done.startedAt)/1000)),date:localDate(new Date(done.startedAt)),name:fill('defaultName',{date:dayText(localDate(new Date(done.startedAt)))})};
      const saved=track(done.id);if(saved)Object.assign(pending,{name:saved.name,date:saved.date,dogs:[...saved.dogs]});
      message=reason?{key:reason,error:false}:null;view='save';render();
    }finally{busy=false;setBusy(false);}
  }
  async function discard(){if(busy)return;busy=true;setBusy(true);try{halt();const stopped=rec;rec=null;await stopped?.write;await clearDraft(stopped?stopped.saved:draftSaved);pending=null;view='list';render();}finally{busy=false;setBusy(false);}}

  // ---- import / export ----
  async function importFile(file){
    const started=operation;message=null;
    if(tracks().length>=M.LIMITS.tracks){message={key:'tooManyTracks',error:true};render();return;}
    if(file.size>M.LIMITS.fileBytes){message={key:'tooBig',error:true};render();return;}
    try{
      const content=await file.text();if(started!==operation)return;
      const parsed=M.parseGpx(content,localDate()),first=parsed.points.find(p=>p[2]!==null);
      const date=first?localDate(new Date(first[2]*1000)):localDate();
      pending={source:'import',points:parsed.points,spots:parsed.spots,durationSec:M.timeSpan(parsed.points),date,
        name:M.clean(parsed.name||file.name.replace(/\.gpx$/i,''),M.LIMITS.name)||fill('defaultName',{date:dayText(date)})};
      view='save';
    }catch(error){message={key:error instanceof M.BaladeError&&error.code!=='invalid'?error.code:'xml',error:true};}
    render();
  }
  function exportTrack(t){
    const blob=new Blob([M.toGpx(t,text)],{type:'application/gpx+xml'}),a=document.createElement('a');
    a.href=URL.createObjectURL(blob);a.download=`balade-${t.date}-${t.name.normalize('NFD').replace(/[̀-ͯ]/g,'').toLowerCase().replace(/[^a-z0-9]+/g,'-').replace(/^-|-$/g,'').slice(0,40)||'trace'}.gpx`;
    document.body.append(a);a.click();a.remove();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
  }

  // ---- spots ----
  function openSpot(at,existing=null){
    if(busy)return;abandon();
    const t=track(current);if(!t)return;
    if(!existing&&t.spots.length>=M.LIMITS.spots){message={key:'tooManySpots',error:true};render();return;}
    placing=false;
    spot=existing?{...existing}:{id:null,type:'pause',lat:Math.round(at.lat*1e6)/1e6,lon:Math.round(at.lon*1e6)/1e6,note:'',rule:'',noted:localDate()};
    view='spot';render();$('#spot-form [name=type]:checked')?.focus();
  }
  function placeWithoutMap(){const t=track(current),p=t.points[Math.floor(t.points.length/2)];openSpot({lat:p[0],lon:p[1]});}

  // ---- linking to a walk ticked in Planning ----
  function linkTo(id,next,ref){
    const t=target(next,id);if(!ref)return;
    for(const other of next.tracks)other.walkRefs=other.walkRefs.filter(r=>!(r.date===ref.date&&r.dogId===ref.dogId));
    if(!t.dogs.includes(ref.dogId))t.dogs.push(ref.dogId);
    t.walkRefs.push({...ref});
  }
  function linked_done(ref){link=null;showToast(fill('linkedToast',{dog:dogName(ref.dogId)}));view='list';navigate('schedule');}

  // ---- views ----
  const messageHtml=()=>message?`<div id="balades-message" class="${message.error?'daily-error':'balades-info'}" role="${message.error?'alert':'status'}">${esc(text(message.key))}${retry?` <button class="ghost" type="button" data-b="replay">${esc(text('reloadRetry'))}</button>`:''}</div>`:'<div id="balades-message" hidden></div>';
  const meta=t=>`${esc(dayText(t.date))} · ${esc(km(M.distance(t.points)))} · ${esc(clock(t.durationSec))}<br><span translate="no">${esc(dogList(t.dogs))}</span>`;
  const legend=()=>`<ul class="balades-legend" id="balades-legend" aria-label="${esc(text('legend'))}">${M.TYPES.map(type=>`<li><span class="balade-marker balade-${type}" aria-hidden="true">${ICONS[type]}</span>${esc(text(type))}</li>`).join('')}</ul>`;
  const linkBanner=()=>link?`<div class="balades-info" role="status">${esc(fill('linkBanner',{dog:dogName(link.dogId),date:dayText(link.date)}))} <button class="link-button" type="button" data-b="cancel-link">${esc(text('cancelLink'))}</button></div>`:'';
  const discardPrompt=()=>confirmDelete?`<div class="balades-confirm" role="alert"><p>${esc(text('discardConfirm'))}</p><div class="daily-actions"><button class="primary" type="button" data-b="discard">${esc(text('discardYes'))}</button><button class="ghost" type="button" data-b="discard-no">${esc(text('keepRecording'))}</button></div></div>`:'';
  function listView(){
    const all=tracks().slice().sort((a,b)=>b.date.localeCompare(a.date)||a.name.localeCompare(b.name));
    const resume=draftFound?`<section class="card balades-draft"><h2>${esc(text('draftTitle'))}</h2><p>${esc(fill('draftBody',{distance:km(M.distance(draftFound.points)),time:clock(Math.round(((draftFound.savedAt||Date.now())-draftFound.startedAt)/1000))}))}</p><div class="daily-actions"><button class="primary" type="button" data-b="resume">${esc(text('resume'))}</button><button class="ghost" type="button" data-b="finish-draft">${esc(text('finishNow'))}</button><button class="ghost" type="button" data-b="discard-ask">${esc(text('discard'))}</button></div>${discardPrompt()}</section>`:'';
    const rows=all.map(t=>`<article class="daily-record balade-row" data-track="${esc(t.id)}"><div><strong translate="no">${esc(t.name)}</strong><p>${meta(t)}</p>${t.spots.length?`<small>${esc(fill('spotCount',{count:t.spots.length}))}</small>`:''}</div><div class="daily-actions">${link?`<button class="primary" type="button" data-b="link" data-id="${esc(t.id)}">${esc(text('linkThis'))}</button>`:''}<button class="ghost" type="button" data-b="open" data-id="${esc(t.id)}">${esc(text('open'))}</button></div></article>`).join('');
    return `${linkBanner()}${resume}<div class="daily-toolbar balades-toolbar"><button class="primary" type="button" data-b="record" ${draftFound?'disabled':''}>● ${esc(text('record'))}</button><label class="ghost balades-file">${esc(text('import'))}<input type="file" id="balades-import" accept=".gpx,application/gpx+xml,application/xml,text/xml"></label></div><p class="daily-help">${esc(text('importHelp'))}</p>${messageHtml()}<h2 class="balades-heading">${esc(text('tracks'))}</h2>${rows||`<p class="daily-empty">${esc(text('empty'))}</p>`}`;
  }
  function recordView(){
    return `<section class="card balades-recording" aria-labelledby="rec-title"><h2 id="rec-title">${esc(text('recording'))}</h2><p class="balades-warning" role="note">${esc(text('screenOn'))}</p><p class="daily-help"><span id="rec-wake">${esc(text(rec.lockState))}</span> · <span id="rec-gps" aria-live="polite">${esc(text(rec.gps))}</span></p><dl class="balades-stats"><div><dt>${esc(text('distance'))}</dt><dd id="rec-distance">${esc(km(M.distance(rec.points)))}</dd></div><div><dt>${esc(text('duration'))}</dt><dd id="rec-time">${esc(clock(Math.round((Date.now()-rec.startedAt)/1000)))}</dd></div><div><dt>${esc(text('points'))}</dt><dd id="rec-points">${rec.points.length}</dd></div><div><dt>${esc(text('accuracy'))}</dt><dd id="rec-accuracy">${rec.accuracy===null?'—':`± ${Math.round(rec.accuracy)} m`}</dd></div></dl>${messageHtml()}<div class="daily-actions"><button class="primary" type="button" data-b="finish">${esc(text('finish'))}</button><button class="ghost" type="button" data-b="discard-ask">${esc(text('discard'))}</button></div>${discardPrompt()}</section>`;
  }
  const dogBoxes=(selected,locked)=>{
    const list=Object.entries(typeof dogs!=='undefined'?dogs:{}).sort(([,a],[,b])=>a.name.localeCompare(b.name,formatLocale(Intl.Collator)));
    return list.length?`<fieldset class="walk-list"><legend class="daily-field">${esc(text('dogs'))}</legend>${list.map(([id,d])=>`<label class="walk-dog"><input type="checkbox" name="dog" value="${esc(id)}" ${selected.includes(id)?'checked':''} ${locked===id?'disabled':''}><span><strong translate="no">${esc(d.name)}</strong></span></label>`).join('')}</fieldset>`:`<p class="daily-empty">${esc(text('noDogsYet'))}</p>`;
  };
  function trackForm(id,values,heading,submit,cancel){
    const locked=link&&view==='save'?link.dogId:null,selected=locked&&!values.dogs.includes(locked)?[...values.dogs,locked]:values.dogs;
    return `<form id="${id}" class="card daily-form" novalidate><h2>${esc(heading)}</h2>${values.summary||''}<div class="daily-fields"><label class="daily-field">${esc(text('name'))}<input name="name" required maxlength="${M.LIMITS.name}" value="${esc(values.name)}"></label><label class="daily-field">${esc(text('date'))}<input name="date" type="date" required value="${esc(values.date)}" max="${localDate()}"></label></div>${dogBoxes(selected,locked)}${messageHtml()}<div class="daily-actions"><button class="primary" type="submit">${esc(submit)}</button><button class="ghost" type="button" data-b="${cancel}">${esc(text('cancel'))}</button></div></form>`;
  }
  function saveView(){
    const summary=`<p class="daily-help">${esc(km(M.distance(pending.points)))} · ${esc(clock(pending.durationSec))} · ${esc(fill('pointCount',{count:pending.points.length}))}${pending.spots.length?' · '+esc(fill('spotCount',{count:pending.spots.length})):''}</p>`;
    return `${linkBanner()}${trackForm('track-form',{name:pending.name,date:pending.date,dogs:pending.dogs||[],summary},text(pending.source==='record'?'saveRecorded':'saveImported'),text('save'),'cancel-save')}`;
  }
  function spotItem(s){
    const rule=s.type==='tolere'?`<div class="balade-rule-pair"><div><h4>${esc(text('practice'))}</h4><p>${esc(s.note||'—')}</p></div><div><h4>${esc(text('officialRule'))}</h4><p>${esc(s.rule||'—')}</p></div></div><p class="daily-help">${esc(text('tolereNotice'))}</p>`:`<p>${esc(s.note||'—')}</p>`;
    return `<li class="balade-spot" id="spot-${esc(s.id)}" tabindex="-1"><div class="balade-spot-head"><span class="balade-marker balade-${s.type}" aria-hidden="true">${ICONS[s.type]}</span><strong>${esc(text(s.type))}</strong><small>${esc(fill('notedOn',{date:dayText(s.noted)}))}</small></div>${rule}<div class="daily-actions"><button class="link-button" type="button" data-b="edit-spot" data-id="${esc(s.id)}">${esc(text('edit'))}</button><button class="link-button" type="button" data-b="delete-spot" data-id="${esc(s.id)}">${esc(text('delete'))}</button></div></li>`;
  }
  function trackView(){
    if(editing)return trackForm('edit-form',editing,text('editTrack'),text('save'),'cancel-edit');
    const t=track(current);if(!t){view='list';return listView();}
    const walks=t.walkRefs.length?`<ul class="balades-walks">${t.walkRefs.map(r=>`<li><span translate="no">${esc(dogName(r.dogId))}</span> · ${esc(dayText(r.date))} <button class="link-button" type="button" data-b="unlink" data-date="${esc(r.date)}" data-dog="${esc(r.dogId)}">${esc(text('unlink'))}</button></li>`).join('')}</ul>`:'';
    const place=placing?`<div class="balades-info" role="status">${esc(text(mapFailed?'placeNoMap':'placeHelp'))}<div class="daily-actions">${mapFailed?'':`<button class="ghost" type="button" data-b="place-center">${esc(text('placeCenter'))}</button>`}<button class="link-button" type="button" data-b="place-cancel">${esc(text('cancel'))}</button></div></div>`:'';
    const remove=confirmDelete?`<div class="balades-confirm" role="alert"><p>${esc(fill('deleteConfirm',{name:t.name}))}</p><div class="daily-actions"><button class="primary" type="button" data-b="delete">${esc(text('deleteYes'))}</button><button class="ghost" type="button" data-b="delete-no">${esc(text('cancel'))}</button></div></div>`:'';
    return `${linkBanner()}<button class="link-button" type="button" data-b="back">← ${esc(text('allTracks'))}</button><section class="card balades-track"><h2 translate="no">${esc(t.name)}</h2><p class="daily-help">${meta(t)}</p>${walks?`<h3>${esc(text('linkedWalks'))}</h3>${walks}`:''}${link?`<button class="primary" type="button" data-b="link" data-id="${esc(t.id)}">${esc(text('linkThis'))}</button>`:''}${messageHtml()}<div class="daily-actions balades-actions"><button class="primary" type="button" data-b="add-spot" ${placing?'aria-pressed="true"':''}>＋ ${esc(text('addSpot'))}</button><button class="ghost" type="button" data-b="edit">${esc(text('edit'))}</button><button class="ghost" type="button" data-b="export">${esc(text('export'))}</button><button class="ghost" type="button" data-b="delete-ask">${esc(text('delete'))}</button></div>${place}${remove}<h3>${esc(text('spots'))}</h3>${t.spots.length?`<ul class="balades-spots">${t.spots.map(spotItem).join('')}</ul>`:`<p class="daily-empty">${esc(text('noSpots'))}</p>`}</section>`;
  }
  function spotView(){
    const hint=type=>`<small>${esc(text(type+'Hint'))}</small>`;
    return `<form id="spot-form" class="card daily-form" novalidate><h2>${esc(text(spot.id?'editSpot':'newSpot'))}</h2><fieldset class="balades-types"><legend>${esc(text('spotType'))}</legend>${M.TYPES.map(type=>`<label class="balades-type"><input type="radio" name="type" value="${type}" ${spot.type===type?'checked':''}><span class="balade-marker balade-${type}" aria-hidden="true">${ICONS[type]}</span><span><strong>${esc(text(type))}</strong>${hint(type)}</span></label>`).join('')}</fieldset><label class="daily-field">${esc(text(spot.type==='tolere'?'practice':'note'))}<textarea name="note" maxlength="${M.LIMITS.note}" rows="3" placeholder="${esc(text(spot.type+'Placeholder'))}">${esc(spot.note)}</textarea></label><label class="daily-field" id="spot-rule" ${spot.type==='tolere'?'':'hidden'}>${esc(text('officialRule'))}<textarea name="rule" maxlength="${M.LIMITS.note}" rows="3" placeholder="${esc(text('rulePlaceholder'))}">${esc(spot.rule)}</textarea></label><div class="daily-fields"><label class="daily-field">${esc(text('noted'))}<input name="noted" type="date" required value="${esc(spot.noted)}" max="${localDate()}"></label></div><details class="daily-help"><summary>${esc(text('position'))}</summary><div class="daily-fields"><label class="daily-field">${esc(text('latitude'))}<input name="lat" inputmode="decimal" value="${esc(spot.lat)}"></label><label class="daily-field">${esc(text('longitude'))}<input name="lon" inputmode="decimal" value="${esc(spot.lon)}"></label></div></details>${messageHtml()}<div class="daily-actions"><button class="primary" type="submit">${esc(text('saveSpot'))}</button><button class="ghost" type="button" data-b="cancel-spot">${esc(text('cancel'))}</button></div></form>`;
  }
  function panel(){
    if(rec&&view!=='record')view='record';
    return view==='record'?recordView():view==='save'&&pending?.points?saveView():view==='spot'&&spot?spotView():view==='track'?trackView():(view='list',listView());
  }
  function view_(){
    const failed=ready&&S.unavailable()&&!retry;
    return `<div class="balades" id="balades-root"><p class="balades-intro">${esc(text('intro'))}</p>${w.DogCareAPI?'':`<p class="daily-storage">${esc(text('browserOnly'))}</p>`}<div id="balades-map" class="balades-map" role="region" aria-label="${esc(text('map'))}" hidden></div><p class="daily-help balades-map-note" id="balades-map-note" ${mapFailed?'':'hidden'}>${mapFailed?esc(text('mapUnavailable')):''}</p>${legend().replace('<ul ','<ul hidden ')}${draftHtml()}<div id="balades-panel">${!ready?`<p class="daily-help" role="status">${esc(text('loading'))}</p>`:failed?`<p class="daily-error" role="alert">${esc(text('loadError'))}</p><button class="primary" type="button" data-b="retry-load">${esc(text('retry'))}</button>`:panel()}</div><p class="daily-help balades-privacy">${esc(text('privacy'))}</p></div>`;
  }
  function render(fit=true){
    if(!onPage()||!ready)return;
    $('#balades-panel').innerHTML=S.unavailable()&&!retry?`<p class="daily-error" role="alert">${esc(text('loadError'))}</p><button class="primary" type="button" data-b="retry-load">${esc(text('retry'))}</button>`:panel();
    bindPanel();if(busy)setBusy(true);draftStatus();drawMap(fit);
    if(fit)window.scrollTo({top:0,behavior:'instant'});
  }

  // ---- events ----
  const actions={
    record:()=>start(null),
    resume:()=>start(draftFound),
    'finish-draft':async()=>{const d=draftFound;rec={...d,id:d.id||uid(),saved:draftSaved,watch:null,tick:null,save:null,lock:null};await finish();},
    finish:()=>finish(),
    'discard-ask':()=>{confirmDelete=true;render(false);},
    'discard-no':()=>{confirmDelete=false;render(false);},
    discard:()=>{confirmDelete=false;discard();},
    'cancel-save':()=>{pending=null;message=null;view='list';render();},
    'cancel-link':()=>{link=null;render(false);},
    open:el=>{current=el.dataset.id;view='track';message=null;placing=false;confirmDelete=false;editing=false;render();},
    back:()=>{view='list';current=null;placing=false;confirmDelete=false;editing=false;message=null;render();},
    link:el=>{const id=el.dataset.id,ref={...link};return commit(next=>linkTo(id,next,ref),()=>linked_done(ref));},
    unlink:el=>{const id=current,{date,dog}=el.dataset;return commit(next=>{const t=target(next,id);t.walkRefs=t.walkRefs.filter(r=>!(r.date===date&&r.dogId===dog));},()=>render(false));},
    'add-spot':()=>{message=null;if(mapFailed||!map){placeWithoutMap();return;}placing=!placing;render(false);if(placing)$('#balades-map').scrollIntoView({block:'center',behavior:'instant'});},
    'place-center':()=>{const c=map.getCenter();openSpot({lat:c.lat,lon:c.lng});},
    'place-cancel':()=>{placing=false;render(false);},
    edit:()=>{const t=track(current);if(!t)return;editing={name:t.name,date:t.date,dogs:[...t.dogs]};message=null;render(false);},
    'cancel-edit':()=>{editing=false;message=null;render(false);},
    export:()=>exportTrack(track(current)),
    'delete-ask':()=>{confirmDelete=true;render(false);},
    'delete-no':()=>{confirmDelete=false;render(false);},
    delete:()=>{const id=current;return commit(next=>{next.tracks=next.tracks.filter(t=>t.id!==id);},()=>{confirmDelete=false;current=null;view='list';showToast(text('deleted'));render();});},
    'edit-spot':el=>openSpot(null,track(current).spots.find(s=>s.id===el.dataset.id)),
    'delete-spot':el=>{const id=current,spotId=el.dataset.id;return commit(next=>{const t=target(next,id);t.spots=t.spots.filter(s=>s.id!==spotId);},()=>render(false));},
    'cancel-spot':()=>{spot=null;message=null;view='track';render(false);},
    replay:()=>replay(),
    'retry-load':async()=>{await S.reload();if(!draftFound&&!S.unavailable())draftFound=draftSaved=await S.draft();render();}
  };
  const readForm=form=>({name:form.elements.name.value,date:form.elements.date.value,dogs:[...form.querySelectorAll('[name=dog]')].filter(b=>b.checked).map(b=>b.value)});
  function formValues(form){
    const name=form.elements.name.value.trim(),date=form.elements.date.value;
    const chosen=readForm(form).dogs;
    if(!name){message={key:'nameRequired',error:true};return null;}
    if(!M.date(date)||date>localDate()){message={key:'dateInvalid',error:true};return null;}
    return {name:M.clean(name,M.LIMITS.name),date,dogs:chosen};
  }
  function bindPanel(){
    document.querySelectorAll('#balades-panel [data-b]').forEach(el=>el.onclick=e=>{e.preventDefault();if(!busy){if(el.dataset.b!=='replay')abandon();actions[el.dataset.b]?.(el);}});
    const file=$('#balades-import');if(file)file.onchange=()=>{if(busy)return;const f=file.files[0];file.value='';if(f){abandon();importFile(f);}};
    const save=$('#track-form');
    if(save)save.oninput=()=>{Object.assign(pending,readForm(save));abandon();};
    if(save)save.onsubmit=async e=>{
      e.preventDefault();if(busy)return;abandon();Object.assign(pending,readForm(save));const values=formValues(save);if(!values){render(false);return;}
      const id=pending.id||=uid(),source=pending.source,ref=link?{...link}:null,draft=pending;
      const made={id,name:values.name,date:values.date,dogs:values.dogs,points:pending.points,durationSec:pending.durationSec,source,walkRefs:[],spots:pending.spots};
      await commit(next=>{const saved=next.tracks.find(t=>t.id===id);if(saved){Object.assign(saved,values);if(source==='record')Object.assign(saved,{points:made.points,durationSec:made.durationSec});saved.walkRefs=saved.walkRefs.filter(r=>saved.dogs.includes(r.dogId));}else next.tracks.push(structuredClone(made));if(ref)linkTo(id,next,ref);},()=>{
        if(ref){linked_done(ref);return;}
        current=id;view='track';showToast(text('saved'));render();
      },async()=>{
        if(source==='record')await clearDraft(draft.draft);
        if(pending===draft){pending=null;if(view==='save')view='list';}
      });
    };
    const edit=$('#edit-form');
    if(edit)edit.oninput=()=>{editing=readForm(edit);abandon();};
    if(edit)edit.onsubmit=async e=>{
      e.preventDefault();if(busy)return;abandon();editing=readForm(edit);const values=formValues(edit);if(!values){render(false);return;}
      const id=current;await commit(next=>{const t=target(next,id);Object.assign(t,values);t.walkRefs=t.walkRefs.filter(r=>t.dogs.includes(r.dogId));},()=>{editing=false;showToast(text('saved'));render(false);});
    };
    const form=$('#spot-form');
    if(form){
      const remember=()=>{for(const key of ['type','lat','lon','note','rule','noted'])spot[key]=form.elements[key].value;};
      form.oninput=()=>{remember();abandon();};
      form.querySelectorAll('[name=type]').forEach(r=>r.onchange=()=>{const tolere=form.elements.type.value==='tolere';$('#spot-rule').hidden=!tolere;
        const note=form.elements.note;note.placeholder=text(form.elements.type.value+'Placeholder');note.closest('label').firstChild.nodeValue=text(tolere?'practice':'note');});
      form.onsubmit=async e=>{
        e.preventDefault();if(busy)return;abandon();remember();
        const type=form.elements.type.value,rawLat=String(form.elements.lat.value).trim(),rawLon=String(form.elements.lon.value).trim(),lat=Number(rawLat.replace(',','.')),lon=Number(rawLon.replace(',','.')),noted=form.elements.noted.value;
        if(!M.date(noted)||noted>localDate()){message={key:'dateInvalid',error:true};render(false);return;}
        if(!rawLat||!rawLon){message={key:'positionRequired',error:true};render(false);return;}
        if(!(Number.isFinite(lat)&&lat>=-90&&lat<=90&&Number.isFinite(lon)&&lon>=-180&&lon<=180)){message={key:'positionInvalid',error:true};render(false);return;}
        const value={id:spot.id||=uid(),type,lat,lon,note:M.clean(form.elements.note.value,M.LIMITS.note),rule:type==='tolere'?M.clean(form.elements.rule.value,M.LIMITS.note):'',noted};
        const id=current;await commit(next=>{const t=target(next,id),at=t.spots.findIndex(s=>s.id===value.id);if(at<0)t.spots.push(value);else t.spots[at]=value;},()=>{spot=null;view='track';showToast(text('spotSaved'));render(false);});
      };
    }
  }

  // Planning: under the walk checklist, each walk saved for that day can carry its track.
  function walkLinks(date,dogIds){
    if(!ready||S.unavailable()||!dogIds.length)return '<div id="walk-tracks"></div>';
    return `<div id="walk-tracks" class="walk-tracks"><h3>${esc(text('walkTracks'))}</h3>${dogIds.map(id=>{const t=linked(date,id);
      return `<div class="walk-track"><span translate="no">${esc(dogName(id))}</span>${t?`<button class="link-button" type="button" data-balade-open="${esc(t.id)}">${esc(text('viewTrack'))} ↗</button>`:`<button class="link-button" type="button" data-balade-link="${esc(id)}" data-balade-date="${esc(date)}">＋ ${esc(text('addTrack'))}</button>`}</div>`;}).join('')}</div>`;
  }
  document.addEventListener('click',e=>{
    const add=e.target.closest('[data-balade-link]'),show=e.target.closest('[data-balade-open]');
    if(add){abandon();link={date:add.dataset.baladeDate,dogId:add.dataset.baladeLink};view=rec?'record':'list';current=null;message=null;navigate('balades');}
    else if(show&&track(show.dataset.baladeOpen)){abandon();link=null;current=show.dataset.baladeOpen;view=rec?'record':'track';editing=false;confirmDelete=false;message=null;navigate('balades');}
  });
  function refreshPlanning(){
    const box=$('#walk-tracks'),form=$('#walk-form');if(!box||!form||state.page!=='schedule')return;
    const date=form.elements.date.value,done=[...form.querySelectorAll('[name="walked"]')].filter(b=>b.defaultChecked).map(b=>b.value);
    box.outerHTML=walkLinks(date,done);
  }
  async function load(){
    await S.load();
    if(!draftFound&&!S.unavailable())draftFound=draftSaved=await S.draft();
    ready=true;
    refreshPlanning();if(onPage())render();
  }
  function bind(){
    placing=false;
    if(!ready)return;
    bindPanel();if(busy)setBusy(true);drawMap();
  }
  function leave(){abandon();drawing++;mapReady=null;mapBox=null;if(map){map.remove();map=null;markers=[];}placing=false;}
  w.BaladesUI={text,load,view:view_,bind,leave,walkLinks,recording:()=>!!rec};
})(window);

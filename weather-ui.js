(function(w){
  'use strict';
  const M=w.WalkWeatherModel, KEY='dogcare-weather-settings-v1';
  const text=key=>(w.WalkWeatherCopy[state.language]||w.WalkWeatherCopy.fr)[key];
  const esc=value=>String(value).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const read=()=>M.settings(w.DogCareAPI?w.DogCareAPI.getWeatherSettings():JSON.parse(localStorage.getItem(KEY)||JSON.stringify(M.empty())));
  let context=null;
  async function json(url){
    const controller=new AbortController(),timer=setTimeout(()=>controller.abort(),M.LIMITS.timeoutMs);
    try{const response=await fetch(url,{signal:controller.signal,credentials:'omit',referrerPolicy:'no-referrer'});if(!response.ok)throw Error('network');return await response.json();}
    finally{clearTimeout(timer);}
  }
  function forecastContext(location){
    const scope=w.DogCareAPI?w.DogCareAPI.weatherCacheScope():'static',key=M.locationKey(location),storageKey='dogcare-weather-forecast-v1:'+scope;
    if(context?.key===key&&context.scope===scope)return context;
    context={scope,key,storageKey,forecast:null,fetchedAt:0,lastAttempt:0,failed:false,pending:null};
    try{
      const saved=JSON.parse(localStorage.getItem(storageKey));
      if(saved?.location===key&&Number.isFinite(saved.fetchedAt)&&saved.fetchedAt>0&&saved.fetchedAt<=Date.now()){
        context.forecast=M.parse(saved.raw);context.fetchedAt=saved.fetchedAt;
      }
    }catch{/* An unreadable cache never blocks the workspace. */}
    return context;
  }
  function mount(){
    const target=document.querySelector('#walk-weather');
    if(!target)return;
    let config;try{config=read();}catch{target.innerHTML='';return;}
    if(!config.location){
      target.innerHTML=`<section class="weather-strip"><h2>${esc(text('title'))}</h2><p>${esc(text('noLocation'))}</p>${PortalUI.owner()?`<button class="ghost" data-weather-settings>${esc(text('configure'))}</button>`:`<p>${esc(text('staffLocation'))}</p>`}</section>`;
      target.querySelector('[data-weather-settings]')?.addEventListener('click',()=>navigate('settings'));return;
    }
    const ctx=forecastContext(config.location);
    paint(target,ctx,config);
    const now=Date.now();
    if(!ctx.pending&&now-ctx.fetchedAt>=M.LIMITS.cacheMs&&now-ctx.lastAttempt>=M.LIMITS.retryMs){
      ctx.lastAttempt=now;
      ctx.pending=json(M.forecastURL(config.location)).then(raw=>{
        ctx.forecast=M.parse(raw);ctx.fetchedAt=Date.now();ctx.failed=false;
        // A location changed while this request ran: leave the new location's cache alone.
        if(context===ctx)try{localStorage.setItem(ctx.storageKey,JSON.stringify({location:ctx.key,fetchedAt:ctx.fetchedAt,raw}));}catch{}
      }).catch(()=>{ctx.failed=true;}).finally(()=>{
        ctx.pending=null;
        if(context===ctx&&document.querySelector('#walk-weather'))mount();
      });
    }
  }
  const format=(value,unit='',digits=0)=>value===null?'—':new Intl.NumberFormat(state.language,{maximumFractionDigits:digits}).format(value)+unit;
  function paint(target,ctx,config){
    if(!ctx.forecast){target.innerHTML='';return;}
    const days=M.days(ctx.forecast,config.heatThreshold);
    if(!days.length){target.innerHTML='';return;}
    const clock=time=>M.local(time,ctx.forecast.timezone).clock;
    const stale=ctx.failed||Date.now()-ctx.fetchedAt>=M.LIMITS.cacheMs;
    const stamp=new Intl.DateTimeFormat(state.language,{timeZone:ctx.forecast.timezone,dateStyle:'short',timeStyle:'short'}).format(ctx.fetchedAt);
    const expanded=target.querySelector('details')?.open;
    target.innerHTML=`<section class="weather-strip" aria-label="${esc(text('settings'))}"><div class="weather-heading"><h2>${esc(text('title'))}</h2><span>${esc(config.location.name)}</span></div>
      ${stale?`<p class="weather-cached">${esc(text(ctx.failed?'cached':'older'))}</p>`:''}
      ${days.map(day=>{
        const warnings=[...new Set(day.hours.flatMap(h=>M.warnings(h,config.heatThreshold)))];
        return `<div class="weather-day"><strong>${esc(text(day.label))}</strong><p class="weather-windows">${stale?'':day.windows.length?`${esc(text('best'))} · ${day.windows.map(win=>`<b>${clock(win.start)}–${clock(win.end)}</b>`).join(' / ')}`:esc(text('noWindow'))}</p>${warnings.length?`<p class="weather-warning">${warnings.map(k=>esc(text(k))+(k==='heat'?` ≥ ${format(config.heatThreshold,' °C',1)}`:'')).join(' · ')}</p>`:''}</div>`;
      }).join('')}
      <details ${expanded?'open':''}><summary>${esc(text('hourly'))}</summary><div class="weather-hours" tabindex="0" role="region" aria-label="${esc(text('hourly'))}">${days.map(day=>day.hours.map(h=>{
        const best=!stale&&day.windows.some(win=>h.time>=win.start&&h.time<win.end),warnings=M.warnings(h,config.heatThreshold);
        return `<article class="weather-hour ${best?'weather-best':''}"><strong>${esc(text(day.label))} ${h.clock}</strong>${best?`<span class="weather-best-label">${esc(text('best'))}</span>`:''}<dl><div><dt>${esc(text('temperature'))}</dt><dd>${format(h.temperature_2m,' °C',1)}</dd></div><div><dt>${esc(text('probability'))}</dt><dd>${format(h.precipitation_probability,' %')}</dd></div><div><dt>${esc(text('precipitation'))}</dt><dd>${format(h.precipitation,' mm',1)}</dd></div><div><dt>${esc(text('stormRisk'))}</dt><dd>${esc(text(h.weather_code===null?'unknown':h.weather_code>=95&&h.weather_code<=99?'stormYes':'stormNo'))}</dd></div><div><dt>${esc(text('uvIndex'))}</dt><dd>${format(h.uv_index,'',1)}</dd></div><div><dt>${esc(text('wind'))}</dt><dd>${format(h.wind_gusts_10m,' km/h')}</dd></div></dl>${warnings.length?`<p class="weather-warning">${warnings.map(k=>esc(text(k))).join(' · ')}</p>`:''}</article>`;
      }).join('')).join('')}</div><p class="weather-basis">${esc(text('basis'))}</p></details>
      <footer>${esc(text('updated'))} ${esc(stamp)} · ${esc(ctx.forecast.timezone)} · <a href="https://open-meteo.com/" target="_blank" rel="noopener noreferrer">Open-Meteo</a> · <a href="https://creativecommons.org/licenses/by/4.0/" target="_blank" rel="noopener noreferrer">CC BY 4.0</a></footer></section>`;
  }
  function settings(){
    let config;try{config=read();}catch{return `<section class="weather-settings card"><p>${esc(text('resetError'))}</p></section>`;}
    return `<section class="weather-settings card"><h2>${esc(text('settings'))}</h2><p>${esc(text('privacy'))}</p><form id="weather-search"><label for="weather-city">${esc(text('city'))}</label><div class="weather-actions"><input id="weather-city" name="city" maxlength="120" minlength="2" required autocomplete="off"><button class="ghost">${esc(text('search'))}</button><button type="button" id="weather-position" class="ghost">${esc(text('position'))}</button></div></form><p id="weather-search-status" role="status"></p><div id="weather-results"></div><form id="weather-settings-form"><p id="weather-selected">${esc(text('selected'))} : ${esc(config.location?.name||'—')}</p><button type="button" id="weather-clear" class="ghost">${esc(text('clear'))}</button><label for="weather-heat">${esc(text('heatThreshold'))}</label><input id="weather-heat" name="heat" type="number" min="${M.LIMITS.minHeat}" max="${M.LIMITS.maxHeat}" step="0.5" value="${config.heatThreshold}" required aria-describedby="weather-asphalt"><p id="weather-asphalt">${esc(text('asphalt'))}</p><button class="primary">${esc(text('save'))}</button><p id="weather-save-status" role="status"></p></form></section>`;
  }
  function bindSettings(){
    const form=document.querySelector('#weather-settings-form');if(!form)return;
    let selected=read().location;
    const loaded=w.DogCareAPI?null:localStorage.getItem(KEY),search=document.querySelector('#weather-search'),results=document.querySelector('#weather-results'),status=document.querySelector('#weather-search-status');
    let generation=0;
    const message=key=>{status.textContent=text(key);};
    const select=location=>{
      selected=location;document.querySelector('#weather-selected').textContent=text('selected')+' : '+(location?.name||'—');
      document.querySelector('#weather-save-status').textContent='';results.replaceChildren();status.textContent='';
    };
    search.onsubmit=async event=>{
      event.preventDefault();const query=search.city.value.trim();if(query.length<2)return;
      const request=++generation;status.textContent='';results.replaceChildren();
      try{
        const data=await json('https://geocoding-api.open-meteo.com/v1/search?'+new URLSearchParams({name:query,count:'5',language:state.language,format:'json'}));
        if(!form.isConnected||request!==generation)return;
        const locations=(Array.isArray(data.results)?data.results:[]).flatMap(p=>{
          const location={name:[p.name,p.admin1,p.country].filter(Boolean).join(', '),latitude:p.latitude,longitude:p.longitude};
          location.name=[...location.name].slice(0,120).join('');
          try{M.settings({location,heatThreshold:M.LIMITS.defaultHeat});return [location];}catch{return [];}
        });
        if(!locations.length){message('noResults');return;}
        for(const location of locations){const button=document.createElement('button');button.type='button';button.className='ghost';button.textContent=location.name;button.onclick=()=>{generation++;select(location);};results.append(button);}
      }catch{if(form.isConnected&&request===generation)message('searchError');}
    };
    document.querySelector('#weather-position').onclick=()=>{
      const request=++generation;status.textContent='';results.replaceChildren();
      const failed=()=>{if(form.isConnected&&request===generation)message('positionError');};
      if(!navigator.geolocation){failed();return;}
      navigator.geolocation.getCurrentPosition(position=>{
        if(!form.isConnected||request!==generation)return;
        const latitude=Math.round(position.coords.latitude*1000)/1000,longitude=Math.round(position.coords.longitude*1000)/1000;
        select({name:`${text('positionName')} (${latitude}, ${longitude})`,latitude,longitude});
      },failed,{enableHighAccuracy:false,timeout:M.LIMITS.timeoutMs,maximumAge:300000});
    };
    document.querySelector('#weather-clear').onclick=()=>{generation++;select(null);};
    form.oninput=()=>{document.querySelector('#weather-save-status').textContent='';};
    form.onsubmit=async event=>{
      event.preventDefault();let config;const notice=document.querySelector('#weather-save-status');
      try{config=M.settings({location:selected,heatThreshold:Number(form.heat.value)});}catch{notice.textContent=text('invalid');return;}
      const ok=await persistChange(async()=>{
        try{
          if(w.DogCareAPI)return await w.DogCareAPI.saveWeatherSettings(config);
          if(!navigator.locks)return false;
          return await navigator.locks.request(KEY,()=>{if(localStorage.getItem(KEY)!==loaded)return false;localStorage.setItem(KEY,JSON.stringify(config));return true;});
        }catch{return false;}
      },form.querySelector('[type=submit]')||form.querySelector('.primary'));
      if(ok){context=null;navigate('settings');document.querySelector('#weather-save-status').textContent=text('saved');}
      else notice.textContent=text('saveError');
    };
  }
  w.WalkWeatherUI={strip:()=>'<div id="walk-weather"></div>',settings,bind(){mount();bindSettings();}};
  // Update the day boundary / 18:00 reveal without replacing any Planning or GPS draft.
  setInterval(()=>{if(!document.hidden)mount();},60000);
  document.addEventListener('visibilitychange',()=>{if(!document.hidden)mount();});
})(window);

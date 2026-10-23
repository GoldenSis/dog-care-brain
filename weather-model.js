/* Forecast selection is pure: no dog, client or track data enters this module. */
(function(root,factory){const model=factory();if(typeof module==='object'&&module.exports)module.exports=model;else root.WalkWeatherModel=model;}(typeof window==='undefined'?globalThis:window,()=>{
  'use strict';
  const LIMITS=Object.freeze({defaultHeat:25,minHeat:0,maxHeat:50,heavyRain:5,strongGust:50,highUV:6,
    tomorrowHour:18,firstWalkHour:6,lastWalkHour:22,windowHours:2,maxWindows:2,
    cacheMs:30*60*1000,retryMs:60*1000,timeoutMs:10000});
  const FIELDS=['temperature_2m','precipitation_probability','precipitation','weather_code','uv_index','wind_gusts_10m'];
  const empty=()=>({location:null,heatThreshold:LIMITS.defaultHeat});
  const number=(v,min,max)=>typeof v==='number'&&Number.isFinite(v)&&v>=min&&v<=max;
  const keys=(v,expected)=>v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join(' ')===expected.split(' ').sort().join(' ');
  function settings(value){
    if(!keys(value,'location heatThreshold')||!number(value.heatThreshold,LIMITS.minHeat,LIMITS.maxHeat))throw Error('settings');
    const p=value.location;
    if(p!==null&&(!keys(p,'name latitude longitude')||typeof p.name!=='string'||!p.name.trim()||[...p.name].length>120||/[\x00-\x1f\x7f]/.test(p.name)||!number(p.latitude,-90,90)||!number(p.longitude,-180,180)))throw Error('location');
    return value;
  }
  const locationKey=p=>p?`${p.latitude},${p.longitude}`:'';
  function forecastURL(p){
    return 'https://api.open-meteo.com/v1/forecast?'+new URLSearchParams({latitude:p.latitude,longitude:p.longitude,hourly:FIELDS.join(','),timezone:'auto',timeformat:'unixtime',forecast_days:'2',temperature_unit:'celsius',wind_speed_unit:'kmh',precipitation_unit:'mm'});
  }
  function parse(data){
    const h=data?.hourly;
    if(!h||!Array.isArray(h.time)||!h.time.length||h.time.length>72||typeof data.timezone!=='string')throw Error('forecast');
    new Intl.DateTimeFormat('en',{timeZone:data.timezone}).format();
    if(FIELDS.some(key=>!Array.isArray(h[key])||h[key].length!==h.time.length))throw Error('forecast');
    const ranges=[[-100,70],[0,100],[0,1000],[0,99],[0,30],[0,500]];
    const hours=h.time.map((time,i)=>{
      if(!Number.isSafeInteger(time)||time<0||!Number.isFinite(new Date(time*1000).getTime())||(i&&time<=h.time[i-1]))throw Error('time');
      const values=FIELDS.map((key,j)=>number(h[key][i],...ranges[j])?h[key][i]:null);
      return {time,...Object.fromEntries(FIELDS.map((key,j)=>[key,values[j]]))};
    });
    // Open-Meteo labels these aggregates at the END of the preceding hour.
    // Cards and walk windows use interval starts; never guess the missing end row.
    const intervalFields=['precipitation_probability','precipitation','wind_gusts_10m'];
    const aligned=hours.map((hour,i)=>({...hour,...Object.fromEntries(intervalFields.map(key=>[
      key,hours[i+1]?.time===hour.time+3600?hours[i+1][key]:null
    ]))}));
    return {timezone:data.timezone,hours:aligned};
  }
  function local(time,timezone){
    const parts=Object.fromEntries(new Intl.DateTimeFormat('en-CA',{timeZone:timezone,year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date(time*1000)).map(p=>[p.type,p.value]));
    return {date:`${parts.year}-${parts.month}-${parts.day}`,hour:Number(parts.hour),clock:`${parts.hour}:${parts.minute}`};
  }
  function warnings(h,heat){
    return [h.temperature_2m!==null&&h.temperature_2m>=heat&&'heat',h.weather_code!==null&&h.weather_code>=95&&h.weather_code<=99&&'storm',h.precipitation!==null&&h.precipitation>=LIMITS.heavyRain&&'rain',h.wind_gusts_10m!==null&&h.wind_gusts_10m>=LIMITS.strongGust&&'gust',h.uv_index!==null&&h.uv_index>=LIMITS.highUV&&'uv'].filter(Boolean);
  }
  function bestWindows(hours,heat,now){
    const score=h=>h.precipitation_probability+20*h.precipitation+2*h.uv_index+h.wind_gusts_10m/5+Math.max(0,h.temperature_2m-20);
    const candidates=[];
    for(let i=0;i<hours.length-LIMITS.windowHours+1;i++){
      const pair=hours.slice(i,i+LIMITS.windowHours);
      if(pair.some((h,j)=>h.time<now||h.hour<LIMITS.firstWalkHour||h.hour>=LIMITS.lastWalkHour||FIELDS.some(k=>h[k]===null)||warnings(h,heat).length||(j&&h.time!==pair[j-1].time+3600)))continue;
      candidates.push({start:pair[0].time,end:pair.at(-1).time+3600,score:pair.reduce((sum,h)=>sum+score(h),0)});
    }
    const chosen=[];
    for(const candidate of candidates.sort((a,b)=>a.score-b.score||a.start-b.start)){
      if(chosen.every(w=>candidate.end<=w.start||candidate.start>=w.end))chosen.push(candidate);
      if(chosen.length===LIMITS.maxWindows)break;
    }
    return chosen.sort((a,b)=>a.start-b.start);
  }
  function days(forecast,heat,now=Date.now()){
    const current=local(now/1000,forecast.timezone);
    const tomorrow=new Date(Date.parse(current.date+'T12:00:00Z')+86400000).toISOString().slice(0,10);
    return [current.date,...(current.hour>=LIMITS.tomorrowHour?[tomorrow]:[])].map((date,index)=>{
      const hours=forecast.hours.map(h=>({...h,...local(h.time,forecast.timezone)})).filter(h=>h.date===date&&h.time+3600>now/1000);
      return {date,label:index?'tomorrow':'today',hours,windows:bestWindows(hours,heat,now/1000)};
    }).filter(day=>day.hours.length);
  }
  return {LIMITS,FIELDS,empty,settings,locationKey,forecastURL,parse,local,warnings,days};
}));

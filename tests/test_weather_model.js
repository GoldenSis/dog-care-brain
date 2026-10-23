const test=require('node:test');
const assert=require('node:assert/strict');
const M=require('../weather-model.js');
const start=Date.parse('2026-10-23T00:00:00Z')/1000;
function fixture(){return {timezone:'Europe/Zurich',hourly:{time:Array.from({length:48},(_,i)=>start+i*3600),...Object.fromEntries(M.FIELDS.map((key,i)=>[key,Array(48).fill([18,10,0,0,2,12][i])]))}};}

test('business timezone reveals tomorrow at 18:00, independent of browser timezone',()=>{
  const forecast=M.parse(fixture());
  assert.deepEqual(M.days(forecast,25,Date.parse('2026-10-23T15:59Z')).map(d=>d.label),['today']);
  assert.deepEqual(M.days(forecast,25,Date.parse('2026-10-23T16:00Z')).map(d=>d.label),['today','tomorrow']);
  assert.equal(M.days(forecast,25,Date.parse('2026-10-23T22:01Z'))[0].date,'2026-10-24');
  assert.equal(M.local(Date.parse('2026-10-25T00:00Z')/1000,'Europe/Zurich').clock,'02:00');
  assert.equal(M.local(Date.parse('2026-10-25T01:00Z')/1000,'Europe/Zurich').clock,'02:00');
});
test('heat, storms 95–99, rain, UV and gusts exclude each affected hour from suggestions',()=>{
  for(const [field,value] of [['temperature_2m',25],['precipitation',5],['uv_index',6],['wind_gusts_10m',50],...[95,96,97,98,99].map(v=>['weather_code',v])]){
    const raw=fixture();raw.hourly[field].fill(value);const day=M.days(M.parse(raw),25,start*1000)[0];
    assert.equal(day.windows.length,0,field+' '+value);assert.ok(M.warnings(day.hours[0],25).length);
  }
  const raw=fixture();raw.hourly.temperature_2m.fill(26);
  assert.equal(M.days(M.parse(raw),27,start*1000)[0].windows.length,2);
});
test('unknown fields are never treated as zero or preferred conditions',()=>{
  for(const value of [null,'0',undefined,NaN,-2]){
    const raw=fixture();raw.hourly.precipitation.fill(value);const forecast=M.parse(raw);
    assert.equal(forecast.hours[0].precipitation,null);
    assert.equal(M.days(forecast,25,start*1000)[0].windows.length,0);
  }
  const raw=fixture();raw.hourly.uv_index.pop();assert.throws(()=>M.parse(raw));
  raw.hourly.uv_index.push(2);raw.timezone='Bad/Zone';assert.throws(()=>M.parse(raw));
  const invalidTime=fixture();invalidTime.hourly.time[0]=Number.MAX_SAFE_INTEGER;assert.throws(()=>M.parse(invalidTime));
});
test('suggestions have two continuous future hours, never overlap or cross the chosen day',()=>{
  const now=Date.parse('2026-10-23T11:15Z'),raw=fixture();
  const day=M.days(M.parse(raw),25,now)[0];
  assert.equal(day.windows.length,2);
  for(const win of day.windows){assert.ok(win.start>=now/1000);assert.equal(win.end-win.start,7200);}
  assert.ok(day.windows[0].end<=day.windows[1].start);
  const last=M.days(M.parse(raw),25,Date.parse('2026-10-23T19:01Z'))[0];assert.deepEqual(last.windows,[]);
});
test('forecast request sends only coordinates and explicit weather controls',()=>{
  const url=new URL(M.forecastURL({latitude:0,longitude:0,name:'private',dogs:['private']}));
  assert.equal(url.origin,'https://api.open-meteo.com');assert.equal(url.searchParams.get('timezone'),'auto');
  assert.equal(url.searchParams.get('forecast_days'),'2');assert.equal(url.searchParams.get('hourly'),M.FIELDS.join(','));
  assert.ok(!url.toString().includes('private'));
});
test('settings reject invalid data and copy has all five languages with identical keys',()=>{
  assert.deepEqual(M.settings(M.empty()),{location:null,heatThreshold:25});
  for(const value of [null,{}, {...M.empty(),heatThreshold:true},{...M.empty(),heatThreshold:Infinity},{...M.empty(),heatThreshold:-1}])assert.throws(()=>M.settings(value));
  const vm=require('node:vm'),fs=require('node:fs'),context={window:{}};vm.runInNewContext(fs.readFileSync(require.resolve('../weather-copy.js'),'utf8'),context);
  const copy=context.window.WalkWeatherCopy;assert.deepEqual(Object.keys(copy).sort(),['de','en','es','fr','it']);
  for(const language of Object.values(copy))assert.deepEqual(Object.keys(language).sort(),Object.keys(copy.fr).sort());
});


test('preceding-hour rain, probability and gusts exclude the interval before their timestamp',()=>{
  const raw=fixture(),i=12; // 14:00 Zurich row describes rain/gusts from 13:00–14:00.
  raw.hourly.precipitation[i]=10;raw.hourly.precipitation_probability[i]=100;raw.hourly.wind_gusts_10m[i]=80;
  const forecast=M.parse(raw),hour=forecast.hours[i-1];
  assert.equal(M.local(hour.time,forecast.timezone).clock,'13:00');
  assert.equal(hour.precipitation_probability,100);
  assert.deepEqual(M.warnings(hour,25),['rain','gust']);
  const day=M.days(forecast,25,Date.parse('2026-10-23T10:00Z'))[0];
  assert.ok(day.windows.every(win=>win.end<=hour.time||win.start>=hour.time+3600));
  for(const key of ['precipitation','precipitation_probability','wind_gusts_10m'])assert.equal(forecast.hours.at(-1)[key],null);
});

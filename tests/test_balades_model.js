const test=require('node:test'),assert=require('node:assert/strict');
const M=require('../balades-model.js');
const track=(over={})=>({id:'walk-1',name:'Parc de Saint-Cloud',date:'2026-10-21',dogs:['billie'],points:[[48.8402,2.2190,1792900000],[48.8411,2.2205,1792900060]],durationSec:60,source:'record',walkRefs:[],spots:[],...over});
const spot=(over={})=>({id:'s1',type:'tolere',lat:48.84,lon:2.22,note:'Chiens calmes sans laisse tôt le matin',rule:'Laisse obligatoire dans tout le parc',noted:'2026-10-20',...over});

test('aggregate UTF-8 capacity includes spot text, below all count limits',()=>{
  const spots=Array.from({length:200},(_,i)=>spot({id:'s'+i,note:'é'.repeat(500),rule:'é'.repeat(500)}));
  const value={version:1,tracks:Array.from({length:80},(_,i)=>track({id:'t'+i,spots}))};
  assert.ok(JSON.stringify(value).length<30*1024*1024);
  assert.ok(Buffer.byteLength(JSON.stringify(value))>30*1024*1024);
  assert.throws(()=>M.validate(value),{code:'tooLarge'});
  value.tracks.length=40;
  assert.doesNotThrow(()=>M.validate(value));
});

test('validation keeps limits, spot rules and one track per walk',()=>{
  assert.doesNotThrow(()=>M.validate({version:1,tracks:[track({spots:[spot()],walkRefs:[{date:'2026-10-21',dogId:'billie'}]})]}));
  const bad=[
    {extra:true},{points:[[48,2,null]]},{points:[[91,2,null],[48,2,null]]},{name:' '},{date:'2026-02-30'},
    {spots:[spot({type:'pause'})]},{spots:[spot({note:'x'.repeat(501)})]},{spots:[spot(),spot()]},{spots:[spot({type:'parc'})]},
    {walkRefs:[{date:'2026-10-21',dogId:'charlie'}]},{dogs:['billie','billie']},{durationSec:-1},{source:'strava'},
    {points:Array.from({length:M.LIMITS.points+1},(_,i)=>[48+i*1e-5,2,null])},{spots:Array.from({length:201},(_,i)=>spot({id:'s'+i,type:'pause',rule:''}))}
  ];
  for(const patch of bad)assert.throws(()=>M.validate({version:1,tracks:[track(patch)]}),M.BaladeError,JSON.stringify(patch).slice(0,80));
  const ref={walkRefs:[{date:'2026-10-21',dogId:'billie'}]};
  assert.throws(()=>M.validate({version:1,tracks:[track(ref),track({id:'walk-2',...ref})]}));
  assert.throws(()=>M.validate({version:1,tracks:Array.from({length:501},(_,i)=>track({id:'t'+i}))}));
});

test('recorder drops imprecise fixes and moves under four metres',()=>{
  const last=[48.84,2.22,null];
  assert.equal(M.accept({lat:48.8401,lon:2.22,accuracy:36},last),false);
  assert.equal(M.accept({lat:48.84002,lon:2.22,accuracy:5},last),false);
  assert.equal(M.accept({lat:48.8401,lon:2.22,accuracy:35},last),true);
  assert.ok(Math.abs(M.distance([[48.84,2.22,null],[48.8409,2.22,null]])-100)<1);
});

test('GPX export and import round trip keeps points and spots',()=>{
  const original=track({spots:[spot(),spot({id:'s2',type:'danger',note:'Route <rapide> & vélos',rule:''})]});
  const back=M.parseGpx(M.toGpx(original,t=>t.toUpperCase()),'2026-10-22');
  assert.equal(back.name,original.name);
  assert.deepEqual(back.points,original.points);
  assert.deepEqual(back.spots.map(({id,...s})=>s),original.spots.map(({id,...s})=>s));
});

test('foreign GPX: route points, waypoints as pause spots, malformed files rejected',()=>{
  const gpx=`<?xml version="1.0"?><gpx:gpx xmlns:gpx="http://www.topografix.com/GPX/1/1"><gpx:wpt lat="48.1" lon="2.1"><gpx:name>Lac &amp; banc</gpx:name></gpx:wpt><gpx:rte><gpx:name>Boucle</gpx:name><gpx:rtept lat="48.1" lon="2.1"/><gpx:rtept lat='48.2' lon='2.2'/></gpx:rte></gpx:gpx>`;
  const parsed=M.parseGpx(gpx,'2026-10-22');
  assert.equal(parsed.name,'Boucle');
  assert.deepEqual(parsed.points,[[48.1,2.1,null],[48.2,2.2,null]]);
  assert.deepEqual(parsed.spots,[{id:'spot-1',type:'pause',lat:48.1,lon:2.1,note:'Lac & banc',rule:'',noted:'2026-10-22'}]);
  const code=src=>{try{M.parseGpx(src,'2026-10-22');}catch(e){return e.code;}};
  assert.equal(code('<gpx><trk><trkseg><trkpt lat="1" lon="2"></trkseg></trk></gpx>'),'xml');
  assert.equal(code('<!DOCTYPE gpx [<!ENTITY a "b">]><gpx/>'),'xml');
  assert.equal(code('<kml/>'),'notGpx');
  assert.equal(code('<gpx><trk><trkseg><trkpt lat="1" lon="2"/></trkseg></trk></gpx>'),'noTrack');
  assert.equal(code('<gpx><trk><trkseg><trkpt lat="x" lon="2"/><trkpt lat="1" lon="2"/></trkseg></trk></gpx>'),'point');
  assert.equal(code('<gpx>'+'<trkpt lat="1" lon="2"/>'.repeat(M.LIMITS.points+1)+'</gpx>'),'tooManyPoints');
  assert.equal(code('<gpx>'+' '.repeat(M.LIMITS.fileBytes)+'</gpx>'),'tooBig');
});

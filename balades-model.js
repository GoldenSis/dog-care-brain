/* Balades: walk tracks with spots. One validator for browser and Node; GPX in and out without a DOM. */
(function(root,factory){const m=factory();if(typeof module==='object'&&module.exports)module.exports=m;else root.BaladesModel=m;}(typeof window==='undefined'?globalThis:window,()=>{
  'use strict';
  const LIMITS={fileBytes:8*1024*1024,snapshotBytes:30*1024*1024,points:20000,spots:200,tracks:500,totalPoints:600000,dogs:50,walkRefs:50,name:120,note:500,maxAccuracy:35,minMove:4};
  const TYPES=['pause','danger','interdit','laisse','tolere'];
  class BaladeError extends Error{constructor(code){super(code);this.code=code;}}
  const fail=code=>{throw new BaladeError(code);};
  const check=ok=>{if(!ok)fail('invalid');};
  const empty=()=>({version:1,tracks:[]});
  const fields=(v,keys)=>check(v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join(' ')===keys.split(' ').sort().join(' '));
  const text=(v,n,required=false)=>typeof v==='string'&&[...v].length<=n&&(!required||v.trim().length>0)&&!/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(v)&&![...v].some(c=>c.codePointAt(0)>=0xd800&&c.codePointAt(0)<=0xdfff);
  const ident=v=>typeof v==='string'&&/^[A-Za-z0-9][A-Za-z0-9_-]{0,80}(?![\s\S])/.test(v);
  const date=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&v>='0001-01-01'&&Number.isFinite(Date.parse(v+'T00:00:00Z'))&&new Date(v+'T00:00:00Z').toISOString().slice(0,10)===v;
  const lat=v=>typeof v==='number'&&Number.isFinite(v)&&v>=-90&&v<=90;
  const lon=v=>typeof v==='number'&&Number.isFinite(v)&&v>=-180&&v<=180;
  const stamp=v=>v===null||(Number.isSafeInteger(v)&&v>=0&&v<=4102444800);
  // Removes what the validator refuses, so text read from a foreign file can be stored.
  const clean=(v,n)=>[...String(v||'').replace(/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/g,'')].filter(c=>c.codePointAt(0)<0xd800||c.codePointAt(0)>0xdfff).slice(0,n).join('').trim();
  const round=v=>Math.round(v*1e6)/1e6;
  function validate(value){
    fields(value,'version tracks');check(value.version===1&&Array.isArray(value.tracks)&&value.tracks.length<=LIMITS.tracks);
    const ids=new Set(),walks=new Set();let total=0;
    for(const t of value.tracks){
      fields(t,'id name date dogs points durationSec source walkRefs spots');
      check(ident(t.id)&&!ids.has(t.id));ids.add(t.id);
      check(text(t.name,LIMITS.name,true)&&date(t.date)&&['record','import'].includes(t.source));
      check(t.durationSec===null||(Number.isSafeInteger(t.durationSec)&&t.durationSec>=0&&t.durationSec<=604800));
      check(Array.isArray(t.dogs)&&t.dogs.length<=LIMITS.dogs&&t.dogs.every(ident)&&new Set(t.dogs).size===t.dogs.length);
      check(Array.isArray(t.points)&&t.points.length>=2&&t.points.length<=LIMITS.points);
      for(const p of t.points)check(Array.isArray(p)&&p.length===3&&lat(p[0])&&lon(p[1])&&stamp(p[2]));
      total+=t.points.length;check(total<=LIMITS.totalPoints);
      check(Array.isArray(t.walkRefs)&&t.walkRefs.length<=LIMITS.walkRefs);
      for(const r of t.walkRefs){fields(r,'date dogId');check(date(r.date)&&ident(r.dogId)&&t.dogs.includes(r.dogId));const key=r.date+'|'+r.dogId;check(!walks.has(key));walks.add(key);}
      check(Array.isArray(t.spots)&&t.spots.length<=LIMITS.spots);
      const spotIds=new Set();
      for(const s of t.spots){
        fields(s,'id type lat lon note rule noted');check(ident(s.id)&&!spotIds.has(s.id));spotIds.add(s.id);
        check(TYPES.includes(s.type)&&lat(s.lat)&&lon(s.lon)&&text(s.note,LIMITS.note)&&text(s.rule,LIMITS.note)&&(s.type==='tolere'||s.rule==='')&&date(s.noted));
      }
    }
    if(new TextEncoder().encode(JSON.stringify(value)).length>LIMITS.snapshotBytes)fail('tooLarge');
    return value;
  }
  function meters(a,b){
    const r=Math.PI/180,dLat=(b[0]-a[0])*r,dLon=(b[1]-a[1])*r;
    const h=Math.sin(dLat/2)**2+Math.cos(a[0]*r)*Math.cos(b[0]*r)*Math.sin(dLon/2)**2;
    return 2*6371008.8*Math.asin(Math.min(1,Math.sqrt(h)));
  }
  const distance=points=>points.reduce((sum,p,i)=>i?sum+meters(points[i-1],p):0,0);
  // A recorded fix is kept only when it is precise enough and actually moved.
  function accept(fix,last){
    if(!fix||!lat(fix.lat)||!lon(fix.lon)||!(fix.accuracy<=LIMITS.maxAccuracy))return false;
    return !last||meters(last,[fix.lat,fix.lon])>=LIMITS.minMove;
  }
  const timeSpan=points=>{const times=points.map(p=>p[2]).filter(t=>t!==null);return times.length>1?Math.max(0,Math.min(604800,times[times.length-1]-times[0])):null;};

  // Minimal XML reader: elements, attributes, text, CDATA, comments. A DOCTYPE,
  // an unknown entity or a mismatched tag rejects the file instead of guessing.
  function parseXml(src){
    if(/<!DOCTYPE/i.test(src))fail('xml');
    const top={name:'#root',attrs:{},children:[],text:''},stack=[top];
    const re=/<!--[\s\S]*?-->|<!\[CDATA\[([\s\S]*?)\]\]>|<\?[\s\S]*?\?>|<\/([^\s>]+)\s*>|<([^\s/>!?]+)((?:\s+[^\s=/>]+\s*=\s*(?:"[^"]*"|'[^']*'))*)\s*(\/?)>|([^<]+)|([\s\S])/g;
    const local=n=>n.slice(n.indexOf(':')+1);
    const entity=s=>s.replace(/&(#x[0-9a-f]+|#\d+|[a-z]+);?/gi,(m,e)=>{
      if(!m.endsWith(';'))fail('xml');
      const named={lt:'<',gt:'>',amp:'&',quot:'"',apos:"'"};
      if(e[0]==='#'){const n=e[1]==='x'||e[1]==='X'?parseInt(e.slice(2),16):parseInt(e.slice(1),10);if(!(n>0&&n<=0x10ffff))fail('xml');return String.fromCodePoint(n);}
      if(!Object.hasOwn(named,e))fail('xml');return named[e];
    });
    let m;
    while((m=re.exec(src))){
      const node=stack[stack.length-1];
      if(m[7]!==undefined)fail('xml');
      if(m[1]!==undefined)node.text+=m[1];
      else if(m[2]!==undefined){if(stack.length<2||node.raw!==m[2])fail('xml');stack.pop();}
      else if(m[3]!==undefined){
        const attrs={};for(const a of m[4].matchAll(/([^\s=]+)\s*=\s*(?:"([^"]*)"|'([^']*)')/g))attrs[local(a[1])]=entity(a[2]??a[3]);
        const child={name:local(m[3]),raw:m[3],attrs,children:[],text:''};node.children.push(child);
        if(!m[5])stack.push(child);
      }
      else if(m[6]!==undefined){if(stack.length<2&&m[6].trim())fail('xml');node.text+=entity(m[6]);}
    }
    if(stack.length!==1||top.children.length!==1)fail('xml');
    return top.children[0];
  }
  const kids=(n,name)=>n.children.filter(c=>c.name===name);
  const all=(n,name,out=[])=>{for(const c of n.children){if(c.name===name)out.push(c);all(c,name,out);}return out;};
  const child=(n,name)=>(kids(n,name)[0]?.text||'').trim();
  function coords(n){const a=Number(n.attrs.lat),b=Number(n.attrs.lon);if(!n.attrs.lat||!n.attrs.lon||!lat(a)||!lon(b))fail('point');return [round(a),round(b)];}
  function seconds(v){const t=Date.parse(v);return v&&Number.isFinite(t)&&t>=0&&t<=4102444800000?Math.floor(t/1000):null;}
  // GPX text → {name, points, spots}. Track points first, route points otherwise; waypoints become spots.
  function parseGpx(src,today){
    if(typeof src!=='string')fail('xml');
    if(new TextEncoder().encode(src).length>LIMITS.fileBytes)fail('tooBig');
    const gpx=parseXml(src);if(gpx.name!=='gpx')fail('notGpx');
    let nodes=all(gpx,'trkpt');if(!nodes.length)nodes=all(gpx,'rtept');
    if(nodes.length>LIMITS.points)fail('tooManyPoints');
    const points=nodes.map(n=>[...coords(n),seconds(child(n,'time'))]);
    if(points.length<2)fail('noTrack');
    const wpts=kids(gpx,'wpt');if(wpts.length>LIMITS.spots)fail('tooManySpots');
    const spots=wpts.map((n,i)=>{
      const [a,b]=coords(n),kind=child(n,'type').toLowerCase(),ours=TYPES.includes(kind),stampValue=seconds(child(n,'time'));
      const noted=stampValue===null?today:new Date(stampValue*1000).toISOString().slice(0,10);
      return {id:'spot-'+(i+1),type:ours?kind:'pause',lat:a,lon:b,note:clean(ours?child(n,'desc'):(child(n,'name')||child(n,'desc')),LIMITS.note),rule:ours&&kind==='tolere'?clean(child(n,'cmt'),LIMITS.note):'',noted:date(noted)?noted:today};
    });
    const meta=kids(gpx,'metadata')[0],trk=kids(gpx,'trk')[0],rte=kids(gpx,'rte')[0];
    const name=clean((meta&&child(meta,'name'))||(trk&&child(trk,'name'))||(rte&&child(rte,'name')),LIMITS.name);
    return {name,points,spots};
  }
  const xml=v=>String(v).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&apos;'}[c]));
  const iso=t=>new Date(t*1000).toISOString().replace('.000Z','Z');
  function toGpx(track,label=type=>type){
    const wpt=s=>`  <wpt lat="${s.lat}" lon="${s.lon}"><time>${s.noted}T12:00:00Z</time><name>${xml(label(s.type))}</name>${s.rule?`<cmt>${xml(s.rule)}</cmt>`:''}${s.note?`<desc>${xml(s.note)}</desc>`:''}<type>${s.type}</type></wpt>\n`;
    const pt=p=>`      <trkpt lat="${p[0]}" lon="${p[1]}">${p[2]===null?'':`<time>${iso(p[2])}</time>`}</trkpt>\n`;
    return `<?xml version="1.0" encoding="UTF-8"?>\n<gpx version="1.1" creator="Le Bus des Toutous" xmlns="http://www.topografix.com/GPX/1/1">\n  <metadata><name>${xml(track.name)}</name></metadata>\n${track.spots.map(wpt).join('')}  <trk><name>${xml(track.name)}</name><trkseg>\n${track.points.map(pt).join('')}  </trkseg></trk>\n</gpx>\n`;
  }
  return {LIMITS,TYPES,BaladeError,empty,validate,distance,meters,accept,timeSpan,parseGpx,toGpx,clean,date,ident};
}));

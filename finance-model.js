/* Accounting preparation: explicit drafts, immutable issued invoices and sources. */
(function(root,factory){const m=factory();if(typeof module==='object'&&module.exports)module.exports=m;else root.FinanceModel=m;}(typeof window==='undefined'?globalThis:window,()=>{
  'use strict';
  const kinds=['sale','purchase','expense','extra'], categories=['service','supplies','food','transport','health','equipment','insurance','other'];
  const empty=()=>({version:1,profile:{name:'',address:'',taxId:''},entries:[],documents:[]});
  const check=(ok)=>{if(!ok)throw Error('Invalid accounting record');};
  const fields=(v,keys)=>check(v&&typeof v==='object'&&!Array.isArray(v)&&Object.keys(v).sort().join(' ')===keys.split(' ').sort().join(' '));
  const text=(v,n,required=false)=>typeof v==='string'&&[...v].length<=n&&(!required||v.trim().length>0)&&!/[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]/.test(v)&&![...v].some(c=>c.codePointAt(0)>=0xd800&&c.codePointAt(0)<=0xdfff);
  const ident=v=>typeof v==='string'&&/^[A-Za-z0-9][A-Za-z0-9_-]{0,80}(?![\s\S])/.test(v);
  const date=v=>typeof v==='string'&&/^\d{4}-\d{2}-\d{2}$/.test(v)&&v>='0001-01-01'&&Number.isFinite(Date.parse(v+'T00:00:00Z'))&&new Date(v+'T00:00:00Z').toISOString().slice(0,10)===v;
  const minor=v=>Number.isSafeInteger(v)&&v>=0&&v<=100000000;
  function collection(items,max=5000){check(Array.isArray(items)&&items.length<=max);const ids=new Set();for(const x of items){check(x&&ident(x.id)&&!ids.has(x.id));ids.add(x.id);}return ids;}
  function parseMinor(v){if(!v.trim())return null;check(/^\d+(?:[.,]\d{1,2})?$/.test(v.trim()));const [a,b='']=v.trim().split(/[.,]/);const n=Number(BigInt(a)*100n+BigInt(b.padEnd(2,'0')));check(minor(n));return n;}
  function total(e){if(!e.lines.length||e.lines.some(l=>l.unitMinor===null))return null;const t=e.lines.reduce((sum,l)=>sum+l.quantity*l.unitMinor,0);check(Number.isSafeInteger(t)&&t<=1000000000000);return t;}
  const paid=e=>e.payments.reduce((sum,p)=>sum+p.amountMinor,0);
  const incoming=kind=>['sale','extra'].includes(kind);
  function draft(id,kind='purchase'){return {id,kind,status:'draft',number:'',date:'',due:'',party:'',address:'',issuer:'',issuerAddress:'',taxId:'',currency:'',category:'other',lines:[{description:'',quantity:1,unitMinor:null,bookingId:''}],vatMinor:null,note:'',sourceId:'',region:null,raw:'',payments:[],cancelReason:''};}
  function validate(value,previous=null){
    fields(value,'version profile entries documents');check(value.version===1);fields(value.profile,'name address taxId');
    check(text(value.profile.name,160)&&text(value.profile.address,1000)&&text(value.profile.taxId,120));
    const docs=collection(value.documents);collection(value.entries);
    const hashes=new Set(),numbers=new Set(),regions=new Set();
    for(const d of value.documents){fields(d,'id name type size sha256');check(/^[a-f0-9]{64}$/.test(d.sha256)&&d.id===d.sha256&&!hashes.has(d.sha256)&&text(d.name,180,true)&&['image/jpeg','image/png','application/pdf'].includes(d.type)&&Number.isSafeInteger(d.size)&&d.size>0&&d.size<=5*1024*1024);hashes.add(d.sha256);}
    for(const e of value.entries){
      fields(e,'id kind status number date due party address issuer issuerAddress taxId currency category lines vatMinor note sourceId region raw payments cancelReason');
      check(kinds.includes(e.kind)&&['draft','confirmed','cancelled'].includes(e.status)&&categories.includes(e.category));
      for(const k of ['number','party','issuer','taxId'])check(text(e[k],160));
      for(const k of ['address','issuerAddress','note','cancelReason'])check(text(e[k],1000));
      check(text(e.raw,20000)&&text(e.currency,3)&&(e.currency===''||/^[A-Z]{3}$/.test(e.currency))&&(e.date===''||date(e.date))&&(e.due===''||date(e.due))&&(!e.due||!e.date||e.due>=e.date));
      check(e.sourceId===''||docs.has(e.sourceId));
      if(e.region!==null){fields(e.region,'page x y width height');check(e.sourceId&&Number.isSafeInteger(e.region.page)&&e.region.page>=1&&e.region.page<=100);for(const k of ['x','y','width','height'])check(typeof e.region[k]==='number'&&Number.isFinite(e.region[k])&&e.region[k]>=0&&e.region[k]<=1);check(e.region.width>0&&e.region.height>0&&e.region.x+e.region.width<=1.000001&&e.region.y+e.region.height<=1.000001);}
      check(Array.isArray(e.lines)&&e.lines.length>=1&&e.lines.length<=100);
      for(const l of e.lines){fields(l,'description quantity unitMinor bookingId');check(text(l.description,500)&&Number.isSafeInteger(l.quantity)&&l.quantity>=1&&l.quantity<=10000&&(l.unitMinor===null||minor(l.unitMinor))&&(l.bookingId===''||ident(l.bookingId)));}
      const amount=total(e);check(e.vatMinor===null||(minor(e.vatMinor)&&(amount===null||e.vatMinor<=amount)));
      collection(e.payments,100);for(const p of e.payments){fields(p,'id date amountMinor note');check(date(p.date)&&minor(p.amountMinor)&&p.amountMinor>0&&text(p.note,500));}
      check(!e.payments.length||(e.status==='confirmed'&&amount!==null&&paid(e)<=amount));
      if(e.status==='confirmed'){check(date(e.date)&&e.party.trim()&&e.currency&&amount!==null&&e.lines.every(l=>l.description.trim()));if(e.kind==='sale')check(e.number.trim()&&e.address.trim()&&e.issuer.trim()&&e.issuerAddress.trim());}
      if(e.status==='cancelled')check(e.cancelReason.trim()&&!e.payments.length);
      if(e.kind==='sale'&&e.status!=='draft'&&e.number.trim()){check(!numbers.has(e.number.trim()));numbers.add(e.number.trim());}
      if(e.sourceId&&e.region&&e.status!=='cancelled'){const key=e.sourceId+JSON.stringify(['page','x','y','width','height'].map(k=>e.region[k]));check(!regions.has(key));regions.add(key);}
    }
    if(previous){
      const documents=new Map(value.documents.map(d=>[d.id,JSON.stringify(d)]));
      for(const old of previous.documents)check(documents.get(old.id)===JSON.stringify(old));
      for(const old of previous.entries){const e=value.entries.find(x=>x.id===old.id);check(e);if(old.payments.length)check(e.currency===old.currency&&incoming(e.kind)===incoming(old.kind));if(old.kind==='sale'&&old.status!=='draft'){
        for(const key of Object.keys(old).filter(k=>!['payments','status','cancelReason'].includes(k)))check(JSON.stringify(old[key])===JSON.stringify(e[key]));
        check(e.status===old.status||(old.status==='confirmed'&&e.status==='cancelled'));if(old.status==='cancelled')check(e.cancelReason===old.cancelReason);
      }
      for(const payment of old.payments)check(e.payments.some(p=>JSON.stringify(p)===JSON.stringify(payment)));
      }
    }
    return true;
  }
  /* Conservative OCR proposals. No amount/date/category becomes confirmed here. */
  function propose(raw){
    const result={date:'',party:'',number:'',currency:'',amount:null,category:'other'};
    const lines=raw.split(/\r?\n/).map(x=>x.trim()).filter(Boolean);
    result.party=lines[0]?.slice(0,160)||'';
    const currencies=[...new Set(raw.match(/\b(?:CHF|EUR|GBP|USD)\b/g)||[])];if(currencies.length===1)result.currency=currencies[0];
    const dates=[...raw.matchAll(/\b(\d{2})[./](\d{2})[./](\d{4})\b/g)].map(m=>`${m[3]}-${m[2]}-${m[1]}`).filter(date);
    const iso=[...raw.matchAll(/\b\d{4}-\d{2}-\d{2}\b/g)].map(m=>m[0]).filter(date);if(new Set([...dates,...iso]).size===1)result.date=[...dates,...iso][0];
    const ref=raw.match(/(?:facture|invoice|rechnung|fattura|factura)\s*(?:n[°o.]?|#|nr\.?)?\s*[:#]?\s*([A-Z0-9][A-Z0-9/-]{2,40})\b/i);if(ref)result.number=ref[1];
    const totals=lines.filter(l=>/\b(total|ttc|gesamt|totale|importe)\b/i.test(l)&&!/sous|sub|subtotal|hors|ht\b|tax/i.test(l)).map(l=>{const m=l.match(/^(?:total(?:\s+ttc)?|ttc|gesamt(?:betrag)?|totale|importe)\s*[:=]?\s*(?:CHF|EUR|GBP|USD|€)?\s*([0-9]+[.,][0-9]{2})(?:\s*(?:CHF|EUR|GBP|USD|€))?\s*$/i);try{return m?parseMinor(m[1]):null;}catch{return null;}}).filter(x=>x!==null);
    if(new Set(totals).size===1)result.amount=totals[0];
    const rules={food:/croquettes|alimentation|kibble|pet food/i,transport:/carburant|essence|fuel|parking|péage/i,health:/vétérin|veterin|vaccin/i,insurance:/assurance|insurance/i};
    const found=Object.keys(rules).filter(k=>rules[k].test(raw));if(found.length===1)result.category=found[0];
    return result;
  }
  return {empty,draft,validate,total,paid,incoming,parseMinor,propose,kinds,categories,date};
}));

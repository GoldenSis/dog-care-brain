/* Balades storage: static IndexedDB or the account API, plus the in-progress recording on this device. */
(function(w){
  'use strict';
  const M=w.BaladesModel, NAME='dogcare-balades-v1';
  let db=null, data=M.empty(), baseline=null, revision=0, version=0, scope='static', failed=true, stale=false, loaded=null;
  const request=r=>new Promise((resolve,reject)=>{r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
  const complete=t=>new Promise((resolve,reject)=>{t.oncomplete=()=>resolve(true);t.onabort=t.onerror=()=>reject(t.error||Error('Storage failed'));});
  async function open(){
    if(db)return db;
    const o=indexedDB.open(NAME,1);o.onupgradeneeded=()=>{o.result.createObjectStore('state');o.result.createObjectStore('drafts');};
    return db=await request(o);
  }
  async function read(){
    try{
      if(w.DogCareAPI){
        const r=await w.DogCareAPI.balades();if(!r.ok)throw Error('Balades unavailable');
        M.validate(r.balades);data=r.balades;revision=r.revision;scope='account:'+r.businessId;
      }else{
        await open();const raw=await request(db.transaction('state').objectStore('state').get('current'));
        const candidate=raw?JSON.parse(raw):M.empty();M.validate(candidate);data=candidate;baseline=raw||null;
      }
      failed=false;stale=false;version++;return true;
    }catch{failed=true;return false;}
  }
  const load=()=>loaded||=read();
  const reload=()=>loaded=read();
  // Returns 'ok', 'conflict' (another tab or device saved first), 'invalid' or 'failed'.
  async function save(next){
    if(failed)return 'failed';
    if(stale)return 'conflict';
    try{M.validate(next);}catch{return 'invalid';}
    if(w.DogCareAPI){
      const r=await w.DogCareAPI.balades(next,revision);
      if(r.ok){data=r.balades;revision=r.revision;version++;return 'ok';}
      if(r.conflict){stale=true;return 'conflict';}
      return 'failed';
    }
    const text=JSON.stringify(next);
    try{
      const tx=db.transaction('state','readwrite'),done=complete(tx),store=tx.objectStore('state'),current=store.get('current');
      current.onsuccess=()=>{if((current.result||null)!==baseline){stale=true;tx.abort();return;}store.put(text,'current');};
      await done;
    }catch{return stale?'conflict':'failed';}
    data=structuredClone(next);baseline=text;version++;return 'ok';
  }
  // The draft stays in this browser, keyed by business (shared by its staff) or by static mode.
  async function draft(value,previous=null){
    const key=scope;
    try{
      await open();
      if(value===undefined)return await request(db.transaction('drafts').objectStore('drafts').get(key))||null;
      if(value!==null&&(!M.ident(value.id)||!M.ident(value.token)))return false;
      const tx=db.transaction('drafts','readwrite'),done=complete(tx),store=tx.objectStore('drafts'),read=store.get(key);let matched=false,found=null;
      read.onsuccess=()=>{
        const old=found=read.result||null;
        matched=old===null?previous===null:!!previous&&(old.id&&old.token?old.id===previous.id&&old.token===previous.token:JSON.stringify(old)===JSON.stringify(previous));
        if(!matched)return;
        if(value!==null&&old?.id&&old.id!==value.id){matched=false;return;}
        if(value===null)store.delete(key);else store.put(value,key);
      };
      await done;return matched?true:{conflict:true,draft:found};
    }catch{return value===undefined?null:false;}
  }
  w.BaladesStore={load,reload,save,draft,snapshot:()=>structuredClone(data),version:()=>version,unavailable:()=>failed};
})(window);

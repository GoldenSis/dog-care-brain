/* Balades storage: static IndexedDB or the account API, plus the in-progress recording on this device. */
(function(w){
  'use strict';
  const M=w.BaladesModel, NAME='dogcare-balades-v1';
  let db=null, data=M.empty(), baseline=null, revision=0, scope='static', failed=true, stale=false, loaded=null;
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
      failed=false;stale=false;return true;
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
      if(r.ok){data=r.balades;revision=r.revision;return 'ok';}
      if(r.conflict){stale=true;return 'conflict';}
      return 'failed';
    }
    const text=JSON.stringify(next);
    try{
      const tx=db.transaction('state','readwrite'),done=complete(tx),store=tx.objectStore('state'),current=store.get('current');
      current.onsuccess=()=>{if((current.result||null)!==baseline){stale=true;tx.abort();return;}store.put(text,'current');};
      await done;
    }catch{return stale?'conflict':'failed';}
    data=structuredClone(next);baseline=text;return 'ok';
  }
  // The recording draft never leaves this browser; it is keyed by account so a shared device keeps them apart.
  async function draft(value){
    try{
      await open();
      const tx=db.transaction('drafts',value===undefined?'readonly':'readwrite'),store=tx.objectStore('drafts');
      if(value===undefined)return await request(store.get(scope))||null;
      if(value===null)store.delete(scope);else store.put(value,scope);
      await complete(tx);return true;
    }catch{return value===undefined?null:false;}
  }
  w.BaladesStore={load,reload,save,draft,snapshot:()=>structuredClone(data),unavailable:()=>failed};
})(window);

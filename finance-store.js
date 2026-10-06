/* Browser originals and snapshot commit together; account mode uses existing revision guards. */
(function(w){
  'use strict';
  let db, baseline=null, data=FinanceModel.empty(), failed=false;
  const request=r=>new Promise((resolve,reject)=>{r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});
  const complete=t=>new Promise((resolve,reject)=>{t.oncomplete=()=>resolve(true);t.onabort=t.onerror=()=>reject(t.error||Error('Storage failed'));});
  async function load(){
    try{
      if(w.DogCareAPI)data=w.DogCareAPI.getFinance();
      else{
        const open=indexedDB.open('dogcare-finance-v1',1);open.onupgradeneeded=()=>{open.result.createObjectStore('state');open.result.createObjectStore('documents');};
        db=await request(open);const raw=await request(db.transaction('state').objectStore('state').get('current'));
        baseline=raw||null;data=raw?JSON.parse(raw):FinanceModel.empty();
      }
      FinanceModel.validate(data);return true;
    }catch{failed=true;return false;}
  }
  const snapshot=()=>structuredClone(data);
  const base64=async blob=>new Promise((resolve,reject)=>{const r=new FileReader();r.onload=()=>resolve(r.result.split(',')[1]);r.onerror=reject;r.readAsDataURL(blob);});
  async function save(next,files=new Map()){
    if(failed)return false;
    try{
      FinanceModel.validate(next,data);
      if(w.DogCareAPI){
        const uploads=[];for(const [id,blob] of files)uploads.push({id,data:await base64(blob)});
        if(!await w.DogCareAPI.saveFinance(next,uploads))return false;
        data=w.DogCareAPI.getFinance();return true;
      }
      const additions=next.documents.filter(d=>!data.documents.some(old=>old.id===d.id));
      if(additions.length!==files.size||additions.some(d=>!files.has(d.id)))return false;
      // One readwrite transaction serializes other tabs and preserves sources on failure.
      const tx=db.transaction(['state','documents'],'readwrite'), done=complete(tx), stateStore=tx.objectStore('state');
      const read=stateStore.get('current');let stale=false;
      read.onsuccess=()=>{if((read.result||null)!==baseline){stale=true;tx.abort();return;}
        for(const [id,blob] of files)tx.objectStore('documents').add(blob,id);
        stateStore.put(JSON.stringify(next),'current');};
      try{await done;}catch{if(stale)failed=true;return false;}
      data=structuredClone(next);baseline=JSON.stringify(next);return true;
    }catch{return false;}
  }
  async function document(id){
    if(failed||!data.documents.some(d=>d.id===id))return null;
    if(w.DogCareAPI)return w.DogCareAPI.getFinanceDocument(id);
    try{return await request(db.transaction('documents').objectStore('documents').get(id));}catch{return null;}
  }
  w.FinanceStore={load,snapshot,save,document,unavailable:()=>failed};
})(window);

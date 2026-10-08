/* Adapter behind window.DOGCARE_API (the API server injects "/api").
   Flag off (undefined/falsy) → no storage or network access from this file.
   Flag on → hydrate account state, optionally import dogcare-observations,
   dogcare-invites and dogcare-language once per business; daily records,
   experiences and accounting records/originals are excluded. Save through /api
   with a session cookie; browser copies stay intact. Observations/invites/daily
   records/experiences/accounting use full replacement snapshots; accounting
   writes retain existing records and commit new originals atomically. Language
   is per user, and care writes bind to the loaded business/revision.
   See README.md's Slice 1 API section for the request and recovery contracts. */
(function (w) {
  const base = w.DOGCARE_API;
  if (!base) return;

  const cache = {
    observations: null,
    dogs: [],
    invites: [],
    language: "fr",
    daily: null,
    knowledge: null,
    finance: null,
    media: {items:[],covers:{},branding:{hero:null,services:{}}},
    portal: {updates:[],requests:[],documents:[],members:[]},
  };

  function url(path) {
    return String(base).replace(/\/$/, "") + path;
  }

  function failed() {
    if (typeof w.showToast === "function") w.showToast(writeBlocked || "Not saved — check your connection and try again");
  }

  let hydrated = false;
  let sessionUser = null;
  let anonymous = false;
  let businessId = null;
  let revision = null;
  let writeBlocked = "";
  let loadError = "Could not load your account. Check your connection and reload.";
  let writes = Promise.resolve();
  const uploaded = new Map();
  const requestTimeout = 15000;

  async function req(path, opts) {
    const writing = opts && opts.method && opts.method !== "GET";
    if (writing) {
      if ((writeBlocked && path !== '/auth/logout') || businessId === null) { failed(); return { ok: false, status: 0, data: {} }; }
      opts = { ...opts, headers: { ...opts.headers, "X-DogCare-Business": String(businessId), "If-Match": `"${revision}"` } };
    }
    const controller = new AbortController();
    let timer;
    try {
      const timeout = new Promise((_, reject) => {
        timer = setTimeout(() => {
          reject(new Error("Request timed out"));
          controller.abort();
        }, requestTimeout);
      });
      const request = (async () => {
        const r = await fetch(url(path), { credentials: "include", ...opts, signal: controller.signal });
        const text = await r.text();
        return { r, data: text ? JSON.parse(text) : {} };
      })();
      const { r, data } = await Promise.race([request, timeout]);
      if (writing && (data.reload_required || r.status === 401)) {
        writeBlocked = "Not saved — your account or care records changed. Copy your draft, then reload before saving.";
      }
      if (writing && r.ok && path !== "/blobs" && path !== "/auth/logout") {
        if (data.business_id !== businessId || !Number.isSafeInteger(data.revision)) {
          failed();
          return { ok: false, status: r.status, data: {} };
        }
        revision = data.revision;
      }
      if (!r.ok && writing) failed();
      return { ok: r.ok, status: r.status, data };
    } catch {
      if (writing) failed();
      return { ok: false, status: 0, data: {} };
    } finally {
      clearTimeout(timer);
    }
  }

  async function putJson(path, body) {
    return req(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  async function postJson(path, body) {
    return req(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  }

  async function uploadDataUrl(dataUrl) {
    if (uploaded.has(dataUrl)) return uploaded.get(dataUrl);
    const m = /^data:([^,]+);base64,([a-z0-9+/=\s]+)$/i.exec(dataUrl || "");
    if (!m) { failed(); return null; }
    const res = await postJson("/blobs", { type: m[1], data: m[2] });
    if (!res.ok || !res.data.ref) return null;
    const refUrl = url("/blobs/" + res.data.ref);
    uploaded.set(dataUrl, refUrl);
    return refUrl;
  }

  function reconcileAudio(observations) {
    for (const items of Object.values(observations || {})) {
      for (const item of items) {
        const src = item.audio && item.audio.url;
        if (uploaded.has(src)) item.audio.url = uploaded.get(src);
      }
    }
  }

  async function extractAudio(observations, original) {
    for (const items of Object.values(observations || {})) {
      for (const item of items) {
        const src = item.audio && item.audio.url;
        if (src && src.startsWith("data:")) {
          const refUrl = await uploadDataUrl(src);
          if (!refUrl) return false;
          item.audio.url = refUrl;
          if (original) reconcileAudio(original);
        }
      }
    }
    return true;
  }

  function acceptState(data) {
    if (!data.ok || !data.observations || typeof data.observations !== "object" ||
        Array.isArray(data.observations) || !Array.isArray(data.invites) ||
        !Number.isSafeInteger(data.business_id) || !Number.isSafeInteger(data.revision) ||
        (businessId !== null && data.business_id !== businessId)) return false;
    sessionUser = {email:data.email, role:data.role || "owner"};
    businessId = data.business_id;
    revision = data.revision;
    cache.observations = data.observations;
    cache.dogs = data.dogs || [];
    cache.invites = data.invites;
    cache.language = data.language || "en";
    cache.daily = data.daily ?? null;
    cache.knowledge = data.knowledge || {version:1,experiences:[]};
    cache.finance = data.finance ?? null;
    cache.media = data.media || {items:[],covers:{},branding:{hero:null,services:{}}};
    cache.portal = data.portal || {updates:[],requests:[],documents:[],members:[]};
    return true;
  }

  const ready = (async function hydrate() {
    const identity = await req("/auth/me");
    if (!identity.ok) return false;
    if (!identity.data.ok) { anonymous = true; return false; }
    const state = await req("/state");
    if (state.status === 401) {
      loadError = "Open your sign-in link in this browser to access your account. If the link has expired or was already used, request a new one from the person who gave you access.";
      return false;
    }
    if (!state.ok || !acceptState(state.data)) return false;
    const marker = "dogcare-imported:" + state.data.business_id;
    if (sessionUser.role === "owner" && !state.data.imported && !w.localStorage.getItem(marker)) {
      const payload = {};
      for (const key of ["observations", "invites", "language"]) {
        const raw = w.localStorage.getItem("dogcare-" + key);
        if (raw !== null) payload[key] = key === "language" ? raw : JSON.parse(raw);
      }
      if (Object.keys(payload).length) {
        loadError = "Your browser records could not be imported. They are still here; reload to retry.";
        const recordings = Object.values(payload.observations || {}).flat().some(item => item.audio?.url?.startsWith("data:"));
        if (recordings && !w.confirm("Existing recordings will move to your business’s own account store on the server it runs, accessible only to signed-in members of your business, never to a third party.")) {
          loadError = "Recording import paused. Your browser records are still here; reload to continue.";
          return false;
        }
        if (!await extractAudio(payload.observations)) return false;
        const result = await postJson("/import", payload);
        if (!result.ok || !acceptState(result.data)) return false;
        if (!result.data.skipped) {
          try { w.localStorage.setItem(marker, "1"); } catch {}
        }
      }
    }
    hydrated = true;
    return true;
  })().catch(() => false);

  function enqueue(save) {
    if (!hydrated) { failed(); return Promise.resolve(false); }
    writes = writes.then(() => {
      if (writeBlocked) { failed(); return false; }
      return save();
    }).catch(() => { failed(); return false; });
    return writes;
  }

  function acceptMedia(result, expectedBusiness) {
    if (!result?.ok || !Array.isArray(result.media?.items)) throw Error(result?.error || "Le média n’a pas été enregistré. Réessayez.");
    if (businessId !== expectedBusiness || result.business_id !== expectedBusiness) throw Error("Le compte actif a changé. Rechargez votre espace avant de réessayer.");
    cache.media = result.media;
    return JSON.parse(JSON.stringify(cache.media));
  }

  async function mediaRequest(action, payload) {
    if (!hydrated || businessId === null) throw Error("Rechargez votre espace avant de réessayer.");
    const expectedBusiness = businessId;
    const controller = new AbortController(), timer = setTimeout(() => controller.abort(), requestTimeout);
    try {
      const response = await fetch(url('/media' + (action ? '/' + action : '')), {
        credentials:'include', signal:controller.signal,
        headers:{'X-DogCare-Business':String(expectedBusiness),...(action ? {'Content-Type':'application/json'} : {})},
        ...(action ? {method:'POST',body:JSON.stringify(payload)} : {})
      });
      const result = await response.json();
      if (!response.ok) throw Error(result.error || "Le média n’a pas été enregistré. Réessayez.");
      return acceptMedia(result, expectedBusiness);
    } catch (error) {
      if (error.name === 'AbortError' || error instanceof TypeError) throw Error("Connexion interrompue. Rechargez l’album avant de réessayer.");
      throw error;
    } finally { clearTimeout(timer); }
  }

  function mediaType(file) {
    if (file.type && file.type !== 'application/octet-stream') return file.type;
    const extension = String(file.name || '').split('.').pop().toLowerCase();
    const types = {jpg:'image/jpeg',jpeg:'image/jpeg',png:'image/png',webp:'image/webp',heic:'image/heic',heif:'image/heif',
      mp4:'video/mp4',mov:'video/quicktime',webm:'video/webm'};
    return Object.hasOwn(types, extension) ? types[extension] : 'application/octet-stream';
  }

  // Await ready's boolean before using cached getters or saving. Queued care and
  // portal saves resolve to booleans in call order; whenSaved waits for that queue.
  // Media operations run separately, return snapshots/upload results and reject
  // on failure; see docs/media.md. Observation saves reconcile uploaded data URLs
  // into the supplied objects.
  w.DogCareAPI = {
    ready,
    isAnonymous() { return anonymous; },
    getUser() { return sessionUser && {...sessionUser}; },
    getLoadError() { return loadError; },
    getMedia() { return JSON.parse(JSON.stringify(cache.media)); },
    mediaType,
    reloadMedia() { return mediaRequest(); },
    saveMedia(action, payload) { return mediaRequest(action, payload); },
    uploadMedia(file, target, progress) {
      return new Promise((resolve, reject) => {
        if (!hydrated || businessId === null) { reject(Error("Rechargez votre espace avant de réessayer.")); return; }
        const expectedBusiness = businessId;
        const xhr = new XMLHttpRequest();
        xhr.open('POST', url('/media/upload?' + new URLSearchParams(target)));
        xhr.withCredentials = true;
        xhr.timeout = 180000;
        xhr.setRequestHeader('X-DogCare-Business', String(expectedBusiness));
        xhr.setRequestHeader('X-DogCare-Filename', encodeURIComponent(file.name));
        xhr.setRequestHeader('Content-Type', mediaType(file));
        xhr.upload.onprogress = event => { if (event.lengthComputable) progress?.(Math.round(event.loaded / event.total * 100)); };
        xhr.onload = () => {
          try {
            const result = JSON.parse(xhr.responseText);
            if (xhr.status < 200 || xhr.status >= 300) throw Error(result.error || "Le fichier n’a pas été ajouté.");
            if (typeof result.uploadedId !== 'string' || !result.media?.items?.some(item => item.id === result.uploadedId)) throw Error("Le fichier ajouté n’a pas été identifié. Rechargez l’album avant de réessayer.");
            resolve({media:acceptMedia(result, expectedBusiness), uploadedId:result.uploadedId});
          } catch (error) { reject(error); }
        };
        xhr.onerror = xhr.ontimeout = xhr.onabort = () => reject(Error("Transfert interrompu. Rechargez l’album avant de réessayer."));
        xhr.send(file);
      });
    },
    getPortal() { return JSON.parse(JSON.stringify(cache.portal)); },
    savePortal(action, payload) {
      const snapshot = JSON.parse(JSON.stringify(payload));
      return enqueue(async () => {
        const result = await postJson("/portal/" + action, snapshot);
        return result.ok && acceptState(result.data);
      });
    },
    async logout() {
      const result = await req('/auth/logout', {method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
      if(result.ok) w.location.reload();
      return result.ok;
    },
    whenSaved() { return writes; },
    getObservations() {
      return cache.observations || {};
    },
    getDogs() { return JSON.parse(JSON.stringify(cache.dogs)); },
    getInvites() {
      return cache.invites || [];
    },
    getLanguage() {
      return cache.language || "en";
    },
    getFinance() { return JSON.parse(JSON.stringify(cache.finance)); },
    reloadFinance() {
      return enqueue(async()=>{
        const result=await req('/state');
        if(!result.ok || !result.data.ok || result.data.business_id!==businessId || result.data.revision!==revision || !result.data.finance)return false;
        cache.finance=result.data.finance;return true;
      });
    },
    saveFinance(finance, uploads=[]) {
      if(!cache.finance)return Promise.resolve(false);
      const snapshot=JSON.parse(JSON.stringify({finance,uploads}));
      return enqueue(async()=>{const result=await putJson('/finance',snapshot);return result.ok&&acceptState(result.data);});
    },
    async getFinanceDocument(id) {
      if(!hydrated || writeBlocked || !/^[a-f0-9]{64}$/.test(id))return null;
      const controller=new AbortController(), timer=setTimeout(()=>controller.abort(),requestTimeout);
      try{const response=await fetch(url('/finance-documents/'+id),{credentials:'include',signal:controller.signal});return response.ok?await response.blob():null;}
      catch{return null;}finally{clearTimeout(timer);}
    },
    getKnowledge() { return JSON.parse(JSON.stringify(cache.knowledge)); },
    saveKnowledge(knowledge) {
      const snapshot = JSON.parse(JSON.stringify(knowledge));
      return enqueue(async () => {
        const result = await putJson("/knowledge", {knowledge: snapshot});
        return result.ok && acceptState(result.data);
      });
    },
    async estimateRequest(item) {
      if(!hydrated)return null;
      const result=await req('/portal/estimate?'+new URLSearchParams(item));
      return result.ok ? result.data.quote : null;
    },
    getDaily() { return JSON.parse(JSON.stringify(cache.daily)); },
    saveDaily(daily) {
      const snapshot = JSON.parse(JSON.stringify(daily));
      return enqueue(async () => {
        const result = await putJson("/daily", {daily: snapshot});
        return result.ok && acceptState(result.data);
      });
    },
    saveDocument(document) {
      const snapshot = JSON.parse(JSON.stringify(document));
      return enqueue(async () => {
        const result = await postJson("/documents", snapshot);
        return result.ok && acceptState(result.data);
      });
    },
    async getDocument(id) {
      if (!hydrated || writeBlocked || !/^[a-f0-9]{32}$/.test(id)) return null;
      const controller = new AbortController();
      const timer = setTimeout(() => controller.abort(), requestTimeout);
      try {
        const response = await fetch(url("/documents/" + id), {credentials:"include",signal:controller.signal});
        if (!response.ok) return null;
        return await response.blob();
      } catch { return null; }
      finally { clearTimeout(timer); }
    },
    saveObservations(obs) {
      if (!hydrated) return enqueue(() => false);
      const snapshot = JSON.parse(JSON.stringify(obs));
      return enqueue(async () => {
        if (!await extractAudio(snapshot, obs)) return false;
        const result = await putJson("/observations", { observations: snapshot });
        if (result.ok) cache.observations = obs;
        return result.ok;
      });
    },
    saveInvites(invites) {
      if (!hydrated) return enqueue(() => false);
      const snapshot = JSON.parse(JSON.stringify(invites));
      return enqueue(async () => {
        const result = await putJson("/invites", { invites: snapshot });
        if (result.ok) cache.invites = invites;
        return result.ok;
      });
    },
    saveLanguage(language) {
      if (!hydrated) return enqueue(() => false);
      return enqueue(async () => {
        const result = await putJson("/prefs", { language });
        if (result.ok) cache.language = language;
        return result.ok;
      });
    },
  };
})(window);

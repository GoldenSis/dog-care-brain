/* Adapter behind window.DOGCARE_API (the API server injects "/api").
   Flag off (undefined/falsy) → no storage or network access from this file.
   Flag on → hydrate account state, optionally import dogcare-observations,
   dogcare-invites and dogcare-language once per business; dogcare-daily-v1 is
   excluded. Save through /api with a session cookie; browser copies stay intact.
   Observations/invites/daily records use full replacement snapshots,
   language is per user, and care writes bind to the loaded business/revision.
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
  };

  function url(path) {
    return String(base).replace(/\/$/, "") + path;
  }

  function failed() {
    if (typeof w.showToast === "function") w.showToast(writeBlocked || "Not saved — check your connection and try again");
  }

  let hydrated = false;
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
      if (writeBlocked || businessId === null) { failed(); return { ok: false, status: 0, data: {} }; }
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
      if (writing && r.ok && path !== "/blobs") {
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
    businessId = data.business_id;
    revision = data.revision;
    cache.observations = data.observations;
    cache.dogs = data.dogs || [];
    cache.invites = data.invites;
    cache.language = data.language || "en";
    cache.daily = data.daily || {version:1,clients:[],dogs:[],bookings:[],rates:{currency:"CHF",walk:null,day:null,night:null},documents:[]};
    cache.knowledge = data.knowledge || {version:1,experiences:[]};
    return true;
  }

  const ready = (async function hydrate() {
    const state = await req("/state");
    if (state.status === 401) {
      loadError = "Open your sign-in link in this browser to access your account. If the link has expired or was already used, request a new one from the person who gave you access.";
      return false;
    }
    if (!state.ok || !acceptState(state.data)) return false;
    const marker = "dogcare-imported:" + state.data.business_id;
    if (!state.data.imported && !w.localStorage.getItem(marker)) {
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

  // Await ready's boolean before using cached getters or saving. Valid save calls
  // resolve to booleans in call order; whenSaved waits for writes already queued.
  // Observation saves reconcile uploaded data URLs into the supplied objects.
  w.DogCareAPI = {
    ready,
    getLoadError() { return loadError; },
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
    getKnowledge() { return JSON.parse(JSON.stringify(cache.knowledge)); },
    saveKnowledge(knowledge) {
      const snapshot = JSON.parse(JSON.stringify(knowledge));
      return enqueue(async () => {
        const result = await putJson("/knowledge", {knowledge: snapshot});
        return result.ok && acceptState(result.data);
      });
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

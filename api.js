/* Adapter behind window.DOGCARE_API. Flag off (undefined/falsy) → this file is a no-op.
   Flag on → the three localStorage keys go through /api and a session cookie. */
(function (w) {
  const base = w.DOGCARE_API;
  if (!base) return;

  const cache = {
    observations: null,
    invites: [],
    language: "en",
  };

  function url(path) {
    return String(base).replace(/\/$/, "") + path;
  }

  function failed() {
    if (typeof w.showToast === "function") w.showToast("Not saved — check your connection and try again");
  }

  let hydrated = false;
  let loadError = "Could not load your account. Check your connection and reload.";
  let writes = Promise.resolve();
  const uploaded = new Map();

  async function req(path, opts) {
    const writing = opts && opts.method && opts.method !== "GET";
    try {
      const r = await fetch(url(path), Object.assign({ credentials: "include" }, opts));
      const text = await r.text();
      const data = text ? JSON.parse(text) : {};
      if (!r.ok && writing) failed();
      return { ok: r.ok, status: r.status, data };
    } catch {
      if (writing) failed();
      return { ok: false, status: 0, data: {} };
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
        Array.isArray(data.observations) || !Array.isArray(data.invites)) return false;
    cache.observations = data.observations;
    cache.invites = data.invites;
    cache.language = data.language || "en";
    return true;
  }

  const ready = (async function hydrate() {
    const state = await req("/state");
    if (state.status === 401) {
      loadError = "Sign in using your magic link, then reload to open your account.";
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
    writes = writes.then(save).catch(() => { failed(); return false; });
    return writes;
  }

  w.DogCareAPI = {
    ready,
    getLoadError() { return loadError; },
    whenSaved() { return writes; },
    getObservations() {
      return cache.observations || {};
    },
    getInvites() {
      return cache.invites || [];
    },
    getLanguage() {
      return cache.language || "en";
    },
    saveObservations(obs) {
      if (!hydrated) return enqueue(() => false);
      cache.observations = obs;
      const snapshot = JSON.parse(JSON.stringify(obs));
      return enqueue(async () => {
        if (!await extractAudio(snapshot, obs)) return false;
        return (await putJson("/observations", { observations: snapshot })).ok;
      });
    },
    saveInvites(invites) {
      if (!hydrated) return enqueue(() => false);
      cache.invites = invites;
      const snapshot = JSON.parse(JSON.stringify(invites));
      return enqueue(async () => (await putJson("/invites", { invites: snapshot })).ok);
    },
    saveLanguage(language) {
      if (!hydrated) return enqueue(() => false);
      cache.language = language;
      return enqueue(async () => (await putJson("/prefs", { language })).ok);
    },
  };
})(window);

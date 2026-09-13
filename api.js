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

  async function req(path, opts) {
    let r;
    try {
      r = await fetch(url(path), Object.assign({ credentials: "include" }, opts));
    } catch {
      if (opts && opts.method && opts.method !== "GET") failed();
      return { ok: false, status: 0, data: {} };
    }
    const text = await r.text();
    let data = {};
    try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
    if (!r.ok && opts && opts.method && opts.method !== "GET") failed();
    return { ok: r.ok, status: r.status, data };
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
    const m = /^data:([^;]+);base64,(.+)$/.exec(dataUrl || "");
    if (!m) return null;
    const res = await postJson("/blobs", { type: m[1], data: m[2] });
    if (!res.ok || !res.data.ref) return null;
    return url("/blobs/" + res.data.ref);
  }

  async function persistObservations(obs) {
    const copy = JSON.parse(JSON.stringify(obs || {}));
    for (const slug of Object.keys(copy)) {
      for (const item of copy[slug] || []) {
        const src = item.audio && item.audio.url;
        if (src && src.startsWith("data:")) {
          const refUrl = await uploadDataUrl(src);
          if (refUrl) item.audio.url = refUrl;
        }
      }
    }
    await putJson("/observations", { observations: copy });
    cache.observations = copy;
  }

  const ready = (async function hydrate() {
    const localObs = w.localStorage.getItem("dogcare-observations");
    const localInv = w.localStorage.getItem("dogcare-invites");
    const localLang = w.localStorage.getItem("dogcare-language");
    const state = await req("/state");
    if (state.status === 401) return false;
    if (!state.ok) return false;
    const imported = w.localStorage.getItem("dogcare-imported");
    if (localObs && !imported) {
      let observations = {}, invites = [];
      try { observations = JSON.parse(localObs) || {}; } catch { observations = {}; }
      try { invites = JSON.parse(localInv) || []; } catch { invites = []; }
      // The server imports once per business and ignores later calls, so a second
      // device's stale localStorage can never overwrite real notes.
      await postJson("/import", { observations, invites, language: localLang || "en" });
      w.localStorage.setItem("dogcare-imported", "1");
      const again = await req("/state");
      if (again.ok) Object.assign(cache, {
        observations: again.data.observations,
        invites: again.data.invites || [],
        language: again.data.language || localLang || "en",
      });
      return true;
    }
    cache.observations = state.data.observations;
    cache.invites = state.data.invites || [];
    cache.language = state.data.language || localLang || "en";
    return true;
  })();

  w.DogCareAPI = {
    ready,
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
      cache.observations = obs;
      persistObservations(obs);
    },
    saveInvites(invites) {
      cache.invites = invites;
      putJson("/invites", { invites });
    },
    saveLanguage(language) {
      cache.language = language;
      putJson("/prefs", { language });
    },
  };
})(window);

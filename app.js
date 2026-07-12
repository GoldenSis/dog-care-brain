const baseObservations = {
  billie: [
    { id: 1, time: '08:25', date: 'Today', title: 'Breakfast & morning check-in', text: 'Finished her full breakfast and drank well. Bright, relaxed and ready for the day.', tags: ['Nutrition', 'Mood · bright'] },
    { id: 2, time: '10:10', date: 'Today', title: 'Woodland walk', text: 'A calm 42-minute sniff walk. Good recall around two dogs and no stiffness noticed.', tags: ['Exercise · 42 min', 'Behaviour · calm'] },
    { id: 3, time: '18:40', date: 'Yesterday', title: 'Evening medication', text: 'Joint supplement given with dinner. Coat and paws checked after rain.', tags: ['Medication', 'Health check'] }
  ],
  charlie: [
    { id: 4, time: '09:15', date: 'Today', title: 'Settled into day care', text: 'A little vocal at drop-off, then settled on the green bed after five minutes.', tags: ['Behaviour', 'Mood · settled'] },
    { id: 5, time: '11:30', date: 'Today', title: 'Play session', text: 'Gentle play with Billie in the garden. Responded well to breaks and name cues.', tags: ['Social', 'Training'] }
  ]
};
const frenchExtras = {
  'Billie and Charlie are both checked in. Capture the little moments now and their owner stories will write themselves.':'Billie et Charlie sont bien arrivés. Notez les petits moments : leurs récits pour propriétaires se construiront naturellement.',
  'Live care context, always close by':'Le contexte de soin, toujours à portée de main',
  'Your newest structured observation':'Votre dernière observation structurée',
  '3 of 5 moments complete':'3 moments sur 5 terminés',
  'Day care until 17:30':'Garde de jour jusqu’à 17 h 30','Day care until 18:00':'Garde de jour jusqu’à 18 h',
  'Both dogs':'Les deux chiens','Prepare daily recaps':'Préparer les récits quotidiens',
  'Revenue booked':'Chiffre d’affaires réservé','Capacity filled':'Capacité remplie','Healthy momentum':'Belle dynamique',
  'You’re €340 ahead of this point last month.':'Vous avez 340 € d’avance sur la même période le mois dernier.',
  'Everything that helps Billie feel understood.':'Tout ce qui aide Billie à se sentir compris.',
  'Everything that helps Charlie feel understood.':'Tout ce qui aide Charlie à se sentir compris.',
  'Checked in':'Arrivé','Consent on file':'Accord enregistré','Quick reference for every handover':'Repère rapide pour chaque relais',
  'Write naturally. DogCare Brain will organise the useful details.':'Écrivez naturellement. DogCare Brain organisera les détails utiles.',
  'Start typing to see structured care tags':'Commencez à écrire pour voir les étiquettes structurées',
  'AI structuring preview · This local demo uses on-device rules and sends no data anywhere.':'Aperçu de structuration IA · Cette démo locale n’envoie aucune donnée.',
  'Owner-ready, not auto-sent':'Prêt pour le propriétaire, jamais envoyé automatiquement',
  'Review this draft before sharing. In a future connected version, you could send it through WhatsApp or add it to an Instagram story.':'Relisez ce brouillon avant partage. Une future version connectée pourra préparer WhatsApp ou Instagram.',
  'Preview WhatsApp message':'Prévisualiser le message WhatsApp','Draft preview only · no message will be sent':'Brouillon uniquement · aucun message ne sera envoyé',
  '11 bookings · 76% of this week’s care capacity':'11 réservations · 76 % de la capacité de soin cette semaine','＋ New booking':'＋ Nouvelle réservation',
  'Upcoming handovers':'Prochains départs','Everything owners need before the doorbell rings':'Tout ce dont les propriétaires ont besoin avant la sonnette',
  'A small business, clearly seen':'Une petite entreprise, clairement pilotée','REVENUE BOOKED':'CA RÉSERVÉ','NET AFTER EXPENSES':'NET APRÈS FRAIS','CARE HOURS':'HEURES DE SOIN','REPEAT OWNERS':'PROPRIÉTAIRES FIDÈLES',
  'Revenue rhythm':'Rythme du chiffre d’affaires','Last 7 months · demo data':'7 derniers mois · données de démonstration','Recent expenses':'Dépenses récentes','＋ Add':'＋ Ajouter'
};

const dogs = {
  billie: { name: 'Billie Blue', emoji: '🐕‍🦺', age: 'Profile to complete', breed: 'Breed to confirm', owner: 'Arnaud Chrétien', last: '10:10 woodland walk', health: 'Radiograph recorded at Clinique Artémis. Add current care instructions.', behaviour: 'Add routine, triggers and favourite rewards.', vet: 'Clinique Artémis · Vet.Avenir', vets: [{name:'Vet.Avenir', role:'Current clinic · verified public contact', phone:'+41223615540', video:'Clinic booking site'}, {name:'Clinique Artémis', role:'Radiograph history · contact to verify'}], needs: { energy: 'Confirm with owner', movement: 'Set a daily movement target', enrichment: 'Add favourite enrichment', sensitivities: 'Add sensitivities and recovery needs' }, colour: '' },
  charlie: { name: 'Charlie Rose', emoji: '🐶', age: 'Profile to complete', breed: 'Breed to confirm', owner: 'Arnaud Chrétien', last: '11:30 garden play', health: 'Add current health and medication instructions.', behaviour: 'Add routine, triggers and favourite rewards.', vet: 'Add preferred vet and emergency contact', vets: [], needs: { energy: 'Confirm with owner', movement: 'Set a daily movement target', enrichment: 'Add favourite enrichment', sensitivities: 'Add sensitivities and recovery needs' }, colour: 'charlie' }
};

const translations = {
  en: {},
  fr: {Today:'Aujourd’hui',Dogs:'Chiens',Capture:'Saisir',Gallery:'Galerie','Daily story':'Récit du jour',Schedule:'Planning',Business:'Activité',Settings:'Réglages','All systems calm':'Tout est calme','Capture update':'Ajouter une note','Good morning, Adine-Sophie':'Bonjour, Adine-Sophie','TODAY AT A GLANCE':'APERÇU DU JOUR','Two happy dogs, one beautifully organisé day.':'Deux chiens heureux, une journée bien organisée.','Two happy dogs, one beautifully organised day.':'Deux chiens heureux, une journée bien organisée.','Add a care moment →':'Ajouter une note de soin →','Your dogs today':'Vos chiens aujourd’hui','View profiles':'Voir les profils','Latest from the care log':'Dernière note de soin','Today’s rhythm':'Le rythme du jour','Business snapshot':'Aperçu de l’activité','RAPID CAPTURE':'SAISIE RAPIDE','Capture the moment':'Saisir le moment','What just happened?':'Que vient-il de se passer ?','Who is this about?':'Pour quel chien ?','Care update':'Note de soin','Detected details':'Détails détectés','DOG PROFILE':'PROFIL DU CHIEN','Care record':'Dossier de soin','Care timeline':'Historique de soin','Care context':'Contexte de soin','OWNER UPDATE · DRAFT':'MISE À JOUR PROPRIÉTAIRE · BROUILLON','A lovely day, ready to share':'Une belle journée, prête à partager','Bookings overview':'Vue des réservations','BUSINESS · JULY':'ACTIVITÉ · JUILLET'},
  it: {Today:'Oggi',Dogs:'Cani',Capture:'Registra',Gallery:'Galleria','Daily story':'Racconto del giorno',Schedule:'Agenda',Business:'Attività',Settings:'Impostazioni','All systems calm':'Tutto è tranquillo','Capture update':'Aggiungi nota','Good morning, Adine-Sophie':'Buongiorno, Adine-Sophie','TODAY AT A GLANCE':'PANORAMICA DI OGGI','Two happy dogs, one beautifully organised day.':'Due cani felici, una giornata ben organizzata.','Add a care moment →':'Aggiungi un momento di cura →','Your dogs today':'I tuoi cani oggi','View profiles':'Vedi profili','Latest from the care log':'Ultima nota di cura','Today’s rhythm':'Il ritmo di oggi','Business snapshot':'Panoramica attività','RAPID CAPTURE':'REGISTRAZIONE RAPIDA','Capture the moment':'Cattura il momento','What just happened?':'Cosa è appena successo?','Who is this about?':'Di chi si tratta?','Care update':'Aggiornamento cura','Detected details':'Dettagli rilevati','DOG PROFILE':'PROFILO DEL CANE','Care record':'Scheda di cura','Care timeline':'Cronologia di cura','Care context':'Contesto di cura','OWNER UPDATE · DRAFT':'AGGIORNAMENTO PROPRIETARIO · BOZZA','A lovely day, ready to share':'Una bella giornata, pronta da condividere','Bookings overview':'Panoramica prenotazioni','BUSINESS · JULY':'ATTIVITÀ · LUGLIO'},
  el: {Today:'Σήμερα',Dogs:'Σκύλοι',Capture:'Καταγραφή',Gallery:'Συλλογή','Daily story':'Ιστορία ημέρας',Schedule:'Πρόγραμμα',Business:'Επιχείρηση',Settings:'Ρυθμίσεις','All systems calm':'Όλα είναι ήρεμα','Capture update':'Νέα σημείωση','Good morning, Adine-Sophie':'Καλημέρα, Adine-Sophie','TODAY AT A GLANCE':'ΗΜΕΡΗΣΙΑ ΕΠΙΣΚΟΠΗΣΗ','Two happy dogs, one beautifully organised day.':'Δύο χαρούμενα σκυλιά, μια οργανωμένη ημέρα.','Add a care moment →':'Προσθήκη στιγμής φροντίδας →','Your dogs today':'Τα σκυλιά σας σήμερα','View profiles':'Προβολή προφίλ','Latest from the care log':'Τελευταία καταγραφή φροντίδας','Today’s rhythm':'Ο ρυθμός της ημέρας','Business snapshot':'Σύνοψη επιχείρησης','RAPID CAPTURE':'ΓΡΗΓΟΡΗ ΚΑΤΑΓΡΑΦΗ','Capture the moment':'Καταγράψτε τη στιγμή','What just happened?':'Τι συνέβη μόλις τώρα;','Who is this about?':'Για ποιον είναι;','Care update':'Ενημέρωση φροντίδας','Detected details':'Εντοπισμένες λεπτομέρειες','DOG PROFILE':'ΠΡΟΦΙΛ ΣΚΥΛΟΥ','Care record':'Αρχείο φροντίδας','Care timeline':'Χρονολόγιο φροντίδας','Care context':'Πλαίσιο φροντίδας','OWNER UPDATE · DRAFT':'ΕΝΗΜΕΡΩΣΗ ΙΔΙΟΚΤΗΤΗ · ΠΡΟΣΧΕΔΙΟ','A lovely day, ready to share':'Μια όμορφη ημέρα, έτοιμη για κοινοποίηση','Bookings overview':'Επισκόπηση κρατήσεων','BUSINESS · JULY':'ΕΠΙΧΕΙΡΗΣΗ · ΙΟΥΛΙΟΣ'},
  es: {Today:'Hoy',Dogs:'Perros',Capture:'Registrar',Gallery:'Galería','Daily story':'Historia del día',Schedule:'Agenda',Business:'Negocio',Settings:'Ajustes','All systems calm':'Todo está en calma','Capture update':'Añadir nota','Good morning, Adine-Sophie':'Buenos días, Adine-Sophie','TODAY AT A GLANCE':'RESUMEN DE HOY','Two happy dogs, one beautifully organised day.':'Dos perros felices, un día perfectamente organizado.','Add a care moment →':'Añadir un momento de cuidado →','Your dogs today':'Tus perros hoy','View profiles':'Ver perfiles','Latest from the care log':'Última nota de cuidado','Today’s rhythm':'El ritmo de hoy','Business snapshot':'Resumen del negocio','RAPID CAPTURE':'REGISTRO RÁPIDO','Capture the moment':'Registra el momento','What just happened?':'¿Qué acaba de pasar?','Who is this about?':'¿De quién se trata?','Care update':'Actualización de cuidado','Detected details':'Detalles detectados','DOG PROFILE':'PERFIL DEL PERRO','Care record':'Ficha de cuidado','Care timeline':'Historial de cuidado','Care context':'Contexto de cuidado','OWNER UPDATE · DRAFT':'ACTUALIZACIÓN PARA EL DUEÑO · BORRADOR','A lovely day, ready to share':'Un bonito día, listo para compartir','Bookings overview':'Resumen de reservas','BUSINESS · JULY':'NEGOCIO · JULIO'}
};
Object.assign(translations.fr, frenchExtras);
translations.de = {Today:'Heute',Dogs:'Hunde',Capture:'Erfassen',Gallery:'Galerie','Daily story':'Tagesbericht',Schedule:'Planung',Business:'Betrieb',Settings:'Einstellungen','All systems calm':'Alles im grünen Bereich','Capture update':'Notiz erfassen','Good morning, Adine-Sophie':'Guten Morgen, Adine-Sophie','TODAY AT A GLANCE':'HEUTE IM ÜBERBLICK','Two happy dogs, one beautifully organised day.':'Zwei glückliche Hunde, ein bestens organisierter Tag.','Add a care moment →':'Pflegemoment hinzufügen →','Your dogs today':'Ihre Hunde heute','View profiles':'Profile ansehen','Latest from the care log':'Neuester Pflegeeintrag','Today’s rhythm':'Tagesablauf','Business snapshot':'Betriebsübersicht','RAPID CAPTURE':'SCHNELLE ERFASSUNG','Capture the moment':'Moment erfassen','What just happened?':'Was ist gerade passiert?','Who is this about?':'Wen betrifft das?','Care update':'Pflege-Update','Detected details':'Erkannte Details','DOG PROFILE':'HUNDEPROFIL','Care record':'Pflegeakte','Care timeline':'Pflegeverlauf','Care context':'Pflegekontext','OWNER UPDATE · DRAFT':'BESITZER-UPDATE · ENTWURF','A lovely day, ready to share':'Ein schöner Tag, bereit zum Teilen','Bookings overview':'Buchungsübersicht','BUSINESS · JULY':'BETRIEB · JULI'};
let state = { page: 'dashboard', dog: 'billie', language: localStorage.getItem('dogcare-language') || 'en', observations: loadObservations(), invites: loadInvites() };
let audioDraft = null;
let activeRecorder = null;
let recordingTimer = null;
let activeAudioStream = null;
let recordingSession = 0;
let recordingPending = false;
const content = document.querySelector('#app-content');
const title = document.querySelector('#page-title');
const eyebrow = document.querySelector('#page-eyebrow');

function loadObservations() {
  try { return JSON.parse(localStorage.getItem('dogcare-observations')) || structuredClone(baseObservations); }
  catch { return structuredClone(baseObservations); }
}
function saveObservations() { try { localStorage.setItem('dogcare-observations', JSON.stringify(state.observations)); } catch { showToast('Saved for this session, but browser storage is full'); } }
function loadInvites() {
  try { return JSON.parse(localStorage.getItem('dogcare-invites')) || []; }
  catch { return []; }
}
function saveInvites() { localStorage.setItem('dogcare-invites', JSON.stringify(state.invites)); }
function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function showToast(message) { const toast=document.querySelector('#toast'); toast.textContent=message; toast.classList.add('show'); setTimeout(()=>toast.classList.remove('show'),2500); }
function dogAvatar(key) { const d=dogs[key]; return `<div class="dog-avatar ${d.colour}">${d.emoji}</div>`; }
function t(text) { return translations[state.language]?.[text] || text; }
function setHeader(kicker, heading) { eyebrow.textContent=t(kicker); title.textContent=t(heading); }
function localizeContent() { const walker=document.createTreeWalker(content, NodeFilter.SHOW_TEXT), nodes=[]; while(walker.nextNode()) nodes.push(walker.currentNode); nodes.forEach(node=>{const source=node.nodeValue.trim();if(source && translations[state.language]?.[source]) node.nodeValue=node.nodeValue.replace(source,t(source));}); document.querySelectorAll('[data-i18n]').forEach(el=>el.textContent=t(el.dataset.i18n)); document.documentElement.lang=state.language; }
function tagsHtml(tags) { return `<div class="mini-tags">${tags.map(t=>`<span>${escapeHtml(t)}</span>`).join('')}</div>`; }
function formatDuration(seconds) { const value=Math.max(0,Math.floor(seconds)); return `${String(Math.floor(value/60)).padStart(2,'0')}:${String(value%60).padStart(2,'0')}`; }
function audioHtml(audio, label='Voice note') { return audio?.url ? `<div class="attached-audio"><strong>🎙 ${escapeHtml(label)}</strong><span>${formatDuration(audio.duration)}</span><audio controls preload="metadata" src="${audio.url}" aria-label="Play ${escapeHtml(label)}"></audio></div>` : ''; }
function formatPermissions(permissions) {
  const labels = { stories: 'Daily stories', timeline: 'Care timeline', health: 'Health notes' };
  return permissions.map(permission => labels[permission]).filter(Boolean);
}
function inviteRoleLabel(role) { return role === 'trusted-carer' ? 'Trusted carer' : 'Owner'; }
function pendingInvitesHtml() {
  if (!state.invites.length) return `<div class="empty-state small"><strong>No pending invites yet</strong><span>Create a preview to see it queued here.</span></div>`;
  return state.invites.map(invite => `<article class="pending-invite"><div><span class="status-dot"></span><strong>${escapeHtml(invite.name)}</strong><small>${escapeHtml(invite.email)} · ${inviteRoleLabel(invite.role)}</small></div><div>${tagsHtml(formatPermissions(invite.permissions))}</div><span class="pending-label">Pending preview</span></article>`).join('');
}
function careInsight(key) {
  const observations=state.observations[key];
  const health=observations.filter(o=>o.tags.some(tag=>/health|medication|sick|stool/i.test(tag)));
  const activity=observations.filter(o=>o.tags.some(tag=>/activity|exercise|walk|social/i.test(tag)));
  if (health.length >= 2) return { level:'review', title:'Repeated health observations', text:`${health.length} health-related notes are in the recent record. This is a care prompt, not a diagnosis: review the notes with the owner and contact a vet if concerned.` };
  if (health.length === 1) return { level:'watch', title:'Health note recorded', text:'One health-related note is in the record. Keep observing and share the exact facts with the owner; this app does not diagnose.' };
  if (activity.length >= 2) return { level:'good', title:'Routine context is building', text:'Several activity observations are now linked to this dog. Add energy and enrichment targets to make future insights more personal.' };
  return { level:'neutral', title:'No pattern yet', text:'Keep capturing small moments. Insights appear only when there is enough care history to support them.' };
}

const views = {
  dashboard() {
    setHeader('SUNDAY · 12 JULY', 'Good morning, Adine-Sophie');
    const latest = state.observations.billie[0];
    return `<div class="grid dashboard-grid"><div>
      <section class="card hero"><p class="eyebrow" style="color:#d6ed8c">TODAY AT A GLANCE</p><h2>Two happy dogs, one beautifully organised day.</h2><p>Billie and Charlie are both checked in. Capture the little moments now and their owner stories will write themselves.</p><button class="primary" data-go="capture">Add a care moment →</button></section>
      <div class="section-head"><div><h2>Your dogs today</h2><p>Live care context, always close by</p></div><button class="link-button" data-go="dogs">View profiles</button></div>
      <div class="dog-row">${Object.entries(dogs).map(([key,d])=>`<article class="card dog-card" data-dog="${key}">${dogAvatar(key)}<div class="dog-meta"><h3>${d.name}</h3><p>${d.breed} · ${d.owner}</p>${tagsHtml(key==='billie'?['Day care','All good']:['Day care','Settled'])}</div><span class="dog-arrow">›</span></article>`).join('')}</div>
      <div class="section-head"><div><h2>Latest from the care log</h2><p>Your newest structured observation</p></div></div>
      <article class="card timeline-card"><div class="timeline-top"><h4>${escapeHtml(latest.title)}</h4><time>${latest.time} · ${latest.date}</time></div><p>${escapeHtml(latest.text)}</p>${tagsHtml(latest.tags)}</article>
    </div><aside>
      <section class="card"><div class="section-head" style="margin-top:0"><div><h2>Today's rhythm</h2><p>3 of 5 moments complete</p></div></div><div class="today-list"><div class="booking"><time>08:00</time><div><h4>Billie · arrival</h4><p>Day care until 17:30</p></div><i class="dot"></i></div><div class="booking"><time>09:00</time><div><h4>Charlie · arrival</h4><p>Day care until 18:00</p></div><i class="dot"></i></div><div class="booking"><time>12:30</time><div><h4>Lunch & quiet time</h4><p>Both dogs</p></div><i class="dot peach"></i></div><div class="booking"><time>16:30</time><div><h4>Owner stories</h4><p>Prepare daily recaps</p></div><i class="dot peach"></i></div></div></section>
      <section class="card" style="margin-top:20px"><div class="section-head" style="margin-top:0"><div><h2>July pulse</h2><p>Business snapshot</p></div></div><div class="kpi"><div><strong>€2,840</strong><small>Revenue booked</small></div><div><strong>76%</strong><small>Capacity filled</small></div></div><div class="progress"><span style="width:76%"></span></div><div class="notice"><strong>Healthy momentum</strong>You’re €340 ahead of this point last month.</div></section>
    </aside></div>`;
  },
  dogs() {
    const key=state.dog,d=dogs[key], obs=state.observations[key];
    setHeader('DOG PROFILE', d.name);
    return `<div class="page-title-row"><div><h2>Care record</h2><p>Everything that helps ${d.name.split(' ')[0]} feel understood.</p></div><button class="primary" data-go="capture">＋ Add observation</button></div><div class="grid page-grid"><div>
      <section class="card profile-hero">${dogAvatar(key)}<div><h2>${d.name}</h2><p>${d.breed} · ${d.age} · Owner: ${d.owner}</p>${tagsHtml(['Checked in','Consent on file'])}</div></section>
      <section class="card" style="margin-top:20px"><div class="section-head" style="margin-top:0"><div><h2>Needs & lifestyle</h2><p>Personalise these with the owner — not breed stereotypes.</p></div></div><div class="facts"><div class="fact"><small>Energy</small><strong>${d.needs.energy}</strong></div><div class="fact"><small>Movement</small><strong>${d.needs.movement}</strong></div><div class="fact"><small>Enrichment</small><strong>${d.needs.enrichment}</strong></div><div class="fact"><small>Sensitivities</small><strong>${d.needs.sensitivities}</strong></div></div></section>
      <div class="section-head"><div><h2>Care timeline</h2><p>${obs.length} recorded moments</p></div></div><div class="timeline">${obs.map(o=>`<article class="card timeline-card"><div class="timeline-top"><h4>${escapeHtml(o.title)}</h4><time>${o.time} · ${o.date}</time></div><p>${escapeHtml(o.text)}</p>${audioHtml(o.audio, `${o.title} voice note`)}${tagsHtml(o.tags)}</article>`).join('')}</div>
    </div><aside><section class="card"><div class="section-head" style="margin-top:0"><div><h2>Care insight</h2><p>Evidence-based prompt · never a diagnosis</p></div></div><div class="context ${careInsight(key).level==='review'?'behaviour':''}"><strong>${careInsight(key).title}</strong><p>${careInsight(key).text}</p></div></section><section class="card" style="margin-top:20px"><div class="section-head" style="margin-top:0"><div><h2>Care context</h2><p>Quick reference for every handover</p></div></div><div class="context-list"><div class="context"><strong>HEALTH</strong><p>${d.health}</p></div><div class="context behaviour"><strong>BEHAVIOUR</strong><p>${d.behaviour}</p></div><div class="context vet"><strong>VET & EMERGENCY</strong><p>${d.vet}</p></div></div><div class="facts"><div class="fact"><small>Food</small><strong>Set with owner</strong></div><div class="fact"><small>Walk</small><strong>Set with owner</strong></div><div class="fact"><small>Pickup</small><strong>Set with owner</strong></div></div></section><section class="card" style="margin-top:20px"><div class="section-head" style="margin-top:0"><div><h2>Vet access</h2><p>Preview only · no clinic is contacted</p></div></div><p style="font-size:12px;color:var(--muted);line-height:1.5">${d.vet}</p><div class="composer-actions"><button class="secondary" id="vet-call">Call clinic</button><button class="ghost" id="vet-video">Video consult</button></div></section><section class="card" style="margin-top:20px"><h3 style="font:400 20px Georgia,serif">Switch dog</h3><div class="dog-picker">${Object.entries(dogs).map(([k,x])=>`<button class="dog-pick ${k===key?'active':''}" data-dog="${k}"><span>${x.emoji}</span><div><strong>${x.name.split(' ')[0]}</strong><small>${x.age}</small></div></button>`).join('')}</div></section></aside></div>`;
  },
  capture() {
    const d=dogs[state.dog]; setHeader('RAPID CAPTURE', 'Capture the moment');
    return `<div class="page-title-row"><div><h2>What just happened?</h2><p>Write naturally. DogCare Brain will organise the useful details.</p></div></div><section class="card composer"><label class="label">Who is this about?</label><div class="dog-picker">${Object.entries(dogs).map(([k,x])=>`<button class="dog-pick ${k===state.dog?'active':''}" data-capture-dog="${k}"><span>${x.emoji}</span><div><strong>${x.name}</strong><small>${x.last}</small></div></button>`).join('')}</div><label class="label" for="observation">Care update</label><textarea id="observation" placeholder="Try: Ate all breakfast, playful with Mabel, loose stool at 10:30…"></textarea><section class="voice-recorder" aria-labelledby="voice-title"><div><strong id="voice-title">Add a voice note</strong><p id="recording-status" role="status">Microphone access is requested only after you choose Record.</p></div><div class="recorder-actions"><button class="ghost" type="button" id="record-audio">● Record</button><button class="secondary" type="button" id="stop-audio" hidden>■ Stop</button><span id="recording-duration" aria-label="Recording duration">00:00</span></div><div id="audio-preview">${audioDraft ? `${audioHtml(audioDraft, 'Care update voice note')}<button class="link-button discard-audio" type="button" id="discard-audio">Discard recording</button>` : ''}</div></section><label class="label">Detected details <small style="font-weight:400;text-transform:none;letter-spacing:0"> · updates as you type</small></label><div class="detected" id="detected"><em>Start typing to see structured care tags</em></div><p id="health-safety" class="preview-note" hidden>Health observations are factual notes, not diagnoses. Contact a veterinarian if concerned.</p><div class="composer-actions"><small>AI structuring and audio stay in this browser. Nothing is uploaded or sent.</small><button class="primary" id="save-observation">Save to ${d.name.split(' ')[0]}'s timeline →</button></div></section>`;
  },
  gallery() { setHeader('MEDIA LIBRARY','Little moments, safely kept'); const items=[['🐕‍🦺','Billie’s woodland walk','Today · 10:12'],['🐶','Charlie in the garden','Today · 11:34'],['🐾','Muddy-paw evidence','Yesterday · 16:45'],['🌿','The favourite sniff spot','10 July · 09:50'],['🦴','Enrichment time','9 July · 14:20'],['☁️','Post-walk snooze','8 July · 12:15']]; const audioItems=Object.values(state.observations).flat().filter(o=>o.audio?.url); return `<div class="page-title-row"><div><h2>Care gallery</h2><p>Demo media and voice notes kept in this browser.</p></div></div>${audioItems.length?`<section class="card audio-library"><div class="section-head"><div><h2>Voice notes</h2><p>Attached locally to care updates for this browser session</p></div></div>${audioItems.map(o=>audioHtml(o.audio,o.title)).join('')}</section>`:''}<div class="grid media-grid">${items.map((x,i)=>`<article class="media-item"><div class="media-art" aria-hidden="true">${x[0]}</div>${i<2?'<span class="draft-badge">Story ready</span>':''}<div class="media-copy"><strong>${x[1]}</strong><small>${x[2]}</small></div></article>`).join('')}</div><section class="card social-preview" aria-labelledby="social-heading"><div class="section-head"><div><h2 id="social-heading">Social access previews</h2><p>Explore what a future connection could share. No account is connected and nothing can be posted.</p></div></div><div class="social-platforms">${[['Instagram','Photo and story draft'],['Facebook','Page update draft'],['YouTube','Short video draft']].map(([name,detail])=>`<article><span class="platform-mark" aria-hidden="true">${name[0]}</span><div><strong>${name}</strong><small>${detail} · local preview only</small></div><button class="ghost social-access" type="button" data-platform="${name}" aria-label="Preview local ${name} access">Preview access</button></article>`).join('')}</div><div class="local-boundary"><strong>No social connection</strong><span>No credentials are collected, no network request is made, and no content is posted.</span></div></section>`; },
  story() { const d=dogs[state.dog], latest=state.observations[state.dog][0]; setHeader('OWNER UPDATE · DRAFT','A lovely day, ready to share'); return `<div class="grid page-grid"><div class="story-phone"><div class="story-image">${d.emoji}</div><div class="story-body"><p class="story-date">Sunday, 12 July · Daily story</p><h3>${d.name}’s day</h3><p class="story-copy">${escapeHtml(latest.text)} ${d.name.split(' ')[0]} enjoyed plenty of calm attention and is heading home happy and settled.</p><div class="story-stats"><div><strong>${state.dog==='billie'?'42 min':'25 min'}</strong><small>outside</small></div><div><strong>All eaten</strong><small>meals</small></div><div><strong>Calm</strong><small>mood</small></div></div></div></div><aside><section class="card"><h2 style="font:400 24px Georgia,serif">Owner-ready, not auto-sent</h2><p style="font-size:12px;color:var(--muted);line-height:1.6">Review this draft before sharing. In a future connected version, you could send it through WhatsApp or add it to an Instagram story.</p><label class="label">Preview for</label><div class="dog-picker">${Object.entries(dogs).map(([k,x])=>`<button class="dog-pick ${k===state.dog?'active':''}" data-story-dog="${k}"><span>${x.emoji}</span><div><strong>${x.name}</strong><small>${x.owner}</small></div></button>`).join('')}</div><button class="secondary" id="whatsapp-preview" style="width:100%;margin-top:20px">Preview WhatsApp message</button><p class="preview-note">Draft preview only · no message will be sent</p></section></aside></div>`; },
  invite() { setHeader('INVITE PREVIEW','Share care context safely'); return `<div class="page-title-row"><div><h2>Prepare an invite</h2><p>Build a local pending invite preview for an owner or trusted carer. Nothing is sent.</p></div></div><div class="grid page-grid invite-grid"><section class="card invite-card"><div class="form-row"><label class="label">Invite role</label><div class="role-choice" role="radiogroup" aria-label="Invite role"><label><input type="radio" name="invite-role" value="owner" checked><span><strong>Owner</strong><small>Family member who receives updates</small></span></label><label><input type="radio" name="invite-role" value="trusted-carer"><span><strong>Trusted carer</strong><small>Backup helper with limited context</small></span></label></div></div><div class="form-split"><label class="field-label" for="invite-name">Name<input id="invite-name" autocomplete="name" placeholder="e.g. Camille Martin"></label><label class="field-label" for="invite-email">Email<input id="invite-email" type="email" autocomplete="email" placeholder="camille@example.com"></label></div><label class="label">Can preview</label><div class="permission-list"><label><input type="checkbox" name="invite-permission" value="stories" checked><span><strong>Daily stories</strong><small>Owner-ready recaps and media placeholders</small></span></label><label><input type="checkbox" name="invite-permission" value="timeline" checked><span><strong>Care timeline</strong><small>Structured observations and handover notes</small></span></label><label><input type="checkbox" name="invite-permission" value="health"><span><strong>Health notes</strong><small>Factual medication and watch items, never diagnoses</small></span></label></div><div class="local-boundary"><strong>Local preview only</strong><span>This prototype will not send email, WhatsApp, SMS, or notifications.</span></div><div class="composer-actions"><small>Demo data only · the invite is stored in this browser as pending.</small><button class="primary" id="create-invite">Create pending invite preview →</button></div></section><aside><section class="card summary-card"><div class="section-head" style="margin-top:0"><div><h2>Invite-ready summary</h2><p>Updates as you choose role and permissions</p></div></div><div id="invite-summary" class="invite-summary"></div></section><section class="card" style="margin-top:20px"><div class="section-head" style="margin-top:0"><div><h2>Pending invites</h2><p>Local preview queue</p></div></div><div id="pending-invites" class="pending-list">${pendingInvitesHtml()}</div></section></aside></div>`; },
  schedule() { setHeader('SCHEDULE · 12–18 JULY','A week with room to breathe'); const days=[['Sun','12','Billie · 08:00','Charlie · 09:00'],['Mon','13','Milo · walk',''],['Tue','14','Billie · day care','Poppy · walk'],['Wed','15','Charlie · day care',''],['Thu','16','Billie · day care','Milo · walk'],['Fri','17','Poppy · half day',''],['Sat','18','Admin morning','']]; return `<div class="page-title-row"><div><h2>Bookings overview</h2><p>11 bookings · 76% of this week’s care capacity</p></div><button class="primary" id="new-booking">＋ New booking</button></div><div class="grid week">${days.map((d,i)=>`<div class="day ${i===0?'today':''}"><div class="day-head">${d[0]}<strong>${d[1]}</strong></div>${d[2]?`<div class="event">${d[2]}</div>`:''}${d[3]?`<div class="event peach">${d[3]}</div>`:''}</div>`).join('')}</div><section class="card" style="margin-top:25px"><div class="section-head" style="margin:0"><div><h2>Upcoming handovers</h2><p>Everything owners need before the doorbell rings</p></div></div><div class="today-list" style="margin-top:15px"><div class="booking"><time>17:30</time><div><h4>Billie Blue · pickup</h4><p>Story draft ready · lead and food tub packed</p></div><i class="dot"></i></div><div class="booking"><time>18:00</time><div><h4>Charlie Rose · pickup</h4><p>Add final rest update before handover</p></div><i class="dot peach"></i></div></div></section>`; },
  business() { setHeader('BUSINESS · JULY','A small business, clearly seen'); const bars=[46,58,51,72,63,79,86]; return `<div class="grid metrics"><div class="card metric"><small>REVENUE BOOKED</small><strong>€2,840</strong><span class="tag">↑ 13% vs June</span></div><div class="card metric"><small>NET AFTER EXPENSES</small><strong>€2,196</strong><span class="tag">77% margin</span></div><div class="card metric"><small>CARE HOURS</small><strong>94h</strong><span class="tag">€30.21 / hour</span></div><div class="card metric"><small>REPEAT OWNERS</small><strong>82%</strong><span class="tag">Healthy</span></div></div><div class="grid page-grid" style="margin-top:22px"><section class="card"><div class="section-head" style="margin-top:0"><div><h2>Revenue rhythm</h2><p>Last 7 months · demo data</p></div></div><div class="bar-chart">${bars.map((h,i)=>`<div class="bar ${i===6?'current':''}" style="height:${h}%"><span>${['Jan','Feb','Mar','Apr','May','Jun','Jul'][i]}</span></div>`).join('')}</div></section><aside class="card"><div class="section-head" style="margin-top:0"><div><h2>Recent expenses</h2><p>€644 this month</p></div><button class="link-button" id="add-expense">＋ Add</button></div><div class="expense-row"><div class="expense-icon">🦴</div><div><strong>Enrichment supplies</strong><small>Pet shop · 10 July</small></div><strong>€48</strong></div><div class="expense-row"><div class="expense-icon">🚙</div><div><strong>Fuel</strong><small>Travel · 8 July</small></div><strong>€72</strong></div><div class="expense-row"><div class="expense-icon">🛡</div><div><strong>Business insurance</strong><small>Monthly · 1 July</small></div><strong>€119</strong></div></aside></div>`; },
  settings() { setHeader('SETTINGS','Your calm corner'); return `<section class="card empty"><div class="big">⚙️</div><h2>Demo settings</h2><p>External integrations are intentionally unavailable in this local prototype.</p><button class="ghost" id="reset-demo">Reset demo observations</button></section>`; }
};

function infer(text) {
  const lower=text.toLowerCase(), tags=[];
  if(/eat|breakfast|lunch|dinner|food|drank|water/.test(lower)) tags.push('Nutrition');
  if(/walk|run|play|garden|outside/.test(lower)) tags.push('Activity');
  if(/stool|poo|sick|vomit|ear|paw|limp|medication/.test(lower)) tags.push('Health watch');
  if(/calm|settled|playful|anxious|vocal|recall/.test(lower)) tags.push('Behaviour');
  const time=text.match(/\b(?:[01]?\d|2[0-3]):[0-5]\d\b/); if(time) tags.push(`Time · ${time[0]}`);
  return tags.length?tags:['General care'];
}
function titleFrom(text,tags) { if(tags.includes('Health watch')) return 'Health & care observation'; if(tags.includes('Activity')) return 'Activity update'; if(tags.includes('Nutrition')) return 'Meal update'; return 'Care moment'; }
function discardAudioDraft() {
  audioDraft=null;
  const preview=document.querySelector('#audio-preview');
  if(preview) preview.innerHTML='';
  const status=document.querySelector('#recording-status');
  if(status) status.textContent='Recording discarded. Choose Record to make another voice note.';
}
function stopActiveRecording() {
  recordingSession++;
  recordingPending=false;
  clearInterval(recordingTimer);
  recordingTimer=null;
  const recorder=activeRecorder;
  activeRecorder=null;
  if(recorder && recorder.state!=='inactive') recorder.stop();
  activeAudioStream?.getTracks().forEach(track=>track.stop());
  activeAudioStream=null;
}
async function startAudioRecording() {
  const status=document.querySelector('#recording-status'), recordButton=document.querySelector('#record-audio'), stopButton=document.querySelector('#stop-audio'), duration=document.querySelector('#recording-duration');
  if(recordingPending || activeRecorder?.state==='recording') return;
  if(!navigator.mediaDevices?.getUserMedia || !window.MediaRecorder){ status.textContent='Voice recording is not available in this browser. You can still type and save the care update.'; recordButton.disabled=true; return; }
  recordingPending=true;
  recordButton.disabled=true;
  try {
    const stream=await navigator.mediaDevices.getUserMedia({audio:true});
    const session=++recordingSession;
    if(state.page!=='capture'){stream.getTracks().forEach(track=>track.stop());recordingPending=false;return;}
    activeAudioStream=stream;
    const chunks=[], started=Date.now();
    const recorder=new MediaRecorder(stream);
    activeRecorder=recorder;
    recorder.ondataavailable=event=>{if(event.data.size)chunks.push(event.data);};
    recorder.onerror=()=>{status.textContent='Recording stopped because the microphone became unavailable.';stopActiveRecording();};
    recorder.onstop=()=>{
      clearInterval(recordingTimer); stream.getTracks().forEach(track=>track.stop());
      activeAudioStream=null;
      const elapsed=Math.max(1,Math.round((Date.now()-started)/1000));
      const blob=new Blob(chunks,{type:recorder.mimeType || 'audio/webm'}), reader=new FileReader();
      reader.onload=()=>{if(session!==recordingSession)return;audioDraft={url:reader.result,duration:elapsed,type:blob.type};const preview=document.querySelector('#audio-preview');if(preview){preview.innerHTML=`${audioHtml(audioDraft,'Care update voice note')}<button class="link-button discard-audio" type="button" id="discard-audio">Discard recording</button>`;document.querySelector('#discard-audio').onclick=discardAudioDraft;status.textContent='Voice note ready. Play it back, discard it, or save it with the care update.';}};
      reader.readAsDataURL(blob); if(activeRecorder===recorder)activeRecorder=null; recordingPending=false; recordButton.disabled=false; recordButton.hidden=false; stopButton.hidden=true;
    };
    recordingPending=false; recordButton.disabled=false; recorder.start(); recordButton.hidden=true; stopButton.hidden=false; status.textContent='Recording… choose Stop when you are finished.'; duration.textContent='00:00';
    recordingTimer=setInterval(()=>{const seconds=(Date.now()-started)/1000;duration.textContent=formatDuration(seconds);if(seconds>=120 && activeRecorder?.state==='recording'){status.textContent='Two-minute limit reached. Preparing your voice note…';activeRecorder.stop();}},250);
  } catch(error) {
    recordingPending=false; recordButton.disabled=false;
    status.textContent=error?.name==='NotAllowedError' ? 'Microphone access was denied. You can allow it in browser settings or continue with a typed update.' : 'The microphone could not be started. You can continue with a typed update.';
  }
}
function readInviteForm() {
  const role = document.querySelector('input[name="invite-role"]:checked')?.value || 'owner';
  const name = document.querySelector('#invite-name')?.value.trim() || '';
  const email = document.querySelector('#invite-email')?.value.trim() || '';
  const permissions = [...document.querySelectorAll('input[name="invite-permission"]:checked')].map(input => input.value);
  return { role, name, email, permissions };
}
function updateInviteSummary() {
  const summary = document.querySelector('#invite-summary');
  if (!summary) return;
  const invite = readInviteForm();
  const firstName = invite.name || 'New contact';
  const permissionLabels = formatPermissions(invite.permissions);
  summary.innerHTML = `<div class="summary-person"><span>${invite.role === 'trusted-carer' ? '🤝' : '🏡'}</span><div><strong>${escapeHtml(firstName)}</strong><small>${escapeHtml(invite.email || 'Email needed before preview')}</small></div></div><div class="summary-line"><b>Role</b><span>${inviteRoleLabel(invite.role)}</span></div><div class="summary-line"><b>Shared care context</b><span>${permissionLabels.length ? permissionLabels.map(escapeHtml).join(', ') : 'Choose at least one area'}</span></div><div class="notice compact"><strong>Ready as a pending preview</strong>No delivery will happen from this demo. Review the summary with the sitter before copying anything elsewhere.</div>`;
}
function navigate(page) { if(page!=='capture')stopActiveRecording(); state.page=page; document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('active',n.dataset.page===page)); content.innerHTML=views[page](); localizeContent(); bindView(); document.querySelector('.sidebar').classList.remove('open'); window.scrollTo({top:0}); }
function bindView() {
  document.querySelectorAll('[data-go]').forEach(el=>el.onclick=()=>navigate(el.dataset.go));
  document.querySelectorAll('[data-dog]').forEach(el=>el.onclick=()=>{state.dog=el.dataset.dog;navigate('dogs')});
  document.querySelectorAll('[data-capture-dog]').forEach(el=>el.onclick=()=>{state.dog=el.dataset.captureDog;navigate('capture')});
  document.querySelectorAll('[data-story-dog]').forEach(el=>el.onclick=()=>{state.dog=el.dataset.storyDog;navigate('story')});
  const input=document.querySelector('#observation');
  if(input){
    input.oninput=()=>{const tags=infer(input.value);document.querySelector('#detected').innerHTML=input.value.trim()?tagsHtml(tags):'<em>Start typing to see structured care tags</em>';document.querySelector('#health-safety').hidden=!tags.includes('Health watch');};
    document.querySelector('#record-audio').onclick=startAudioRecording;
    document.querySelector('#stop-audio').onclick=()=>{if(activeRecorder?.state==='recording')activeRecorder.stop();};
    const discard=document.querySelector('#discard-audio'); if(discard)discard.onclick=discardAudioDraft;
    document.querySelector('#save-observation').onclick=()=>{const text=input.value.trim();if(!text){input.focus();showToast('Add a care update first');return}if(activeRecorder?.state==='recording'){showToast('Stop the recording before saving');return}const tags=infer(text), now=new Date();state.observations[state.dog].unshift({id:Date.now(),time:now.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}),date:'Today',title:titleFrom(text,tags),text,tags,audio:audioDraft});audioDraft=null;saveObservations();showToast(`Saved to ${dogs[state.dog].name}’s timeline`);navigate('dogs');};
  }
  const inviteButton=document.querySelector('#create-invite');
  if(inviteButton){
    document.querySelectorAll('input[name="invite-role"], input[name="invite-permission"], #invite-name, #invite-email').forEach(el=>el.addEventListener('input',updateInviteSummary));
    document.querySelectorAll('input[name="invite-role"], input[name="invite-permission"]').forEach(el=>el.addEventListener('change',updateInviteSummary));
    updateInviteSummary();
    inviteButton.onclick=()=>{const invite=readInviteForm();if(!invite.name){document.querySelector('#invite-name').focus();showToast('Add a name for the invite preview');return}if(!invite.email){document.querySelector('#invite-email').focus();showToast('Add an email for the invite preview');return}if(!invite.permissions.length){showToast('Choose at least one thing to share');return}state.invites.unshift({...invite,id:Date.now(),created:'Today'});saveInvites();document.querySelector('#pending-invites').innerHTML=pendingInvitesHtml();showToast('Pending invite preview created — nothing was sent');};
  }
  const preview=document.querySelector('#whatsapp-preview'); if(preview)preview.onclick=()=>showToast('WhatsApp preview only — nothing was sent');
  const vetCall=document.querySelector('#vet-call'); if(vetCall)vetCall.onclick=()=>showToast('Clinic call preview — verify contact details before calling');
  const vetVideo=document.querySelector('#vet-video'); if(vetVideo)vetVideo.onclick=()=>showToast('Video consult preview — no appointment or video call was created');
  document.querySelectorAll('.social-access').forEach(button=>button.onclick=()=>showToast(`${button.dataset.platform} access preview — no account connected or content posted`));
  const booking=document.querySelector('#new-booking'); if(booking)booking.onclick=()=>showToast('Booking creation is a demo preview');
  const expense=document.querySelector('#add-expense'); if(expense)expense.onclick=()=>showToast('Expense entry is a demo preview');
  const reset=document.querySelector('#reset-demo'); if(reset)reset.onclick=()=>{state.observations=structuredClone(baseObservations);saveObservations();showToast('Demo observations reset');navigate('dashboard');};
}
document.querySelectorAll('.nav-item[data-page]').forEach(el=>el.onclick=()=>navigate(el.dataset.page));
document.querySelectorAll('[data-route]').forEach(el=>el.onclick=e=>{e.preventDefault();navigate(el.dataset.route)});
document.querySelector('#mobile-menu').onclick=()=>document.querySelector('.sidebar').classList.toggle('open');
const languagePicker=document.querySelector('#language-picker');
languagePicker.value=state.language;
languagePicker.onchange=()=>{state.language=languagePicker.value;localStorage.setItem('dogcare-language',state.language);navigate(state.page);};
navigate('dashboard');

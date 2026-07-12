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

const dogs = {
  billie: { name: 'Billie Blue', emoji: '🐕‍🦺', age: 'Profile to complete', breed: 'Breed to confirm', owner: 'Arnaud Chrétien', last: '10:10 woodland walk', health: 'Radiograph recorded at Clinique Artémis. Add current care instructions.', behaviour: 'Add routine, triggers and favourite rewards.', vet: 'Clinique Artémis · Vet.Avenir (verify current contact)', colour: '' },
  charlie: { name: 'Charlie Rose', emoji: '🐶', age: 'Profile to complete', breed: 'Breed to confirm', owner: 'Arnaud Chrétien', last: '11:30 garden play', health: 'Add current health and medication instructions.', behaviour: 'Add routine, triggers and favourite rewards.', vet: 'Add preferred vet and emergency contact', colour: 'charlie' }
};

let state = { page: 'dashboard', dog: 'billie', observations: loadObservations() };
const content = document.querySelector('#app-content');
const title = document.querySelector('#page-title');
const eyebrow = document.querySelector('#page-eyebrow');

function loadObservations() {
  try { return JSON.parse(localStorage.getItem('dogcare-observations')) || structuredClone(baseObservations); }
  catch { return structuredClone(baseObservations); }
}
function saveObservations() { localStorage.setItem('dogcare-observations', JSON.stringify(state.observations)); }
function escapeHtml(value) { return value.replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function showToast(message) { const toast=document.querySelector('#toast'); toast.textContent=message; toast.classList.add('show'); setTimeout(()=>toast.classList.remove('show'),2500); }
function dogAvatar(key) { const d=dogs[key]; return `<div class="dog-avatar ${d.colour}">${d.emoji}</div>`; }
function setHeader(kicker, heading) { eyebrow.textContent=kicker; title.textContent=heading; }
function tagsHtml(tags) { return `<div class="mini-tags">${tags.map(t=>`<span>${escapeHtml(t)}</span>`).join('')}</div>`; }

const views = {
  dashboard() {
    setHeader('SUNDAY · 12 JULY', 'Good morning, Adine-Sophie');
    const latest = state.observations.billie[0];
    return `<div class="grid dashboard-grid"><div>
      <section class="card hero"><p class="eyebrow" style="color:#d6ed8c">TODAY AT A GLANCE</p><h2>Two happy dogs, one beautifully organised day.</h2><p>Billie and Charlie are both checked in. Capture the little moments now and their owner stories will write themselves.</p><button class="primary" data-go="capture">Add a care moment →</button></section>
      <div class="section-head"><div><h2>Your dogs today</h2><p>Live care context, always close by</p></div><button class="link-button" data-go="dogs">View profiles</button></div>
      <div class="dog-row">${Object.entries(dogs).map(([key,d])=>`<article class="card dog-card" data-dog="${key}">${dogAvatar(key)}<div class="dog-meta"><h3>${d.name}</h3><p>${d.breed} · ${d.owner}</p>${tagsHtml(key==='billie'?['Day care','All good']:['Day care','Settled'])}</div><span class="dog-arrow">›</span></article>`).join('')}</div>
      <div class="section-head"><div><h2>Latest from the care log</h2><p>Your newest structured observation</p></div></div>
      <article class="card timeline-card"><div class="timeline-top"><h4>${latest.title}</h4><time>${latest.time} · ${latest.date}</time></div><p>${latest.text}</p>${tagsHtml(latest.tags)}</article>
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
      <div class="section-head"><div><h2>Care timeline</h2><p>${obs.length} recorded moments</p></div></div><div class="timeline">${obs.map(o=>`<article class="card timeline-card"><div class="timeline-top"><h4>${o.title}</h4><time>${o.time} · ${o.date}</time></div><p>${o.text}</p>${tagsHtml(o.tags)}</article>`).join('')}</div>
    </div><aside><section class="card"><div class="section-head" style="margin-top:0"><div><h2>Care context</h2><p>Quick reference for every handover</p></div></div><div class="context-list"><div class="context"><strong>HEALTH</strong><p>${d.health}</p></div><div class="context behaviour"><strong>BEHAVIOUR</strong><p>${d.behaviour}</p></div><div class="context vet"><strong>VET & EMERGENCY</strong><p>${d.vet}</p></div></div><div class="facts"><div class="fact"><small>Food</small><strong>${key==='billie'?'120g · 2×':'85g · 2×'}</strong></div><div class="fact"><small>Walk</small><strong>${key==='billie'?'45 min':'25 min'}</strong></div><div class="fact"><small>Pickup</small><strong>${key==='billie'?'17:30':'18:00'}</strong></div></div></section><section class="card" style="margin-top:20px"><h3 style="font:400 20px Georgia,serif">Switch dog</h3><div class="dog-picker">${Object.entries(dogs).map(([k,x])=>`<button class="dog-pick ${k===key?'active':''}" data-dog="${k}"><span>${x.emoji}</span><div><strong>${x.name.split(' ')[0]}</strong><small>${x.age}</small></div></button>`).join('')}</div></section></aside></div>`;
  },
  capture() {
    const d=dogs[state.dog]; setHeader('RAPID CAPTURE', 'Capture the moment');
    return `<div class="page-title-row"><div><h2>What just happened?</h2><p>Write naturally. DogCare Brain will organise the useful details.</p></div></div><section class="card composer"><label class="label">Who is this about?</label><div class="dog-picker">${Object.entries(dogs).map(([k,x])=>`<button class="dog-pick ${k===state.dog?'active':''}" data-capture-dog="${k}"><span>${x.emoji}</span><div><strong>${x.name}</strong><small>${x.last}</small></div></button>`).join('')}</div><label class="label" for="observation">Care update</label><textarea id="observation" placeholder="Try: Ate all breakfast, playful with Mabel, loose stool at 10:30…"></textarea><label class="label">Detected details <small style="font-weight:400;text-transform:none;letter-spacing:0"> · updates as you type</small></label><div class="detected" id="detected"><em>Start typing to see structured care tags</em></div><div class="composer-actions"><small>AI structuring preview · This local demo uses on-device rules and sends no data anywhere.</small><button class="primary" id="save-observation">Save to ${d.name.split(' ')[0]}'s timeline →</button></div></section>`;
  },
  gallery() { setHeader('MEDIA LIBRARY','Little moments, safely kept'); const items=[['🐕‍🦺','Billie’s woodland walk','Today · 10:12'],['🐶','Charlie in the garden','Today · 11:34'],['🐾','Muddy-paw evidence','Yesterday · 16:45'],['🌿','The favourite sniff spot','10 July · 09:50'],['🦴','Enrichment time','9 July · 14:20'],['☁️','Post-walk snooze','8 July · 12:15']]; return `<div class="page-title-row"><div><h2>Care gallery</h2><p>Demo media placeholders attached to owner-ready stories.</p></div><button class="ghost" id="draft-instagram">Instagram draft preview</button></div><div class="grid media-grid">${items.map((x,i)=>`<article class="media-item"><div class="media-art">${x[0]}</div>${i<2?'<span class="draft-badge">Story ready</span>':''}<div class="media-copy"><strong>${x[1]}</strong><small>${x[2]}</small></div></article>`).join('')}</div>`; },
  story() { const d=dogs[state.dog], latest=state.observations[state.dog][0]; setHeader('OWNER UPDATE · DRAFT','A lovely day, ready to share'); return `<div class="grid page-grid"><div class="story-phone"><div class="story-image">${d.emoji}</div><div class="story-body"><p class="story-date">Sunday, 12 July · Daily story</p><h3>${d.name}’s day</h3><p class="story-copy">${latest.text} ${d.name.split(' ')[0]} enjoyed plenty of calm attention and is heading home happy and settled.</p><div class="story-stats"><div><strong>${state.dog==='billie'?'42 min':'25 min'}</strong><small>outside</small></div><div><strong>All eaten</strong><small>meals</small></div><div><strong>Calm</strong><small>mood</small></div></div></div></div><aside><section class="card"><h2 style="font:400 24px Georgia,serif">Owner-ready, not auto-sent</h2><p style="font-size:12px;color:var(--muted);line-height:1.6">Review this draft before sharing. In a future connected version, you could send it through WhatsApp or add it to an Instagram story.</p><label class="label">Preview for</label><div class="dog-picker">${Object.entries(dogs).map(([k,x])=>`<button class="dog-pick ${k===state.dog?'active':''}" data-story-dog="${k}"><span>${x.emoji}</span><div><strong>${x.name}</strong><small>${x.owner}</small></div></button>`).join('')}</div><button class="secondary" id="whatsapp-preview" style="width:100%;margin-top:20px">Preview WhatsApp message</button><p class="preview-note">Draft preview only · no message will be sent</p></section></aside></div>`; },
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
function navigate(page) { state.page=page; document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('active',n.dataset.page===page)); content.innerHTML=views[page](); bindView(); document.querySelector('.sidebar').classList.remove('open'); window.scrollTo({top:0}); }
function bindView() {
  document.querySelectorAll('[data-go]').forEach(el=>el.onclick=()=>navigate(el.dataset.go));
  document.querySelectorAll('[data-dog]').forEach(el=>el.onclick=()=>{state.dog=el.dataset.dog;navigate('dogs')});
  document.querySelectorAll('[data-capture-dog]').forEach(el=>el.onclick=()=>{state.dog=el.dataset.captureDog;navigate('capture')});
  document.querySelectorAll('[data-story-dog]').forEach(el=>el.onclick=()=>{state.dog=el.dataset.storyDog;navigate('story')});
  const input=document.querySelector('#observation');
  if(input){ input.oninput=()=>{const tags=infer(input.value);document.querySelector('#detected').innerHTML=input.value.trim()?tagsHtml(tags):'<em>Start typing to see structured care tags</em>';}; document.querySelector('#save-observation').onclick=()=>{const text=input.value.trim();if(!text){input.focus();showToast('Add a care update first');return}const tags=infer(text), now=new Date();state.observations[state.dog].unshift({id:Date.now(),time:now.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}),date:'Today',title:titleFrom(text,tags),text,tags});saveObservations();showToast(`Saved to ${dogs[state.dog].name}’s timeline`);navigate('dogs');}; }
  const preview=document.querySelector('#whatsapp-preview'); if(preview)preview.onclick=()=>showToast('WhatsApp preview only — nothing was sent');
  const insta=document.querySelector('#draft-instagram'); if(insta)insta.onclick=()=>showToast('Instagram draft preview — no account connected');
  const booking=document.querySelector('#new-booking'); if(booking)booking.onclick=()=>showToast('Booking creation is a demo preview');
  const expense=document.querySelector('#add-expense'); if(expense)expense.onclick=()=>showToast('Expense entry is a demo preview');
  const reset=document.querySelector('#reset-demo'); if(reset)reset.onclick=()=>{state.observations=structuredClone(baseObservations);saveObservations();showToast('Demo observations reset');navigate('dashboard');};
}
document.querySelectorAll('.nav-item[data-page]').forEach(el=>el.onclick=()=>navigate(el.dataset.page));
document.querySelectorAll('[data-route]').forEach(el=>el.onclick=e=>{e.preventDefault();navigate(el.dataset.route)});
document.querySelector('#mobile-menu').onclick=()=>document.querySelector('.sidebar').classList.toggle('open');
navigate('dashboard');

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
  billie: { name: 'Billie Blue', emoji: '🐕‍🦺', age: 'Profile to complete', breed: 'Breed to confirm', owner: 'Arnaud Chrétien', last: '10:10 woodland walk', health: 'Radiograph recorded at Clinique Artémis. Add current care instructions.', behaviour: 'Add routine, triggers and favourite rewards.', vet: 'Clinique Artémis · Vet.Avenir', vets: [{name:'Vet.Avenir', role:'Current clinic · verified public contact', phone:'+41223615540', video:'Clinic booking site'}, {name:'Clinique Artémis', role:'Radiograph history · contact to verify'}], needs: { energy: 'Confirm with owner', movement: 'Set a daily movement target', enrichment: 'Add favourite enrichment', sensitivities: 'Add sensitivities and recovery needs' }, colour: '' },
  charlie: { name: 'Charlie Rose', emoji: '🐶', age: 'Profile to complete', breed: 'Breed to confirm', owner: 'Arnaud Chrétien', last: '11:30 garden play', health: 'Add current health and medication instructions.', behaviour: 'Add routine, triggers and favourite rewards.', vet: 'Add preferred vet and emergency contact', vets: [], needs: { energy: 'Confirm with owner', movement: 'Set a daily movement target', enrichment: 'Add favourite enrichment', sensitivities: 'Add sensitivities and recovery needs' }, colour: 'charlie' }
};

// Localization dictionaries — keyed by the exact English source string.
// t(text) looks up translations[lang][text] and falls back to the English source.
// tf(text, params) does the same, then substitutes {token} placeholders (for word-order-safe interpolation).
// Keep every key byte-identical to the string passed to t()/tf() in the views (mind curly ’ vs straight ' apostrophes).
const translations = {
  en: {},
  fr: {
    // Navigation & chrome
    Today:'Aujourd’hui', Dogs:'Chiens', Capture:'Saisir', Gallery:'Galerie', 'Daily story':'Récit du jour', Schedule:'Planning', Business:'Activité', Settings:'Réglages', Invite:'Inviter',
    'All systems calm':'Tout est calme', 'Capture update':'Ajouter une note',
    // Headers (eyebrow · title)
    'SUNDAY · 12 JULY':'DIMANCHE · 12 JUILLET', 'Good morning, Adine-Sophie':'Bonjour, Adine-Sophie',
    'DOG PROFILE':'PROFIL DU CHIEN', 'RAPID CAPTURE':'SAISIE RAPIDE', 'Capture the moment':'Saisir le moment',
    'MEDIA LIBRARY':'MÉDIATHÈQUE', 'Little moments, safely kept':'De petits instants, précieusement gardés',
    'OWNER UPDATE · DRAFT':'MISE À JOUR PROPRIÉTAIRE · BROUILLON', 'A lovely day, ready to share':'Une belle journée, prête à partager',
    'INVITE PREVIEW':'APERÇU D’INVITATION', 'Share care context safely':'Partager le contexte de soin en toute sécurité',
    'SCHEDULE · 12–18 JULY':'PLANNING · 12–18 JUILLET', 'A week with room to breathe':'Une semaine qui laisse respirer',
    'BUSINESS · JULY':'ACTIVITÉ · JUILLET', 'A small business, clearly seen':'Une petite entreprise, clairement pilotée',
    SETTINGS:'RÉGLAGES', 'Your calm corner':'Votre coin de sérénité',
    // Dashboard
    'TODAY AT A GLANCE':'APERÇU DU JOUR',
    'Two happy dogs, one beautifully organised day.':'Deux chiens heureux, une journée bien organisée.',
    'Billie and Charlie are both checked in. Capture the little moments now and their owner stories will write themselves.':'Billie et Charlie sont bien arrivés. Notez les petits moments : leurs récits pour propriétaires se construiront naturellement.',
    'Add a care moment →':'Ajouter une note de soin →',
    'Your dogs today':'Vos chiens aujourd’hui', 'Live care context, always close by':'Le contexte de soin, toujours à portée de main', 'View profiles':'Voir les profils',
    'Latest from the care log':'Dernière note de soin', 'Your newest structured observation':'Votre dernière observation structurée',
    "Today's rhythm":'Le rythme du jour', '3 of 5 moments complete':'3 moments sur 5 terminés',
    arrival:'arrivée', 'Day care until':'Garde de jour jusqu’à', 'Lunch & quiet time':'Déjeuner & temps calme', 'Both dogs':'Les deux chiens',
    'Owner stories':'Récits pour les propriétaires', 'Prepare daily recaps':'Préparer les récits quotidiens',
    'July pulse':'Pouls de juillet', 'Business snapshot':'Aperçu de l’activité',
    'Revenue booked':'Chiffre d’affaires réservé', 'Capacity filled':'Capacité remplie', 'Healthy momentum':'Belle dynamique',
    'You’re €340 ahead of this point last month.':'Vous avez 340 € d’avance sur la même période le mois dernier.',
    // Dogs view
    'Care record':'Dossier de soin', 'Everything that helps {name} feel understood.':'Tout ce qui aide {name} à se sentir compris.',
    '＋ Add observation':'＋ Ajouter une observation', 'Owner:':'Propriétaire :',
    'Needs & lifestyle':'Besoins & mode de vie', 'Personalise these with the owner — not breed stereotypes.':'Personnalisez-les avec le propriétaire — pas selon des clichés de race.',
    Energy:'Énergie', Movement:'Mouvement', Enrichment:'Enrichissement', Sensitivities:'Sensibilités',
    'Care timeline':'Historique de soin', '{count} recorded moments':'{count} moments enregistrés',
    'Care insight':'Éclairage de soin', 'Evidence-based prompt · never a diagnosis':'Repère fondé sur les faits · jamais un diagnostic',
    'Care context':'Contexte de soin', 'Quick reference for every handover':'Repère rapide pour chaque relais',
    HEALTH:'SANTÉ', BEHAVIOUR:'COMPORTEMENT', 'VET & EMERGENCY':'VÉTÉRINAIRE & URGENCE',
    Food:'Alimentation', Walk:'Promenade', Pickup:'Récupération', 'Set with owner':'À définir avec le propriétaire',
    'Vet access':'Accès vétérinaire', 'Preview only · no clinic is contacted':'Aperçu uniquement · aucune clinique n’est contactée',
    'Call clinic':'Appeler la clinique', 'Video consult':'Consultation vidéo', 'Switch dog':'Changer de chien',
    // Care insight prompts
    'Repeated health observations':'Observations de santé répétées',
    '{count} health-related notes are in the recent record. This is a care prompt, not a diagnosis: review the notes with the owner and contact a vet if concerned.':'{count} notes liées à la santé figurent dans le dossier récent. Il s’agit d’un rappel de soin, pas d’un diagnostic : passez les notes en revue avec le propriétaire et contactez un vétérinaire en cas de doute.',
    'Health note recorded':'Note de santé enregistrée',
    'One health-related note is in the record. Keep observing and share the exact facts with the owner; this app does not diagnose.':'Une note liée à la santé figure au dossier. Continuez d’observer et partagez les faits exacts avec le propriétaire ; cette application ne pose pas de diagnostic.',
    'Routine context is building':'Le contexte de routine se construit',
    'Several activity observations are now linked to this dog. Add energy and enrichment targets to make future insights more personal.':'Plusieurs observations d’activité sont désormais liées à ce chien. Ajoutez des objectifs d’énergie et d’enrichissement pour des éclairages plus personnalisés.',
    'No pattern yet':'Aucune tendance pour l’instant',
    'Keep capturing small moments. Insights appear only when there is enough care history to support them.':'Continuez de noter les petits moments. Les éclairages n’apparaissent que lorsqu’un historique de soin suffisant les justifie.',
    // Tags
    Nutrition:'Nutrition', Medication:'Médication', 'Health check':'Contrôle de santé', Behaviour:'Comportement', Social:'Social', Training:'Éducation',
    Activity:'Activité', 'Health watch':'Vigilance santé', 'General care':'Soin général', Time:'Heure',
    'Mood · bright':'Humeur · rayonnante', 'Exercise · 42 min':'Exercice · 42 min', 'Behaviour · calm':'Comportement · calme', 'Mood · settled':'Humeur · apaisée',
    'Day care':'Garde de jour', 'All good':'Tout va bien', Settled:'Apaisé', 'Checked in':'Arrivé', 'Consent on file':'Accord enregistré',
    // Capture
    'What just happened?':'Que vient-il de se passer ?', 'Write naturally. DogCare Brain will organise the useful details.':'Écrivez naturellement. DogCare Brain organisera les détails utiles.',
    'Who is this about?':'Pour quel chien ?', 'Care update':'Note de soin',
    'Try: Ate all breakfast, playful with Mabel, loose stool at 10:30…':'Essayez : A mangé tout son petit-déjeuner, joueuse avec Mabel, selles molles à 10:30…',
    'Detected details':'Détails détectés', '· updates as you type':'· se met à jour à mesure que vous écrivez',
    'Start typing to see structured care tags':'Commencez à écrire pour voir les étiquettes structurées',
    'Health observations are factual notes, not diagnoses. Contact a veterinarian if concerned.':'Les observations de santé sont des notes factuelles, pas des diagnostics. Contactez un vétérinaire en cas de doute.',
    'AI structuring preview · This local demo uses on-device rules and sends no data anywhere.':'Aperçu de structuration IA · Cette démo locale n’envoie aucune donnée.',
    "Save to {name}'s timeline →":'Enregistrer dans le journal de {name} →',
    // Gallery
    'Care gallery':'Galerie de soin', 'Demo media placeholders attached to owner-ready stories.':'Médias de démonstration reliés à des récits prêts pour les propriétaires.',
    'Instagram draft preview':'Aperçu de brouillon Instagram', 'Story ready':'Récit prêt',
    'Billie’s woodland walk':'Balade en forêt de Billie', 'Today · 10:12':'Aujourd’hui · 10:12',
    'Charlie in the garden':'Charlie dans le jardin', 'Today · 11:34':'Aujourd’hui · 11:34',
    'Muddy-paw evidence':'Preuves de pattes boueuses', 'Yesterday · 16:45':'Hier · 16:45',
    'The favourite sniff spot':'Le coin de reniflage préféré', '10 July · 09:50':'10 juillet · 09:50',
    'Enrichment time':'Temps d’enrichissement', '9 July · 14:20':'9 juillet · 14:20',
    'Post-walk snooze':'Sieste d’après-balade', '8 July · 12:15':'8 juillet · 12:15',
    // Story
    'Sunday, 12 July · Daily story':'Dimanche 12 juillet · Récit du jour', '{name}’s day':'La journée de {name}',
    '{name} enjoyed plenty of calm attention and is heading home happy and settled.':'{name} a profité de beaucoup d’attention paisible et rentre à la maison heureux et apaisé.',
    outside:'dehors', meals:'repas', mood:'humeur', 'All eaten':'Tout mangé', Calm:'Calme',
    'Owner-ready, not auto-sent':'Prêt pour le propriétaire, jamais envoyé automatiquement',
    'Review this draft before sharing. In a future connected version, you could send it through WhatsApp or add it to an Instagram story.':'Relisez ce brouillon avant partage. Une future version connectée pourra préparer WhatsApp ou Instagram.',
    'Preview for':'Aperçu pour', 'Preview WhatsApp message':'Prévisualiser le message WhatsApp', 'Draft preview only · no message will be sent':'Brouillon uniquement · aucun message ne sera envoyé',
    // Invite
    'Prepare an invite':'Préparer une invitation', 'Build a local pending invite preview for an owner or trusted carer. Nothing is sent.':'Créez un aperçu d’invitation local, en attente, pour un propriétaire ou un aidant de confiance. Rien n’est envoyé.',
    'Invite role':'Rôle de l’invité', Owner:'Propriétaire', 'Family member who receives updates':'Membre de la famille qui reçoit les mises à jour',
    'Trusted carer':'Aidant de confiance', 'Backup helper with limited context':'Aide de secours avec un contexte limité',
    Name:'Nom', 'e.g. Camille Martin':'ex. : Camille Martin', Email:'E-mail', 'Can preview':'Peut consulter',
    'Daily stories':'Récits quotidiens', 'Owner-ready recaps and media placeholders':'Récapitulatifs prêts pour le propriétaire et médias de démonstration',
    'Structured observations and handover notes':'Observations structurées et notes de relais',
    'Health notes':'Notes de santé', 'Factual medication and watch items, never diagnoses':'Médications factuelles et points de vigilance, jamais de diagnostics',
    'Local preview only':'Aperçu local uniquement', 'This prototype will not send email, WhatsApp, SMS, or notifications.':'Ce prototype n’enverra ni e-mail, ni WhatsApp, ni SMS, ni notifications.',
    'Demo data only · the invite is stored in this browser as pending.':'Données de démonstration uniquement · l’invitation est stockée dans ce navigateur, en attente.',
    'Create pending invite preview →':'Créer l’aperçu d’invitation en attente →',
    'Invite-ready summary':'Récapitulatif prêt à inviter', 'Updates as you choose role and permissions':'Se met à jour selon le rôle et les autorisations choisis',
    'Pending invites':'Invitations en attente', 'Local preview queue':'File d’aperçus locaux',
    'No pending invites yet':'Aucune invitation en attente', 'Create a preview to see it queued here.':'Créez un aperçu pour le voir apparaître ici.',
    'Pending preview':'Aperçu en attente', 'New contact':'Nouveau contact', 'Email needed before preview':'E-mail requis avant l’aperçu',
    Role:'Rôle', 'Shared care context':'Contexte de soin partagé', 'Choose at least one area':'Choisissez au moins un domaine',
    'Ready as a pending preview':'Prêt comme aperçu en attente',
    'No delivery will happen from this demo. Review the summary with the sitter before copying anything elsewhere.':'Aucun envoi ne partira de cette démo. Passez le récapitulatif en revue avec la personne concernée avant de copier quoi que ce soit ailleurs.',
    // Schedule
    'Bookings overview':'Vue des réservations', '11 bookings · 76% of this week’s care capacity':'11 réservations · 76 % de la capacité de soin cette semaine', '＋ New booking':'＋ Nouvelle réservation',
    Sun:'Dim', Mon:'Lun', Tue:'Mar', Wed:'Mer', Thu:'Jeu', Fri:'Ven', Sat:'Sam',
    walk:'promenade', 'day care':'garde de jour', 'half day':'demi-journée', 'Admin morning':'Matinée administrative',
    'Upcoming handovers':'Prochains départs', 'Everything owners need before the doorbell rings':'Tout ce dont les propriétaires ont besoin avant la sonnette',
    pickup:'récupération', 'Story draft ready · lead and food tub packed':'Brouillon de récit prêt · laisse et boîte de nourriture préparées',
    'Add final rest update before handover':'Ajouter une dernière note de repos avant le départ',
    // Business
    'REVENUE BOOKED':'CA RÉSERVÉ', '↑ 13% vs June':'↑ 13 % vs juin', 'NET AFTER EXPENSES':'NET APRÈS FRAIS', '77% margin':'77 % de marge',
    'CARE HOURS':'HEURES DE SOIN', '€30.21 / hour':'30,21 € / heure', 'REPEAT OWNERS':'PROPRIÉTAIRES FIDÈLES', Healthy:'Sain',
    'Revenue rhythm':'Rythme du chiffre d’affaires', 'Last 7 months · demo data':'7 derniers mois · données de démonstration',
    Jan:'Jan', Feb:'Fév', Mar:'Mar', Apr:'Avr', May:'Mai', Jun:'Juin', Jul:'Juil',
    'Recent expenses':'Dépenses récentes', '€644 this month':'644 € ce mois-ci', '＋ Add':'＋ Ajouter',
    'Enrichment supplies':'Matériel d’enrichissement', 'Pet shop · 10 July':'Animalerie · 10 juillet',
    Fuel:'Carburant', 'Travel · 8 July':'Déplacement · 8 juillet',
    'Business insurance':'Assurance professionnelle', 'Monthly · 1 July':'Mensuel · 1er juillet',
    // Settings
    'Demo settings':'Réglages de démonstration', 'External integrations are intentionally unavailable in this local prototype.':'Les intégrations externes sont volontairement indisponibles dans ce prototype local.',
    'Reset demo observations':'Réinitialiser les observations de démonstration',
    // Toasts
    'Add a care update first':'Ajoutez d’abord une note de soin', 'Saved to {name}’s timeline':'Enregistré dans le journal de {name}',
    'Add a name for the invite preview':'Ajoutez un nom pour l’aperçu d’invitation', 'Add an email for the invite preview':'Ajoutez un e-mail pour l’aperçu d’invitation',
    'Choose at least one thing to share':'Choisissez au moins un élément à partager', 'Pending invite preview created — nothing was sent':'Aperçu d’invitation en attente créé — rien n’a été envoyé',
    'WhatsApp preview only — nothing was sent':'Aperçu WhatsApp uniquement — rien n’a été envoyé',
    'Clinic call preview — verify contact details before calling':'Aperçu d’appel à la clinique — vérifiez les coordonnées avant d’appeler',
    'Video consult preview — no appointment or video call was created':'Aperçu de consultation vidéo — aucun rendez-vous ni appel vidéo n’a été créé',
    'Instagram draft preview — no account connected':'Aperçu de brouillon Instagram — aucun compte connecté',
    'Booking creation is a demo preview':'La création de réservation est un aperçu de démonstration', 'Expense entry is a demo preview':'La saisie de dépense est un aperçu de démonstration',
    'Demo observations reset':'Observations de démonstration réinitialisées',
    // Observation titles from capture inference
    'Health & care observation':'Observation de santé & soin', 'Activity update':'Note d’activité', 'Meal update':'Note de repas', 'Care moment':'Moment de soin',
    // Seed observations
    'Breakfast & morning check-in':'Petit-déjeuner & point du matin',
    'Finished her full breakfast and drank well. Bright, relaxed and ready for the day.':'A terminé tout son petit-déjeuner et bien bu. Éveillée, détendue et prête pour la journée.',
    'Woodland walk':'Balade en forêt',
    'A calm 42-minute sniff walk. Good recall around two dogs and no stiffness noticed.':'Une balade reniflage tranquille de 42 minutes. Bon rappel auprès de deux chiens et aucune raideur remarquée.',
    'Evening medication':'Médication du soir',
    'Joint supplement given with dinner. Coat and paws checked after rain.':'Complément articulaire donné au dîner. Pelage et pattes vérifiés après la pluie.',
    'Settled into day care':'Bien installé en garde de jour',
    'A little vocal at drop-off, then settled on the green bed after five minutes.':'Un peu bruyant à l’arrivée, puis installé sur le lit vert après cinq minutes.',
    'Play session':'Séance de jeu',
    'Gentle play with Billie in the garden. Responded well to breaks and name cues.':'Jeu tout en douceur avec Billie dans le jardin. A bien réagi aux pauses et aux rappels de son nom.',
    Yesterday:'Hier',
    // Dog profile placeholder guidance
    'Profile to complete':'Profil à compléter', 'Breed to confirm':'Race à confirmer',
    'Radiograph recorded at Clinique Artémis. Add current care instructions.':'Radiographie enregistrée à la Clinique Artémis. Ajoutez les instructions de soin actuelles.',
    'Add current health and medication instructions.':'Ajoutez les instructions de santé et de médication actuelles.',
    'Add routine, triggers and favourite rewards.':'Ajoutez la routine, les déclencheurs et les récompenses préférées.',
    'Add preferred vet and emergency contact':'Ajoutez le vétérinaire préféré et le contact d’urgence',
    'Confirm with owner':'À confirmer avec le propriétaire', 'Set a daily movement target':'Définir un objectif de mouvement quotidien',
    'Add favourite enrichment':'Ajouter l’enrichissement préféré', 'Add sensitivities and recovery needs':'Ajouter les sensibilités et besoins de récupération',
    '10:10 woodland walk':'10:10 balade en forêt', '11:30 garden play':'11:30 jeu au jardin'
  },
  it: {
    Today:'Oggi', Dogs:'Cani', Capture:'Registra', Gallery:'Galleria', 'Daily story':'Racconto del giorno', Schedule:'Agenda', Business:'Attività', Settings:'Impostazioni', Invite:'Invita',
    'All systems calm':'Tutto è tranquillo', 'Capture update':'Aggiungi nota',
    'SUNDAY · 12 JULY':'DOMENICA · 12 LUGLIO', 'Good morning, Adine-Sophie':'Buongiorno, Adine-Sophie',
    'DOG PROFILE':'PROFILO DEL CANE', 'RAPID CAPTURE':'REGISTRAZIONE RAPIDA', 'Capture the moment':'Cattura il momento',
    'MEDIA LIBRARY':'LIBRERIA MULTIMEDIALE', 'Little moments, safely kept':'Piccoli momenti, custoditi con cura',
    'OWNER UPDATE · DRAFT':'AGGIORNAMENTO PROPRIETARIO · BOZZA', 'A lovely day, ready to share':'Una bella giornata, pronta da condividere',
    'INVITE PREVIEW':'ANTEPRIMA INVITO', 'Share care context safely':'Condividi il contesto di cura in sicurezza',
    'SCHEDULE · 12–18 JULY':'AGENDA · 12–18 LUGLIO', 'A week with room to breathe':'Una settimana con spazio per respirare',
    'BUSINESS · JULY':'ATTIVITÀ · LUGLIO', 'A small business, clearly seen':'Una piccola attività, gestita con chiarezza',
    SETTINGS:'IMPOSTAZIONI', 'Your calm corner':'Il tuo angolo di calma',
    'TODAY AT A GLANCE':'PANORAMICA DI OGGI',
    'Two happy dogs, one beautifully organised day.':'Due cani felici, una giornata ben organizzata.',
    'Billie and Charlie are both checked in. Capture the little moments now and their owner stories will write themselves.':'Billie e Charlie sono entrambi arrivati. Annota ora i piccoli momenti: i racconti per i proprietari si scriveranno da soli.',
    'Add a care moment →':'Aggiungi un momento di cura →',
    'Your dogs today':'I tuoi cani oggi', 'Live care context, always close by':'Il contesto di cura, sempre a portata di mano', 'View profiles':'Vedi profili',
    'Latest from the care log':'Ultima nota di cura', 'Your newest structured observation':'La tua osservazione strutturata più recente',
    "Today's rhythm":'Il ritmo di oggi', '3 of 5 moments complete':'3 momenti su 5 completati',
    arrival:'arrivo', 'Day care until':'Asilo diurno fino alle', 'Lunch & quiet time':'Pranzo & momento tranquillo', 'Both dogs':'Entrambi i cani',
    'Owner stories':'Racconti per i proprietari', 'Prepare daily recaps':'Prepara i riepiloghi giornalieri',
    'July pulse':'Andamento di luglio', 'Business snapshot':'Panoramica attività',
    'Revenue booked':'Ricavi registrati', 'Capacity filled':'Capacità riempita', 'Healthy momentum':'Buon slancio',
    'You’re €340 ahead of this point last month.':'Sei in vantaggio di 340 € rispetto allo stesso punto del mese scorso.',
    'Care record':'Scheda di cura', 'Everything that helps {name} feel understood.':'Tutto ciò che aiuta {name} a sentirsi capito.',
    '＋ Add observation':'＋ Aggiungi osservazione', 'Owner:':'Proprietario:',
    'Needs & lifestyle':'Bisogni & stile di vita', 'Personalise these with the owner — not breed stereotypes.':'Personalizzali con il proprietario — non con stereotipi di razza.',
    Energy:'Energia', Movement:'Movimento', Enrichment:'Arricchimento', Sensitivities:'Sensibilità',
    'Care timeline':'Cronologia di cura', '{count} recorded moments':'{count} momenti registrati',
    'Care insight':'Spunto di cura', 'Evidence-based prompt · never a diagnosis':'Indicazione basata sui fatti · mai una diagnosi',
    'Care context':'Contesto di cura', 'Quick reference for every handover':'Riferimento rapido per ogni consegna',
    HEALTH:'SALUTE', BEHAVIOUR:'COMPORTAMENTO', 'VET & EMERGENCY':'VETERINARIO & EMERGENZA',
    Food:'Alimentazione', Walk:'Passeggiata', Pickup:'Ritiro', 'Set with owner':'Da definire con il proprietario',
    'Vet access':'Accesso veterinario', 'Preview only · no clinic is contacted':'Solo anteprima · nessuna clinica viene contattata',
    'Call clinic':'Chiama la clinica', 'Video consult':'Consulto video', 'Switch dog':'Cambia cane',
    'Repeated health observations':'Osservazioni di salute ripetute',
    '{count} health-related notes are in the recent record. This is a care prompt, not a diagnosis: review the notes with the owner and contact a vet if concerned.':'Nella scheda recente ci sono {count} note legate alla salute. È un promemoria di cura, non una diagnosi: rivedi le note con il proprietario e contatta un veterinario in caso di dubbio.',
    'Health note recorded':'Nota di salute registrata',
    'One health-related note is in the record. Keep observing and share the exact facts with the owner; this app does not diagnose.':'Nella scheda c’è una nota legata alla salute. Continua a osservare e condividi i fatti esatti con il proprietario; questa app non fa diagnosi.',
    'Routine context is building':'Il contesto della routine sta prendendo forma',
    'Several activity observations are now linked to this dog. Add energy and enrichment targets to make future insights more personal.':'Diverse osservazioni di attività sono ora collegate a questo cane. Aggiungi obiettivi di energia e arricchimento per spunti futuri più personali.',
    'No pattern yet':'Ancora nessuno schema',
    'Keep capturing small moments. Insights appear only when there is enough care history to support them.':'Continua a registrare i piccoli momenti. Gli spunti compaiono solo quando c’è una storia di cura sufficiente a sostenerli.',
    Nutrition:'Nutrizione', Medication:'Farmaci', 'Health check':'Controllo di salute', Behaviour:'Comportamento', Social:'Socialità', Training:'Addestramento',
    Activity:'Attività', 'Health watch':'Attenzione salute', 'General care':'Cura generale', Time:'Ora',
    'Mood · bright':'Umore · brillante', 'Exercise · 42 min':'Esercizio · 42 min', 'Behaviour · calm':'Comportamento · calmo', 'Mood · settled':'Umore · tranquillo',
    'Day care':'Asilo diurno', 'All good':'Tutto bene', Settled:'Tranquillo', 'Checked in':'Arrivato', 'Consent on file':'Consenso registrato',
    'What just happened?':'Cosa è appena successo?', 'Write naturally. DogCare Brain will organise the useful details.':'Scrivi in modo naturale. DogCare Brain organizzerà i dettagli utili.',
    'Who is this about?':'Di chi si tratta?', 'Care update':'Aggiornamento cura',
    'Try: Ate all breakfast, playful with Mabel, loose stool at 10:30…':'Prova: Ha mangiato tutta la colazione, giocosa con Mabel, feci molli alle 10:30…',
    'Detected details':'Dettagli rilevati', '· updates as you type':'· si aggiorna mentre scrivi',
    'Start typing to see structured care tags':'Inizia a scrivere per vedere le etichette di cura strutturate',
    'Health observations are factual notes, not diagnoses. Contact a veterinarian if concerned.':'Le osservazioni di salute sono note fattuali, non diagnosi. Contatta un veterinario in caso di dubbio.',
    'AI structuring preview · This local demo uses on-device rules and sends no data anywhere.':'Anteprima di strutturazione IA · Questa demo locale usa regole sul dispositivo e non invia alcun dato.',
    "Save to {name}'s timeline →":'Salva nella cronologia di {name} →',
    'Care gallery':'Galleria di cura', 'Demo media placeholders attached to owner-ready stories.':'Media dimostrativi collegati a racconti pronti per i proprietari.',
    'Instagram draft preview':'Anteprima bozza Instagram', 'Story ready':'Racconto pronto',
    'Billie’s woodland walk':'Passeggiata nel bosco di Billie', 'Today · 10:12':'Oggi · 10:12',
    'Charlie in the garden':'Charlie in giardino', 'Today · 11:34':'Oggi · 11:34',
    'Muddy-paw evidence':'Prove di zampe fangose', 'Yesterday · 16:45':'Ieri · 16:45',
    'The favourite sniff spot':'Il posto preferito per annusare', '10 July · 09:50':'10 luglio · 09:50',
    'Enrichment time':'Momento di arricchimento', '9 July · 14:20':'9 luglio · 14:20',
    'Post-walk snooze':'Pisolino dopo la passeggiata', '8 July · 12:15':'8 luglio · 12:15',
    'Sunday, 12 July · Daily story':'Domenica 12 luglio · Racconto del giorno', '{name}’s day':'La giornata di {name}',
    '{name} enjoyed plenty of calm attention and is heading home happy and settled.':'{name} ha goduto di tante attenzioni tranquille e torna a casa felice e sereno.',
    outside:'all’aperto', meals:'pasti', mood:'umore', 'All eaten':'Tutto mangiato', Calm:'Calmo',
    'Owner-ready, not auto-sent':'Pronto per il proprietario, mai inviato in automatico',
    'Review this draft before sharing. In a future connected version, you could send it through WhatsApp or add it to an Instagram story.':'Rivedi questa bozza prima di condividerla. In una futura versione connessa potresti inviarla tramite WhatsApp o aggiungerla a una storia Instagram.',
    'Preview for':'Anteprima per', 'Preview WhatsApp message':'Anteprima messaggio WhatsApp', 'Draft preview only · no message will be sent':'Solo anteprima bozza · nessun messaggio verrà inviato',
    'Prepare an invite':'Prepara un invito', 'Build a local pending invite preview for an owner or trusted carer. Nothing is sent.':'Crea un’anteprima locale di invito, in attesa, per un proprietario o un aiutante di fiducia. Non viene inviato nulla.',
    'Invite role':'Ruolo dell’invitato', Owner:'Proprietario', 'Family member who receives updates':'Familiare che riceve gli aggiornamenti',
    'Trusted carer':'Aiutante di fiducia', 'Backup helper with limited context':'Aiutante di riserva con contesto limitato',
    Name:'Nome', 'e.g. Camille Martin':'es. Camille Martin', Email:'E-mail', 'Can preview':'Può visualizzare',
    'Daily stories':'Racconti giornalieri', 'Owner-ready recaps and media placeholders':'Riepiloghi pronti per il proprietario e media dimostrativi',
    'Structured observations and handover notes':'Osservazioni strutturate e note di consegna',
    'Health notes':'Note di salute', 'Factual medication and watch items, never diagnoses':'Farmaci fattuali e punti da monitorare, mai diagnosi',
    'Local preview only':'Solo anteprima locale', 'This prototype will not send email, WhatsApp, SMS, or notifications.':'Questo prototipo non invierà e-mail, WhatsApp, SMS o notifiche.',
    'Demo data only · the invite is stored in this browser as pending.':'Solo dati dimostrativi · l’invito è salvato in questo browser come in attesa.',
    'Create pending invite preview →':'Crea l’anteprima di invito in attesa →',
    'Invite-ready summary':'Riepilogo pronto per l’invito', 'Updates as you choose role and permissions':'Si aggiorna man mano che scegli ruolo e permessi',
    'Pending invites':'Inviti in attesa', 'Local preview queue':'Coda di anteprime locali',
    'No pending invites yet':'Ancora nessun invito in attesa', 'Create a preview to see it queued here.':'Crea un’anteprima per vederla in coda qui.',
    'Pending preview':'Anteprima in attesa', 'New contact':'Nuovo contatto', 'Email needed before preview':'E-mail necessaria prima dell’anteprima',
    Role:'Ruolo', 'Shared care context':'Contesto di cura condiviso', 'Choose at least one area':'Scegli almeno un’area',
    'Ready as a pending preview':'Pronto come anteprima in attesa',
    'No delivery will happen from this demo. Review the summary with the sitter before copying anything elsewhere.':'Da questa demo non partirà alcun invio. Rivedi il riepilogo con la persona interessata prima di copiare qualsiasi cosa altrove.',
    'Bookings overview':'Panoramica prenotazioni', '11 bookings · 76% of this week’s care capacity':'11 prenotazioni · 76% della capacità di cura di questa settimana', '＋ New booking':'＋ Nuova prenotazione',
    Sun:'Dom', Mon:'Lun', Tue:'Mar', Wed:'Mer', Thu:'Gio', Fri:'Ven', Sat:'Sab',
    walk:'passeggiata', 'day care':'asilo diurno', 'half day':'mezza giornata', 'Admin morning':'Mattinata amministrativa',
    'Upcoming handovers':'Prossime consegne', 'Everything owners need before the doorbell rings':'Tutto ciò che serve ai proprietari prima che suoni il campanello',
    pickup:'ritiro', 'Story draft ready · lead and food tub packed':'Bozza del racconto pronta · guinzaglio e contenitore del cibo preparati',
    'Add final rest update before handover':'Aggiungi un’ultima nota sul riposo prima della consegna',
    'REVENUE BOOKED':'RICAVI REGISTRATI', '↑ 13% vs June':'↑ 13% vs giugno', 'NET AFTER EXPENSES':'NETTO DOPO LE SPESE', '77% margin':'77% di margine',
    'CARE HOURS':'ORE DI CURA', '€30.21 / hour':'30,21 € / ora', 'REPEAT OWNERS':'PROPRIETARI ABITUALI', Healthy:'Sano',
    'Revenue rhythm':'Ritmo dei ricavi', 'Last 7 months · demo data':'Ultimi 7 mesi · dati dimostrativi',
    Jan:'Gen', Feb:'Feb', Mar:'Mar', Apr:'Apr', May:'Mag', Jun:'Giu', Jul:'Lug',
    'Recent expenses':'Spese recenti', '€644 this month':'644 € questo mese', '＋ Add':'＋ Aggiungi',
    'Enrichment supplies':'Materiale di arricchimento', 'Pet shop · 10 July':'Negozio per animali · 10 luglio',
    Fuel:'Carburante', 'Travel · 8 July':'Trasferta · 8 luglio',
    'Business insurance':'Assicurazione professionale', 'Monthly · 1 July':'Mensile · 1 luglio',
    'Demo settings':'Impostazioni dimostrative', 'External integrations are intentionally unavailable in this local prototype.':'Le integrazioni esterne sono volutamente non disponibili in questo prototipo locale.',
    'Reset demo observations':'Reimposta le osservazioni dimostrative',
    'Add a care update first':'Aggiungi prima una nota di cura', 'Saved to {name}’s timeline':'Salvato nella cronologia di {name}',
    'Add a name for the invite preview':'Aggiungi un nome per l’anteprima dell’invito', 'Add an email for the invite preview':'Aggiungi un’e-mail per l’anteprima dell’invito',
    'Choose at least one thing to share':'Scegli almeno un elemento da condividere', 'Pending invite preview created — nothing was sent':'Anteprima di invito in attesa creata — non è stato inviato nulla',
    'WhatsApp preview only — nothing was sent':'Solo anteprima WhatsApp — non è stato inviato nulla',
    'Clinic call preview — verify contact details before calling':'Anteprima di chiamata alla clinica — verifica i recapiti prima di chiamare',
    'Video consult preview — no appointment or video call was created':'Anteprima di consulto video — nessun appuntamento o videochiamata è stato creato',
    'Instagram draft preview — no account connected':'Anteprima bozza Instagram — nessun account collegato',
    'Booking creation is a demo preview':'La creazione di prenotazioni è un’anteprima dimostrativa', 'Expense entry is a demo preview':'La registrazione delle spese è un’anteprima dimostrativa',
    'Demo observations reset':'Osservazioni dimostrative reimpostate',
    'Health & care observation':'Osservazione di salute & cura', 'Activity update':'Nota di attività', 'Meal update':'Nota sul pasto', 'Care moment':'Momento di cura',
    'Breakfast & morning check-in':'Colazione & controllo mattutino',
    'Finished her full breakfast and drank well. Bright, relaxed and ready for the day.':'Ha finito tutta la colazione e ha bevuto bene. Vivace, rilassata e pronta per la giornata.',
    'Woodland walk':'Passeggiata nel bosco',
    'A calm 42-minute sniff walk. Good recall around two dogs and no stiffness noticed.':'Una tranquilla passeggiata annusa-annusa di 42 minuti. Buon richiamo vicino a due cani e nessuna rigidità notata.',
    'Evening medication':'Farmaci della sera',
    'Joint supplement given with dinner. Coat and paws checked after rain.':'Integratore per le articolazioni dato a cena. Pelo e zampe controllati dopo la pioggia.',
    'Settled into day care':'Ben ambientato all’asilo diurno',
    'A little vocal at drop-off, then settled on the green bed after five minutes.':'Un po’ vocale all’arrivo, poi sistemato sul lettino verde dopo cinque minuti.',
    'Play session':'Sessione di gioco',
    'Gentle play with Billie in the garden. Responded well to breaks and name cues.':'Gioco delicato con Billie in giardino. Ha risposto bene alle pause e ai richiami del nome.',
    Yesterday:'Ieri',
    'Profile to complete':'Profilo da completare', 'Breed to confirm':'Razza da confermare',
    'Radiograph recorded at Clinique Artémis. Add current care instructions.':'Radiografia registrata alla Clinique Artémis. Aggiungi le istruzioni di cura attuali.',
    'Add current health and medication instructions.':'Aggiungi le istruzioni attuali di salute e farmaci.',
    'Add routine, triggers and favourite rewards.':'Aggiungi routine, fattori scatenanti e premi preferiti.',
    'Add preferred vet and emergency contact':'Aggiungi il veterinario preferito e il contatto di emergenza',
    'Confirm with owner':'Da confermare con il proprietario', 'Set a daily movement target':'Imposta un obiettivo di movimento giornaliero',
    'Add favourite enrichment':'Aggiungi l’arricchimento preferito', 'Add sensitivities and recovery needs':'Aggiungi sensibilità ed esigenze di recupero',
    '10:10 woodland walk':'10:10 passeggiata nel bosco', '11:30 garden play':'11:30 gioco in giardino'
  },
  de: {
    Today:'Heute', Dogs:'Hunde', Capture:'Erfassen', Gallery:'Galerie', 'Daily story':'Tagesbericht', Schedule:'Planung', Business:'Betrieb', Settings:'Einstellungen', Invite:'Einladen',
    'All systems calm':'Alles im grünen Bereich', 'Capture update':'Notiz erfassen',
    'SUNDAY · 12 JULY':'SONNTAG · 12. JULI', 'Good morning, Adine-Sophie':'Guten Morgen, Adine-Sophie',
    'DOG PROFILE':'HUNDEPROFIL', 'RAPID CAPTURE':'SCHNELLE ERFASSUNG', 'Capture the moment':'Moment erfassen',
    'MEDIA LIBRARY':'MEDIENBIBLIOTHEK', 'Little moments, safely kept':'Kleine Momente, sicher bewahrt',
    'OWNER UPDATE · DRAFT':'BESITZER-UPDATE · ENTWURF', 'A lovely day, ready to share':'Ein schöner Tag, bereit zum Teilen',
    'INVITE PREVIEW':'EINLADUNGS-VORSCHAU', 'Share care context safely':'Pflegekontext sicher teilen',
    'SCHEDULE · 12–18 JULY':'PLANUNG · 12.–18. JULI', 'A week with room to breathe':'Eine Woche mit Raum zum Durchatmen',
    'BUSINESS · JULY':'BETRIEB · JULI', 'A small business, clearly seen':'Ein kleines Unternehmen, klar im Blick',
    SETTINGS:'EINSTELLUNGEN', 'Your calm corner':'Ihre ruhige Ecke',
    'TODAY AT A GLANCE':'HEUTE IM ÜBERBLICK',
    'Two happy dogs, one beautifully organised day.':'Zwei glückliche Hunde, ein bestens organisierter Tag.',
    'Billie and Charlie are both checked in. Capture the little moments now and their owner stories will write themselves.':'Billie und Charlie sind beide angekommen. Halten Sie jetzt die kleinen Momente fest, und die Berichte für die Besitzer schreiben sich von selbst.',
    'Add a care moment →':'Pflegemoment hinzufügen →',
    'Your dogs today':'Ihre Hunde heute', 'Live care context, always close by':'Der Pflegekontext, immer griffbereit', 'View profiles':'Profile ansehen',
    'Latest from the care log':'Neuester Pflegeeintrag', 'Your newest structured observation':'Ihre neueste strukturierte Beobachtung',
    "Today's rhythm":'Der Tagesablauf', '3 of 5 moments complete':'3 von 5 Momenten erledigt',
    arrival:'Ankunft', 'Day care until':'Tagesbetreuung bis', 'Lunch & quiet time':'Mittag & Ruhezeit', 'Both dogs':'Beide Hunde',
    'Owner stories':'Berichte für Besitzer', 'Prepare daily recaps':'Tägliche Rückblicke vorbereiten',
    'July pulse':'Juli-Puls', 'Business snapshot':'Betriebsübersicht',
    'Revenue booked':'Gebuchter Umsatz', 'Capacity filled':'Auslastung', 'Healthy momentum':'Gesunde Dynamik',
    'You’re €340 ahead of this point last month.':'Sie liegen 340 € vor dem gleichen Zeitpunkt im Vormonat.',
    'Care record':'Pflegeakte', 'Everything that helps {name} feel understood.':'Alles, was {name} hilft, sich verstanden zu fühlen.',
    '＋ Add observation':'＋ Beobachtung hinzufügen', 'Owner:':'Besitzer:',
    'Needs & lifestyle':'Bedürfnisse & Lebensstil', 'Personalise these with the owner — not breed stereotypes.':'Stimmen Sie diese mit dem Besitzer ab — nicht anhand von Rasseklischees.',
    Energy:'Energie', Movement:'Bewegung', Enrichment:'Beschäftigung', Sensitivities:'Empfindlichkeiten',
    'Care timeline':'Pflegeverlauf', '{count} recorded moments':'{count} erfasste Momente',
    'Care insight':'Pflegehinweis', 'Evidence-based prompt · never a diagnosis':'Faktenbasierter Hinweis · niemals eine Diagnose',
    'Care context':'Pflegekontext', 'Quick reference for every handover':'Schnellreferenz für jede Übergabe',
    HEALTH:'GESUNDHEIT', BEHAVIOUR:'VERHALTEN', 'VET & EMERGENCY':'TIERARZT & NOTFALL',
    Food:'Futter', Walk:'Spaziergang', Pickup:'Abholung', 'Set with owner':'Mit Besitzer festlegen',
    'Vet access':'Tierarzt-Zugang', 'Preview only · no clinic is contacted':'Nur Vorschau · keine Klinik wird kontaktiert',
    'Call clinic':'Klinik anrufen', 'Video consult':'Videosprechstunde', 'Switch dog':'Hund wechseln',
    'Repeated health observations':'Wiederholte Gesundheitsbeobachtungen',
    '{count} health-related notes are in the recent record. This is a care prompt, not a diagnosis: review the notes with the owner and contact a vet if concerned.':'Es liegen {count} gesundheitsbezogene Notizen im jüngsten Verlauf vor. Das ist ein Pflegehinweis, keine Diagnose: Gehen Sie die Notizen mit dem Besitzer durch und kontaktieren Sie bei Bedenken einen Tierarzt.',
    'Health note recorded':'Gesundheitsnotiz erfasst',
    'One health-related note is in the record. Keep observing and share the exact facts with the owner; this app does not diagnose.':'Eine gesundheitsbezogene Notiz liegt im Verlauf vor. Beobachten Sie weiter und teilen Sie dem Besitzer die genauen Fakten mit; diese App stellt keine Diagnose.',
    'Routine context is building':'Der Routinekontext entsteht',
    'Several activity observations are now linked to this dog. Add energy and enrichment targets to make future insights more personal.':'Mehrere Aktivitätsbeobachtungen sind nun mit diesem Hund verknüpft. Ergänzen Sie Energie- und Beschäftigungsziele für persönlichere künftige Hinweise.',
    'No pattern yet':'Noch kein Muster',
    'Keep capturing small moments. Insights appear only when there is enough care history to support them.':'Erfassen Sie weiterhin kleine Momente. Hinweise erscheinen erst, wenn genügend Pflegehistorie sie stützt.',
    Nutrition:'Ernährung', Medication:'Medikation', 'Health check':'Gesundheitscheck', Behaviour:'Verhalten', Social:'Sozialverhalten', Training:'Training',
    Activity:'Aktivität', 'Health watch':'Gesundheits-Beobachtung', 'General care':'Allgemeine Pflege', Time:'Uhrzeit',
    'Mood · bright':'Stimmung · aufgeweckt', 'Exercise · 42 min':'Bewegung · 42 Min.', 'Behaviour · calm':'Verhalten · ruhig', 'Mood · settled':'Stimmung · ausgeglichen',
    'Day care':'Tagesbetreuung', 'All good':'Alles gut', Settled:'Ausgeglichen', 'Checked in':'Angekommen', 'Consent on file':'Einwilligung hinterlegt',
    'What just happened?':'Was ist gerade passiert?', 'Write naturally. DogCare Brain will organise the useful details.':'Schreiben Sie ganz natürlich. DogCare Brain ordnet die nützlichen Details.',
    'Who is this about?':'Um wen geht es?', 'Care update':'Pflege-Update',
    'Try: Ate all breakfast, playful with Mabel, loose stool at 10:30…':'Beispiel: Hat das ganze Frühstück gefressen, verspielt mit Mabel, weicher Stuhl um 10:30…',
    'Detected details':'Erkannte Details', '· updates as you type':'· aktualisiert sich während der Eingabe',
    'Start typing to see structured care tags':'Beginnen Sie zu tippen, um strukturierte Pflege-Tags zu sehen',
    'Health observations are factual notes, not diagnoses. Contact a veterinarian if concerned.':'Gesundheitsbeobachtungen sind sachliche Notizen, keine Diagnosen. Kontaktieren Sie bei Bedenken einen Tierarzt.',
    'AI structuring preview · This local demo uses on-device rules and sends no data anywhere.':'KI-Strukturierungsvorschau · Diese lokale Demo nutzt Regeln auf dem Gerät und sendet keine Daten.',
    "Save to {name}'s timeline →":'In {name}s Verlauf speichern →',
    'Care gallery':'Pflegegalerie', 'Demo media placeholders attached to owner-ready stories.':'Demo-Medien, verknüpft mit besitzerfertigen Berichten.',
    'Instagram draft preview':'Instagram-Entwurfsvorschau', 'Story ready':'Bericht bereit',
    'Billie’s woodland walk':'Billies Waldspaziergang', 'Today · 10:12':'Heute · 10:12',
    'Charlie in the garden':'Charlie im Garten', 'Today · 11:34':'Heute · 11:34',
    'Muddy-paw evidence':'Beweise schlammiger Pfoten', 'Yesterday · 16:45':'Gestern · 16:45',
    'The favourite sniff spot':'Der liebste Schnüffelplatz', '10 July · 09:50':'10. Juli · 09:50',
    'Enrichment time':'Beschäftigungszeit', '9 July · 14:20':'9. Juli · 14:20',
    'Post-walk snooze':'Nickerchen nach dem Spaziergang', '8 July · 12:15':'8. Juli · 12:15',
    'Sunday, 12 July · Daily story':'Sonntag, 12. Juli · Tagesbericht', '{name}’s day':'{name}s Tag',
    '{name} enjoyed plenty of calm attention and is heading home happy and settled.':'{name} hat viel ruhige Zuwendung genossen und geht glücklich und ausgeglichen nach Hause.',
    outside:'draußen', meals:'Mahlzeiten', mood:'Stimmung', 'All eaten':'Alles gefressen', Calm:'Ruhig',
    'Owner-ready, not auto-sent':'Bereit für den Besitzer, nicht automatisch gesendet',
    'Review this draft before sharing. In a future connected version, you could send it through WhatsApp or add it to an Instagram story.':'Prüfen Sie diesen Entwurf vor dem Teilen. In einer künftigen vernetzten Version könnten Sie ihn per WhatsApp senden oder zu einer Instagram-Story hinzufügen.',
    'Preview for':'Vorschau für', 'Preview WhatsApp message':'WhatsApp-Nachricht vorschauen', 'Draft preview only · no message will be sent':'Nur Entwurfsvorschau · es wird keine Nachricht gesendet',
    'Prepare an invite':'Einladung vorbereiten', 'Build a local pending invite preview for an owner or trusted carer. Nothing is sent.':'Erstellen Sie eine lokale, ausstehende Einladungsvorschau für einen Besitzer oder eine Vertrauensperson. Es wird nichts gesendet.',
    'Invite role':'Einladungsrolle', Owner:'Besitzer', 'Family member who receives updates':'Familienmitglied, das Updates erhält',
    'Trusted carer':'Vertrauensperson', 'Backup helper with limited context':'Ersatzhilfe mit begrenztem Kontext',
    Name:'Name', 'e.g. Camille Martin':'z. B. Camille Martin', Email:'E-Mail', 'Can preview':'Kann einsehen',
    'Daily stories':'Tagesberichte', 'Owner-ready recaps and media placeholders':'Besitzerfertige Rückblicke und Demo-Medien',
    'Structured observations and handover notes':'Strukturierte Beobachtungen und Übergabenotizen',
    'Health notes':'Gesundheitsnotizen', 'Factual medication and watch items, never diagnoses':'Sachliche Medikation und Beobachtungspunkte, niemals Diagnosen',
    'Local preview only':'Nur lokale Vorschau', 'This prototype will not send email, WhatsApp, SMS, or notifications.':'Dieser Prototyp sendet keine E-Mails, WhatsApp, SMS oder Benachrichtigungen.',
    'Demo data only · the invite is stored in this browser as pending.':'Nur Demodaten · die Einladung wird in diesem Browser als ausstehend gespeichert.',
    'Create pending invite preview →':'Ausstehende Einladungsvorschau erstellen →',
    'Invite-ready summary':'Einladungsfertige Zusammenfassung', 'Updates as you choose role and permissions':'Aktualisiert sich, während Sie Rolle und Berechtigungen wählen',
    'Pending invites':'Ausstehende Einladungen', 'Local preview queue':'Lokale Vorschau-Warteschlange',
    'No pending invites yet':'Noch keine ausstehenden Einladungen', 'Create a preview to see it queued here.':'Erstellen Sie eine Vorschau, um sie hier in der Warteschlange zu sehen.',
    'Pending preview':'Ausstehende Vorschau', 'New contact':'Neuer Kontakt', 'Email needed before preview':'E-Mail vor der Vorschau erforderlich',
    Role:'Rolle', 'Shared care context':'Geteilter Pflegekontext', 'Choose at least one area':'Wählen Sie mindestens einen Bereich',
    'Ready as a pending preview':'Bereit als ausstehende Vorschau',
    'No delivery will happen from this demo. Review the summary with the sitter before copying anything elsewhere.':'Aus dieser Demo erfolgt kein Versand. Gehen Sie die Zusammenfassung mit der Betreuungsperson durch, bevor Sie etwas anderswohin kopieren.',
    'Bookings overview':'Buchungsübersicht', '11 bookings · 76% of this week’s care capacity':'11 Buchungen · 76 % der Pflegekapazität dieser Woche', '＋ New booking':'＋ Neue Buchung',
    Sun:'So', Mon:'Mo', Tue:'Di', Wed:'Mi', Thu:'Do', Fri:'Fr', Sat:'Sa',
    walk:'Spaziergang', 'day care':'Tagesbetreuung', 'half day':'Halbtag', 'Admin morning':'Bürovormittag',
    'Upcoming handovers':'Anstehende Übergaben', 'Everything owners need before the doorbell rings':'Alles, was Besitzer brauchen, bevor es an der Tür klingelt',
    pickup:'Abholung', 'Story draft ready · lead and food tub packed':'Berichtsentwurf bereit · Leine und Futterdose gepackt',
    'Add final rest update before handover':'Letzte Ruhe-Notiz vor der Übergabe hinzufügen',
    'REVENUE BOOKED':'GEBUCHTER UMSATZ', '↑ 13% vs June':'↑ 13 % vs Juni', 'NET AFTER EXPENSES':'NETTO NACH KOSTEN', '77% margin':'77 % Marge',
    'CARE HOURS':'PFLEGESTUNDEN', '€30.21 / hour':'30,21 € / Stunde', 'REPEAT OWNERS':'STAMMKUNDEN', Healthy:'Gesund',
    'Revenue rhythm':'Umsatzrhythmus', 'Last 7 months · demo data':'Letzte 7 Monate · Demodaten',
    Jan:'Jan', Feb:'Feb', Mar:'Mär', Apr:'Apr', May:'Mai', Jun:'Jun', Jul:'Jul',
    'Recent expenses':'Aktuelle Ausgaben', '€644 this month':'644 € diesen Monat', '＋ Add':'＋ Hinzufügen',
    'Enrichment supplies':'Beschäftigungsmaterial', 'Pet shop · 10 July':'Zoohandlung · 10. Juli',
    Fuel:'Kraftstoff', 'Travel · 8 July':'Fahrt · 8. Juli',
    'Business insurance':'Betriebshaftpflicht', 'Monthly · 1 July':'Monatlich · 1. Juli',
    'Demo settings':'Demo-Einstellungen', 'External integrations are intentionally unavailable in this local prototype.':'Externe Integrationen sind in diesem lokalen Prototyp bewusst nicht verfügbar.',
    'Reset demo observations':'Demo-Beobachtungen zurücksetzen',
    'Add a care update first':'Fügen Sie zuerst eine Pflegenotiz hinzu', 'Saved to {name}’s timeline':'In {name}s Verlauf gespeichert',
    'Add a name for the invite preview':'Fügen Sie einen Namen für die Einladungsvorschau hinzu', 'Add an email for the invite preview':'Fügen Sie eine E-Mail für die Einladungsvorschau hinzu',
    'Choose at least one thing to share':'Wählen Sie mindestens ein Element zum Teilen', 'Pending invite preview created — nothing was sent':'Ausstehende Einladungsvorschau erstellt — es wurde nichts gesendet',
    'WhatsApp preview only — nothing was sent':'Nur WhatsApp-Vorschau — es wurde nichts gesendet',
    'Clinic call preview — verify contact details before calling':'Vorschau des Klinikanrufs — prüfen Sie die Kontaktdaten vor dem Anruf',
    'Video consult preview — no appointment or video call was created':'Vorschau der Videosprechstunde — es wurde kein Termin und kein Videoanruf erstellt',
    'Instagram draft preview — no account connected':'Instagram-Entwurfsvorschau — kein Konto verbunden',
    'Booking creation is a demo preview':'Die Buchungserstellung ist eine Demo-Vorschau', 'Expense entry is a demo preview':'Die Ausgabenerfassung ist eine Demo-Vorschau',
    'Demo observations reset':'Demo-Beobachtungen zurückgesetzt',
    'Health & care observation':'Gesundheits- & Pflegebeobachtung', 'Activity update':'Aktivitätsnotiz', 'Meal update':'Mahlzeitnotiz', 'Care moment':'Pflegemoment',
    'Breakfast & morning check-in':'Frühstück & Morgencheck',
    'Finished her full breakfast and drank well. Bright, relaxed and ready for the day.':'Hat ihr ganzes Frühstück gefressen und gut getrunken. Munter, entspannt und bereit für den Tag.',
    'Woodland walk':'Waldspaziergang',
    'A calm 42-minute sniff walk. Good recall around two dogs and no stiffness noticed.':'Ein ruhiger 42-minütiger Schnüffelspaziergang. Guter Rückruf bei zwei Hunden und keine Steifheit bemerkt.',
    'Evening medication':'Abendmedikation',
    'Joint supplement given with dinner. Coat and paws checked after rain.':'Gelenkpräparat zum Abendessen gegeben. Fell und Pfoten nach dem Regen kontrolliert.',
    'Settled into day care':'Gut in der Tagesbetreuung angekommen',
    'A little vocal at drop-off, then settled on the green bed after five minutes.':'Bei der Abgabe etwas laut, dann nach fünf Minuten auf dem grünen Bett zur Ruhe gekommen.',
    'Play session':'Spieleinheit',
    'Gentle play with Billie in the garden. Responded well to breaks and name cues.':'Sanftes Spiel mit Billie im Garten. Hat gut auf Pausen und Namenssignale reagiert.',
    Yesterday:'Gestern',
    'Profile to complete':'Profil zu vervollständigen', 'Breed to confirm':'Rasse zu bestätigen',
    'Radiograph recorded at Clinique Artémis. Add current care instructions.':'Röntgenbild in der Clinique Artémis erfasst. Aktuelle Pflegeanweisungen hinzufügen.',
    'Add current health and medication instructions.':'Aktuelle Gesundheits- und Medikationsanweisungen hinzufügen.',
    'Add routine, triggers and favourite rewards.':'Routine, Auslöser und Lieblingsbelohnungen hinzufügen.',
    'Add preferred vet and emergency contact':'Bevorzugten Tierarzt und Notfallkontakt hinzufügen',
    'Confirm with owner':'Mit Besitzer bestätigen', 'Set a daily movement target':'Tägliches Bewegungsziel festlegen',
    'Add favourite enrichment':'Lieblingsbeschäftigung hinzufügen', 'Add sensitivities and recovery needs':'Empfindlichkeiten und Erholungsbedürfnisse hinzufügen',
    '10:10 woodland walk':'10:10 Waldspaziergang', '11:30 garden play':'11:30 Spiel im Garten'
  },
  es: {
    Today:'Hoy', Dogs:'Perros', Capture:'Registrar', Gallery:'Galería', 'Daily story':'Historia del día', Schedule:'Agenda', Business:'Negocio', Settings:'Ajustes', Invite:'Invitar',
    'All systems calm':'Todo está en calma', 'Capture update':'Añadir nota',
    'SUNDAY · 12 JULY':'DOMINGO · 12 DE JULIO', 'Good morning, Adine-Sophie':'Buenos días, Adine-Sophie',
    'DOG PROFILE':'PERFIL DEL PERRO', 'RAPID CAPTURE':'REGISTRO RÁPIDO', 'Capture the moment':'Registra el momento',
    'MEDIA LIBRARY':'BIBLIOTECA MULTIMEDIA', 'Little moments, safely kept':'Pequeños momentos, guardados con cuidado',
    'OWNER UPDATE · DRAFT':'ACTUALIZACIÓN PARA EL DUEÑO · BORRADOR', 'A lovely day, ready to share':'Un bonito día, listo para compartir',
    'INVITE PREVIEW':'VISTA PREVIA DE INVITACIÓN', 'Share care context safely':'Comparte el contexto de cuidado de forma segura',
    'SCHEDULE · 12–18 JULY':'AGENDA · 12–18 DE JULIO', 'A week with room to breathe':'Una semana con espacio para respirar',
    'BUSINESS · JULY':'NEGOCIO · JULIO', 'A small business, clearly seen':'Un pequeño negocio, con una visión clara',
    SETTINGS:'AJUSTES', 'Your calm corner':'Tu rincón de calma',
    'TODAY AT A GLANCE':'RESUMEN DE HOY',
    'Two happy dogs, one beautifully organised day.':'Dos perros felices, un día perfectamente organizado.',
    'Billie and Charlie are both checked in. Capture the little moments now and their owner stories will write themselves.':'Billie y Charlie ya están registrados. Anota ahora los pequeños momentos y sus historias para los dueños se escribirán solas.',
    'Add a care moment →':'Añadir un momento de cuidado →',
    'Your dogs today':'Tus perros hoy', 'Live care context, always close by':'El contexto de cuidado, siempre a mano', 'View profiles':'Ver perfiles',
    'Latest from the care log':'Última nota de cuidado', 'Your newest structured observation':'Tu observación estructurada más reciente',
    "Today's rhythm":'El ritmo de hoy', '3 of 5 moments complete':'3 de 5 momentos completados',
    arrival:'llegada', 'Day care until':'Guardería hasta las', 'Lunch & quiet time':'Almuerzo & rato de calma', 'Both dogs':'Ambos perros',
    'Owner stories':'Historias para los dueños', 'Prepare daily recaps':'Preparar los resúmenes diarios',
    'July pulse':'Pulso de julio', 'Business snapshot':'Resumen del negocio',
    'Revenue booked':'Ingresos reservados', 'Capacity filled':'Capacidad ocupada', 'Healthy momentum':'Buen impulso',
    'You’re €340 ahead of this point last month.':'Vas 340 € por delante respecto a este punto del mes pasado.',
    'Care record':'Ficha de cuidado', 'Everything that helps {name} feel understood.':'Todo lo que ayuda a que {name} se sienta comprendido.',
    '＋ Add observation':'＋ Añadir observación', 'Owner:':'Dueño:',
    'Needs & lifestyle':'Necesidades & estilo de vida', 'Personalise these with the owner — not breed stereotypes.':'Personalízalas con el dueño, no según estereotipos de raza.',
    Energy:'Energía', Movement:'Movimiento', Enrichment:'Enriquecimiento', Sensitivities:'Sensibilidades',
    'Care timeline':'Historial de cuidado', '{count} recorded moments':'{count} momentos registrados',
    'Care insight':'Perspectiva de cuidado', 'Evidence-based prompt · never a diagnosis':'Indicación basada en hechos · nunca un diagnóstico',
    'Care context':'Contexto de cuidado', 'Quick reference for every handover':'Referencia rápida para cada entrega',
    HEALTH:'SALUD', BEHAVIOUR:'COMPORTAMIENTO', 'VET & EMERGENCY':'VETERINARIO & EMERGENCIA',
    Food:'Comida', Walk:'Paseo', Pickup:'Recogida', 'Set with owner':'A definir con el dueño',
    'Vet access':'Acceso veterinario', 'Preview only · no clinic is contacted':'Solo vista previa · no se contacta con ninguna clínica',
    'Call clinic':'Llamar a la clínica', 'Video consult':'Consulta por vídeo', 'Switch dog':'Cambiar de perro',
    'Repeated health observations':'Observaciones de salud repetidas',
    '{count} health-related notes are in the recent record. This is a care prompt, not a diagnosis: review the notes with the owner and contact a vet if concerned.':'Hay {count} notas relacionadas con la salud en el historial reciente. Es un recordatorio de cuidado, no un diagnóstico: revisa las notas con el dueño y contacta con un veterinario si te preocupa.',
    'Health note recorded':'Nota de salud registrada',
    'One health-related note is in the record. Keep observing and share the exact facts with the owner; this app does not diagnose.':'Hay una nota relacionada con la salud en el historial. Sigue observando y comparte los datos exactos con el dueño; esta aplicación no diagnostica.',
    'Routine context is building':'El contexto de la rutina va tomando forma',
    'Several activity observations are now linked to this dog. Add energy and enrichment targets to make future insights more personal.':'Varias observaciones de actividad ya están vinculadas a este perro. Añade objetivos de energía y enriquecimiento para que las próximas perspectivas sean más personales.',
    'No pattern yet':'Aún no hay un patrón',
    'Keep capturing small moments. Insights appear only when there is enough care history to support them.':'Sigue registrando pequeños momentos. Las perspectivas aparecen solo cuando hay suficiente historial de cuidado que las respalde.',
    Nutrition:'Nutrición', Medication:'Medicación', 'Health check':'Control de salud', Behaviour:'Comportamiento', Social:'Social', Training:'Adiestramiento',
    Activity:'Actividad', 'Health watch':'Vigilancia de salud', 'General care':'Cuidado general', Time:'Hora',
    'Mood · bright':'Ánimo · radiante', 'Exercise · 42 min':'Ejercicio · 42 min', 'Behaviour · calm':'Comportamiento · tranquilo', 'Mood · settled':'Ánimo · sereno',
    'Day care':'Guardería', 'All good':'Todo bien', Settled:'Sereno', 'Checked in':'Registrado', 'Consent on file':'Consentimiento registrado',
    'What just happened?':'¿Qué acaba de pasar?', 'Write naturally. DogCare Brain will organise the useful details.':'Escribe con naturalidad. DogCare Brain organizará los detalles útiles.',
    'Who is this about?':'¿De quién se trata?', 'Care update':'Actualización de cuidado',
    'Try: Ate all breakfast, playful with Mabel, loose stool at 10:30…':'Prueba: Se comió todo el desayuno, juguetona con Mabel, heces blandas a las 10:30…',
    'Detected details':'Detalles detectados', '· updates as you type':'· se actualiza mientras escribes',
    'Start typing to see structured care tags':'Empieza a escribir para ver las etiquetas de cuidado estructuradas',
    'Health observations are factual notes, not diagnoses. Contact a veterinarian if concerned.':'Las observaciones de salud son notas objetivas, no diagnósticos. Contacta con un veterinario si te preocupa.',
    'AI structuring preview · This local demo uses on-device rules and sends no data anywhere.':'Vista previa de estructuración por IA · Esta demo local usa reglas en el dispositivo y no envía ningún dato.',
    "Save to {name}'s timeline →":'Guardar en el historial de {name} →',
    'Care gallery':'Galería de cuidado', 'Demo media placeholders attached to owner-ready stories.':'Elementos multimedia de demostración vinculados a historias listas para el dueño.',
    'Instagram draft preview':'Vista previa de borrador de Instagram', 'Story ready':'Historia lista',
    'Billie’s woodland walk':'Paseo por el bosque de Billie', 'Today · 10:12':'Hoy · 10:12',
    'Charlie in the garden':'Charlie en el jardín', 'Today · 11:34':'Hoy · 11:34',
    'Muddy-paw evidence':'Pruebas de patas embarradas', 'Yesterday · 16:45':'Ayer · 16:45',
    'The favourite sniff spot':'El rincón favorito para olfatear', '10 July · 09:50':'10 de julio · 09:50',
    'Enrichment time':'Rato de enriquecimiento', '9 July · 14:20':'9 de julio · 14:20',
    'Post-walk snooze':'Siesta tras el paseo', '8 July · 12:15':'8 de julio · 12:15',
    'Sunday, 12 July · Daily story':'Domingo 12 de julio · Historia del día', '{name}’s day':'El día de {name}',
    '{name} enjoyed plenty of calm attention and is heading home happy and settled.':'{name} ha disfrutado de mucha atención tranquila y vuelve a casa feliz y sereno.',
    outside:'al aire libre', meals:'comidas', mood:'ánimo', 'All eaten':'Todo comido', Calm:'Tranquilo',
    'Owner-ready, not auto-sent':'Listo para el dueño, nunca enviado automáticamente',
    'Review this draft before sharing. In a future connected version, you could send it through WhatsApp or add it to an Instagram story.':'Revisa este borrador antes de compartirlo. En una futura versión conectada, podrías enviarlo por WhatsApp o añadirlo a una historia de Instagram.',
    'Preview for':'Vista previa para', 'Preview WhatsApp message':'Previsualizar mensaje de WhatsApp', 'Draft preview only · no message will be sent':'Solo vista previa del borrador · no se enviará ningún mensaje',
    'Prepare an invite':'Preparar una invitación', 'Build a local pending invite preview for an owner or trusted carer. Nothing is sent.':'Crea una vista previa de invitación local y pendiente para un dueño o un cuidador de confianza. No se envía nada.',
    'Invite role':'Rol del invitado', Owner:'Dueño', 'Family member who receives updates':'Familiar que recibe las novedades',
    'Trusted carer':'Cuidador de confianza', 'Backup helper with limited context':'Ayuda de respaldo con contexto limitado',
    Name:'Nombre', 'e.g. Camille Martin':'p. ej. Camille Martin', Email:'Correo', 'Can preview':'Puede ver',
    'Daily stories':'Historias diarias', 'Owner-ready recaps and media placeholders':'Resúmenes listos para el dueño y elementos multimedia de demostración',
    'Structured observations and handover notes':'Observaciones estructuradas y notas de entrega',
    'Health notes':'Notas de salud', 'Factual medication and watch items, never diagnoses':'Medicación objetiva y puntos a vigilar, nunca diagnósticos',
    'Local preview only':'Solo vista previa local', 'This prototype will not send email, WhatsApp, SMS, or notifications.':'Este prototipo no enviará correos, WhatsApp, SMS ni notificaciones.',
    'Demo data only · the invite is stored in this browser as pending.':'Solo datos de demostración · la invitación se guarda en este navegador como pendiente.',
    'Create pending invite preview →':'Crear vista previa de invitación pendiente →',
    'Invite-ready summary':'Resumen listo para invitar', 'Updates as you choose role and permissions':'Se actualiza a medida que eliges el rol y los permisos',
    'Pending invites':'Invitaciones pendientes', 'Local preview queue':'Cola de vistas previas locales',
    'No pending invites yet':'Aún no hay invitaciones pendientes', 'Create a preview to see it queued here.':'Crea una vista previa para verla en cola aquí.',
    'Pending preview':'Vista previa pendiente', 'New contact':'Nuevo contacto', 'Email needed before preview':'Se necesita un correo antes de la vista previa',
    Role:'Rol', 'Shared care context':'Contexto de cuidado compartido', 'Choose at least one area':'Elige al menos un área',
    'Ready as a pending preview':'Lista como vista previa pendiente',
    'No delivery will happen from this demo. Review the summary with the sitter before copying anything elsewhere.':'Desde esta demo no se realizará ningún envío. Revisa el resumen con la persona cuidadora antes de copiar nada en otro lugar.',
    'Bookings overview':'Resumen de reservas', '11 bookings · 76% of this week’s care capacity':'11 reservas · 76 % de la capacidad de cuidado de esta semana', '＋ New booking':'＋ Nueva reserva',
    Sun:'Dom', Mon:'Lun', Tue:'Mar', Wed:'Mié', Thu:'Jue', Fri:'Vie', Sat:'Sáb',
    walk:'paseo', 'day care':'guardería', 'half day':'media jornada', 'Admin morning':'Mañana administrativa',
    'Upcoming handovers':'Próximas entregas', 'Everything owners need before the doorbell rings':'Todo lo que los dueños necesitan antes de que suene el timbre',
    pickup:'recogida', 'Story draft ready · lead and food tub packed':'Borrador de historia listo · correa y bote de comida preparados',
    'Add final rest update before handover':'Añade una última nota de descanso antes de la entrega',
    'REVENUE BOOKED':'INGRESOS RESERVADOS', '↑ 13% vs June':'↑ 13 % vs junio', 'NET AFTER EXPENSES':'NETO TRAS GASTOS', '77% margin':'77 % de margen',
    'CARE HOURS':'HORAS DE CUIDADO', '€30.21 / hour':'30,21 € / hora', 'REPEAT OWNERS':'DUEÑOS RECURRENTES', Healthy:'Saludable',
    'Revenue rhythm':'Ritmo de ingresos', 'Last 7 months · demo data':'Últimos 7 meses · datos de demostración',
    Jan:'Ene', Feb:'Feb', Mar:'Mar', Apr:'Abr', May:'May', Jun:'Jun', Jul:'Jul',
    'Recent expenses':'Gastos recientes', '€644 this month':'644 € este mes', '＋ Add':'＋ Añadir',
    'Enrichment supplies':'Material de enriquecimiento', 'Pet shop · 10 July':'Tienda de mascotas · 10 de julio',
    Fuel:'Combustible', 'Travel · 8 July':'Desplazamiento · 8 de julio',
    'Business insurance':'Seguro del negocio', 'Monthly · 1 July':'Mensual · 1 de julio',
    'Demo settings':'Ajustes de demostración', 'External integrations are intentionally unavailable in this local prototype.':'Las integraciones externas no están disponibles a propósito en este prototipo local.',
    'Reset demo observations':'Restablecer las observaciones de demostración',
    'Add a care update first':'Añade primero una nota de cuidado', 'Saved to {name}’s timeline':'Guardado en el historial de {name}',
    'Add a name for the invite preview':'Añade un nombre para la vista previa de la invitación', 'Add an email for the invite preview':'Añade un correo para la vista previa de la invitación',
    'Choose at least one thing to share':'Elige al menos un elemento para compartir', 'Pending invite preview created — nothing was sent':'Vista previa de invitación pendiente creada — no se envió nada',
    'WhatsApp preview only — nothing was sent':'Solo vista previa de WhatsApp — no se envió nada',
    'Clinic call preview — verify contact details before calling':'Vista previa de llamada a la clínica — verifica los datos de contacto antes de llamar',
    'Video consult preview — no appointment or video call was created':'Vista previa de consulta por vídeo — no se creó ninguna cita ni videollamada',
    'Instagram draft preview — no account connected':'Vista previa de borrador de Instagram — ninguna cuenta conectada',
    'Booking creation is a demo preview':'La creación de reservas es una vista previa de demostración', 'Expense entry is a demo preview':'El registro de gastos es una vista previa de demostración',
    'Demo observations reset':'Observaciones de demostración restablecidas',
    'Health & care observation':'Observación de salud & cuidado', 'Activity update':'Nota de actividad', 'Meal update':'Nota de comida', 'Care moment':'Momento de cuidado',
    'Breakfast & morning check-in':'Desayuno & control de la mañana',
    'Finished her full breakfast and drank well. Bright, relaxed and ready for the day.':'Terminó todo su desayuno y bebió bien. Despierta, relajada y lista para el día.',
    'Woodland walk':'Paseo por el bosque',
    'A calm 42-minute sniff walk. Good recall around two dogs and no stiffness noticed.':'Un tranquilo paseo olfativo de 42 minutos. Buena respuesta a la llamada junto a dos perros y sin rigidez apreciada.',
    'Evening medication':'Medicación de la tarde',
    'Joint supplement given with dinner. Coat and paws checked after rain.':'Suplemento articular dado con la cena. Pelaje y patas revisados tras la lluvia.',
    'Settled into day care':'Bien adaptado en la guardería',
    'A little vocal at drop-off, then settled on the green bed after five minutes.':'Un poco vocal al llegar, luego se acomodó en la cama verde tras cinco minutos.',
    'Play session':'Sesión de juego',
    'Gentle play with Billie in the garden. Responded well to breaks and name cues.':'Juego suave con Billie en el jardín. Respondió bien a las pausas y a las llamadas por su nombre.',
    Yesterday:'Ayer',
    'Profile to complete':'Perfil por completar', 'Breed to confirm':'Raza por confirmar',
    'Radiograph recorded at Clinique Artémis. Add current care instructions.':'Radiografía registrada en la Clinique Artémis. Añade las instrucciones de cuidado actuales.',
    'Add current health and medication instructions.':'Añade las instrucciones actuales de salud y medicación.',
    'Add routine, triggers and favourite rewards.':'Añade la rutina, los desencadenantes y las recompensas favoritas.',
    'Add preferred vet and emergency contact':'Añade el veterinario preferido y el contacto de emergencia',
    'Confirm with owner':'Confirmar con el dueño', 'Set a daily movement target':'Fijar un objetivo de movimiento diario',
    'Add favourite enrichment':'Añadir el enriquecimiento favorito', 'Add sensitivities and recovery needs':'Añadir sensibilidades y necesidades de recuperación',
    '10:10 woodland walk':'10:10 paseo por el bosque', '11:30 garden play':'11:30 juego en el jardín'
  }
};
let state = { page: 'dashboard', dog: 'billie', language: localStorage.getItem('dogcare-language') || 'en', observations: loadObservations(), invites: loadInvites() };
const content = document.querySelector('#app-content');
const title = document.querySelector('#page-title');
const eyebrow = document.querySelector('#page-eyebrow');

function loadObservations() {
  try { return JSON.parse(localStorage.getItem('dogcare-observations')) || structuredClone(baseObservations); }
  catch { return structuredClone(baseObservations); }
}
function saveObservations() { localStorage.setItem('dogcare-observations', JSON.stringify(state.observations)); }
function loadInvites() {
  try { return JSON.parse(localStorage.getItem('dogcare-invites')) || []; }
  catch { return []; }
}
function saveInvites() { localStorage.setItem('dogcare-invites', JSON.stringify(state.invites)); }
function escapeHtml(value) { return String(value).replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function showToast(message) { const toast=document.querySelector('#toast'); toast.textContent=message; toast.classList.add('show'); setTimeout(()=>toast.classList.remove('show'),2500); }
function dogAvatar(key) { const d=dogs[key]; return `<div class="dog-avatar ${d.colour}">${d.emoji}</div>`; }
function t(text) { return translations[state.language]?.[text] || text; }
function tf(text, params) { let out = t(text); for (const key in params) out = out.split('{' + key + '}').join(params[key]); return out; }
function translateTag(tag) {
  if (translations[state.language]?.[tag]) return t(tag);
  return String(tag).split(' · ').map(part => t(part)).join(' · ');
}
function setHeader(kicker, heading) { eyebrow.textContent=t(kicker); title.textContent=t(heading); }
function localizeContent() { const walker=document.createTreeWalker(content, NodeFilter.SHOW_TEXT), nodes=[]; while(walker.nextNode()) nodes.push(walker.currentNode); nodes.forEach(node=>{const source=node.nodeValue.trim();if(source && translations[state.language]?.[source]) node.nodeValue=node.nodeValue.replace(source,t(source));}); document.querySelectorAll('[data-i18n]').forEach(el=>el.textContent=t(el.dataset.i18n)); document.documentElement.lang=state.language; }
function tagsHtml(tags) { return `<div class="mini-tags">${tags.map(tag=>`<span>${escapeHtml(translateTag(tag))}</span>`).join('')}</div>`; }
function formatPermissions(permissions) {
  const labels = { stories: 'Daily stories', timeline: 'Care timeline', health: 'Health notes' };
  return permissions.map(permission => labels[permission]).filter(Boolean);
}
function inviteRoleLabel(role) { return role === 'trusted-carer' ? t('Trusted carer') : t('Owner'); }
function pendingInvitesHtml() {
  if (!state.invites.length) return `<div class="empty-state small"><strong>${t('No pending invites yet')}</strong><span>${t('Create a preview to see it queued here.')}</span></div>`;
  return state.invites.map(invite => `<article class="pending-invite"><div><span class="status-dot"></span><strong>${escapeHtml(invite.name)}</strong><small>${escapeHtml(invite.email)} · ${inviteRoleLabel(invite.role)}</small></div><div>${tagsHtml(formatPermissions(invite.permissions))}</div><span class="pending-label">${t('Pending preview')}</span></article>`).join('');
}
function careInsight(key) {
  const observations=state.observations[key];
  const health=observations.filter(o=>o.tags.some(tag=>/health|medication|sick|stool/i.test(tag)));
  const activity=observations.filter(o=>o.tags.some(tag=>/activity|exercise|walk|social/i.test(tag)));
  if (health.length >= 2) return { level:'review', title:t('Repeated health observations'), text:tf('{count} health-related notes are in the recent record. This is a care prompt, not a diagnosis: review the notes with the owner and contact a vet if concerned.', {count:health.length}) };
  if (health.length === 1) return { level:'watch', title:t('Health note recorded'), text:t('One health-related note is in the record. Keep observing and share the exact facts with the owner; this app does not diagnose.') };
  if (activity.length >= 2) return { level:'good', title:t('Routine context is building'), text:t('Several activity observations are now linked to this dog. Add energy and enrichment targets to make future insights more personal.') };
  return { level:'neutral', title:t('No pattern yet'), text:t('Keep capturing small moments. Insights appear only when there is enough care history to support them.') };
}

const views = {
  dashboard() {
    setHeader('SUNDAY · 12 JULY', 'Good morning, Adine-Sophie');
    const latest = state.observations.billie[0];
    return `<div class="grid dashboard-grid"><div>
      <section class="card hero"><p class="eyebrow" style="color:#d6ed8c">${t('TODAY AT A GLANCE')}</p><h2>${t('Two happy dogs, one beautifully organised day.')}</h2><p>${t('Billie and Charlie are both checked in. Capture the little moments now and their owner stories will write themselves.')}</p><button class="primary" data-go="capture">${t('Add a care moment →')}</button></section>
      <div class="section-head"><div><h2>${t('Your dogs today')}</h2><p>${t('Live care context, always close by')}</p></div><button class="link-button" data-go="dogs">${t('View profiles')}</button></div>
      <div class="dog-row">${Object.entries(dogs).map(([key,d])=>`<article class="card dog-card" data-dog="${key}">${dogAvatar(key)}<div class="dog-meta"><h3>${d.name}</h3><p>${t(d.breed)} · ${d.owner}</p>${tagsHtml(key==='billie'?['Day care','All good']:['Day care','Settled'])}</div><span class="dog-arrow">›</span></article>`).join('')}</div>
      <div class="section-head"><div><h2>${t('Latest from the care log')}</h2><p>${t('Your newest structured observation')}</p></div></div>
      <article class="card timeline-card"><div class="timeline-top"><h4>${escapeHtml(t(latest.title))}</h4><time>${latest.time} · ${t(latest.date)}</time></div><p>${escapeHtml(t(latest.text))}</p>${tagsHtml(latest.tags)}</article>
    </div><aside>
      <section class="card"><div class="section-head" style="margin-top:0"><div><h2>${t("Today's rhythm")}</h2><p>${t('3 of 5 moments complete')}</p></div></div><div class="today-list"><div class="booking"><time>08:00</time><div><h4>Billie · ${t('arrival')}</h4><p>${t('Day care until')} 17:30</p></div><i class="dot"></i></div><div class="booking"><time>09:00</time><div><h4>Charlie · ${t('arrival')}</h4><p>${t('Day care until')} 18:00</p></div><i class="dot"></i></div><div class="booking"><time>12:30</time><div><h4>${t('Lunch & quiet time')}</h4><p>${t('Both dogs')}</p></div><i class="dot peach"></i></div><div class="booking"><time>16:30</time><div><h4>${t('Owner stories')}</h4><p>${t('Prepare daily recaps')}</p></div><i class="dot peach"></i></div></div></section>
      <section class="card" style="margin-top:20px"><div class="section-head" style="margin-top:0"><div><h2>${t('July pulse')}</h2><p>${t('Business snapshot')}</p></div></div><div class="kpi"><div><strong>€2,840</strong><small>${t('Revenue booked')}</small></div><div><strong>76%</strong><small>${t('Capacity filled')}</small></div></div><div class="progress"><span style="width:76%"></span></div><div class="notice"><strong>${t('Healthy momentum')}</strong>${t('You’re €340 ahead of this point last month.')}</div></section>
    </aside></div>`;
  },
  dogs() {
    const key=state.dog,d=dogs[key], obs=state.observations[key];
    setHeader('DOG PROFILE', d.name);
    return `<div class="page-title-row"><div><h2>${t('Care record')}</h2><p>${tf('Everything that helps {name} feel understood.', {name:d.name.split(' ')[0]})}</p></div><button class="primary" data-go="capture">${t('＋ Add observation')}</button></div><div class="grid page-grid"><div>
      <section class="card profile-hero">${dogAvatar(key)}<div><h2>${d.name}</h2><p>${t(d.breed)} · ${t(d.age)} · ${t('Owner:')} ${d.owner}</p>${tagsHtml(['Checked in','Consent on file'])}</div></section>
      <section class="card" style="margin-top:20px"><div class="section-head" style="margin-top:0"><div><h2>${t('Needs & lifestyle')}</h2><p>${t('Personalise these with the owner — not breed stereotypes.')}</p></div></div><div class="facts"><div class="fact"><small>${t('Energy')}</small><strong>${t(d.needs.energy)}</strong></div><div class="fact"><small>${t('Movement')}</small><strong>${t(d.needs.movement)}</strong></div><div class="fact"><small>${t('Enrichment')}</small><strong>${t(d.needs.enrichment)}</strong></div><div class="fact"><small>${t('Sensitivities')}</small><strong>${t(d.needs.sensitivities)}</strong></div></div></section>
      <div class="section-head"><div><h2>${t('Care timeline')}</h2><p>${tf('{count} recorded moments', {count:obs.length})}</p></div></div><div class="timeline">${obs.map(o=>`<article class="card timeline-card"><div class="timeline-top"><h4>${escapeHtml(t(o.title))}</h4><time>${o.time} · ${t(o.date)}</time></div><p>${escapeHtml(t(o.text))}</p>${tagsHtml(o.tags)}</article>`).join('')}</div>
    </div><aside><section class="card"><div class="section-head" style="margin-top:0"><div><h2>${t('Care insight')}</h2><p>${t('Evidence-based prompt · never a diagnosis')}</p></div></div><div class="context ${careInsight(key).level==='review'?'behaviour':''}"><strong>${careInsight(key).title}</strong><p>${careInsight(key).text}</p></div></section><section class="card" style="margin-top:20px"><div class="section-head" style="margin-top:0"><div><h2>${t('Care context')}</h2><p>${t('Quick reference for every handover')}</p></div></div><div class="context-list"><div class="context"><strong>${t('HEALTH')}</strong><p>${t(d.health)}</p></div><div class="context behaviour"><strong>${t('BEHAVIOUR')}</strong><p>${t(d.behaviour)}</p></div><div class="context vet"><strong>${t('VET & EMERGENCY')}</strong><p>${t(d.vet)}</p></div></div><div class="facts"><div class="fact"><small>${t('Food')}</small><strong>${t('Set with owner')}</strong></div><div class="fact"><small>${t('Walk')}</small><strong>${t('Set with owner')}</strong></div><div class="fact"><small>${t('Pickup')}</small><strong>${t('Set with owner')}</strong></div></div></section><section class="card" style="margin-top:20px"><div class="section-head" style="margin-top:0"><div><h2>${t('Vet access')}</h2><p>${t('Preview only · no clinic is contacted')}</p></div></div><p style="font-size:12px;color:var(--muted);line-height:1.5">${t(d.vet)}</p><div class="composer-actions"><button class="secondary" id="vet-call">${t('Call clinic')}</button><button class="ghost" id="vet-video">${t('Video consult')}</button></div></section><section class="card" style="margin-top:20px"><h3 style="font:400 20px Georgia,serif">${t('Switch dog')}</h3><div class="dog-picker">${Object.entries(dogs).map(([k,x])=>`<button class="dog-pick ${k===key?'active':''}" data-dog="${k}"><span>${x.emoji}</span><div><strong>${x.name.split(' ')[0]}</strong><small>${t(x.age)}</small></div></button>`).join('')}</div></section></aside></div>`;
  },
  capture() {
    const d=dogs[state.dog]; setHeader('RAPID CAPTURE', 'Capture the moment');
    return `<div class="page-title-row"><div><h2>${t('What just happened?')}</h2><p>${t('Write naturally. DogCare Brain will organise the useful details.')}</p></div></div><section class="card composer"><label class="label">${t('Who is this about?')}</label><div class="dog-picker">${Object.entries(dogs).map(([k,x])=>`<button class="dog-pick ${k===state.dog?'active':''}" data-capture-dog="${k}"><span>${x.emoji}</span><div><strong>${x.name}</strong><small>${t(x.last)}</small></div></button>`).join('')}</div><label class="label" for="observation">${t('Care update')}</label><textarea id="observation" placeholder="${t('Try: Ate all breakfast, playful with Mabel, loose stool at 10:30…')}"></textarea><label class="label">${t('Detected details')} <small style="font-weight:400;text-transform:none;letter-spacing:0"> ${t('· updates as you type')}</small></label><div class="detected" id="detected"><em>${t('Start typing to see structured care tags')}</em></div><p id="health-safety" class="preview-note" hidden>${t('Health observations are factual notes, not diagnoses. Contact a veterinarian if concerned.')}</p><div class="composer-actions"><small>${t('AI structuring preview · This local demo uses on-device rules and sends no data anywhere.')}</small><button class="primary" id="save-observation">${tf("Save to {name}'s timeline →", {name:d.name.split(' ')[0]})}</button></div></section>`;
  },
  gallery() { setHeader('MEDIA LIBRARY','Little moments, safely kept'); const items=[['🐕‍🦺','Billie’s woodland walk','Today · 10:12'],['🐶','Charlie in the garden','Today · 11:34'],['🐾','Muddy-paw evidence','Yesterday · 16:45'],['🌿','The favourite sniff spot','10 July · 09:50'],['🦴','Enrichment time','9 July · 14:20'],['☁️','Post-walk snooze','8 July · 12:15']]; return `<div class="page-title-row"><div><h2>${t('Care gallery')}</h2><p>${t('Demo media placeholders attached to owner-ready stories.')}</p></div><button class="ghost" id="draft-instagram">${t('Instagram draft preview')}</button></div><div class="grid media-grid">${items.map((x,i)=>`<article class="media-item"><div class="media-art">${x[0]}</div>${i<2?`<span class="draft-badge">${t('Story ready')}</span>`:''}<div class="media-copy"><strong>${t(x[1])}</strong><small>${t(x[2])}</small></div></article>`).join('')}</div>`; },
  story() { const d=dogs[state.dog], latest=state.observations[state.dog][0]; setHeader('OWNER UPDATE · DRAFT','A lovely day, ready to share'); return `<div class="grid page-grid"><div class="story-phone"><div class="story-image">${d.emoji}</div><div class="story-body"><p class="story-date">${t('Sunday, 12 July · Daily story')}</p><h3>${tf('{name}’s day', {name:d.name})}</h3><p class="story-copy">${escapeHtml(t(latest.text))} ${tf('{name} enjoyed plenty of calm attention and is heading home happy and settled.', {name:d.name.split(' ')[0]})}</p><div class="story-stats"><div><strong>${state.dog==='billie'?'42 min':'25 min'}</strong><small>${t('outside')}</small></div><div><strong>${t('All eaten')}</strong><small>${t('meals')}</small></div><div><strong>${t('Calm')}</strong><small>${t('mood')}</small></div></div></div></div><aside><section class="card"><h2 style="font:400 24px Georgia,serif">${t('Owner-ready, not auto-sent')}</h2><p style="font-size:12px;color:var(--muted);line-height:1.6">${t('Review this draft before sharing. In a future connected version, you could send it through WhatsApp or add it to an Instagram story.')}</p><label class="label">${t('Preview for')}</label><div class="dog-picker">${Object.entries(dogs).map(([k,x])=>`<button class="dog-pick ${k===state.dog?'active':''}" data-story-dog="${k}"><span>${x.emoji}</span><div><strong>${x.name}</strong><small>${x.owner}</small></div></button>`).join('')}</div><button class="secondary" id="whatsapp-preview" style="width:100%;margin-top:20px">${t('Preview WhatsApp message')}</button><p class="preview-note">${t('Draft preview only · no message will be sent')}</p></section></aside></div>`; },
  invite() { setHeader('INVITE PREVIEW','Share care context safely'); return `<div class="page-title-row"><div><h2>${t('Prepare an invite')}</h2><p>${t('Build a local pending invite preview for an owner or trusted carer. Nothing is sent.')}</p></div></div><div class="grid page-grid invite-grid"><section class="card invite-card"><div class="form-row"><label class="label">${t('Invite role')}</label><div class="role-choice" role="radiogroup" aria-label="Invite role"><label><input type="radio" name="invite-role" value="owner" checked><span><strong>${t('Owner')}</strong><small>${t('Family member who receives updates')}</small></span></label><label><input type="radio" name="invite-role" value="trusted-carer"><span><strong>${t('Trusted carer')}</strong><small>${t('Backup helper with limited context')}</small></span></label></div></div><div class="form-split"><label class="field-label" for="invite-name">${t('Name')}<input id="invite-name" autocomplete="name" placeholder="${t('e.g. Camille Martin')}"></label><label class="field-label" for="invite-email">${t('Email')}<input id="invite-email" type="email" autocomplete="email" placeholder="camille@example.com"></label></div><label class="label">${t('Can preview')}</label><div class="permission-list"><label><input type="checkbox" name="invite-permission" value="stories" checked><span><strong>${t('Daily stories')}</strong><small>${t('Owner-ready recaps and media placeholders')}</small></span></label><label><input type="checkbox" name="invite-permission" value="timeline" checked><span><strong>${t('Care timeline')}</strong><small>${t('Structured observations and handover notes')}</small></span></label><label><input type="checkbox" name="invite-permission" value="health"><span><strong>${t('Health notes')}</strong><small>${t('Factual medication and watch items, never diagnoses')}</small></span></label></div><div class="local-boundary"><strong>${t('Local preview only')}</strong><span>${t('This prototype will not send email, WhatsApp, SMS, or notifications.')}</span></div><div class="composer-actions"><small>${t('Demo data only · the invite is stored in this browser as pending.')}</small><button class="primary" id="create-invite">${t('Create pending invite preview →')}</button></div></section><aside><section class="card summary-card"><div class="section-head" style="margin-top:0"><div><h2>${t('Invite-ready summary')}</h2><p>${t('Updates as you choose role and permissions')}</p></div></div><div id="invite-summary" class="invite-summary"></div></section><section class="card" style="margin-top:20px"><div class="section-head" style="margin-top:0"><div><h2>${t('Pending invites')}</h2><p>${t('Local preview queue')}</p></div></div><div id="pending-invites" class="pending-list">${pendingInvitesHtml()}</div></section></aside></div>`; },
  schedule() { setHeader('SCHEDULE · 12–18 JULY','A week with room to breathe'); const days=[['Sun','12','Billie · 08:00','Charlie · 09:00'],['Mon','13',`Milo · ${t('walk')}`,''],['Tue','14',`Billie · ${t('day care')}`,`Poppy · ${t('walk')}`],['Wed','15',`Charlie · ${t('day care')}`,''],['Thu','16',`Billie · ${t('day care')}`,`Milo · ${t('walk')}`],['Fri','17',`Poppy · ${t('half day')}`,''],['Sat','18',t('Admin morning'),'']]; return `<div class="page-title-row"><div><h2>${t('Bookings overview')}</h2><p>${t('11 bookings · 76% of this week’s care capacity')}</p></div><button class="primary" id="new-booking">${t('＋ New booking')}</button></div><div class="grid week">${days.map((d,i)=>`<div class="day ${i===0?'today':''}"><div class="day-head">${t(d[0])}<strong>${d[1]}</strong></div>${d[2]?`<div class="event">${d[2]}</div>`:''}${d[3]?`<div class="event peach">${d[3]}</div>`:''}</div>`).join('')}</div><section class="card" style="margin-top:25px"><div class="section-head" style="margin:0"><div><h2>${t('Upcoming handovers')}</h2><p>${t('Everything owners need before the doorbell rings')}</p></div></div><div class="today-list" style="margin-top:15px"><div class="booking"><time>17:30</time><div><h4>Billie Blue · ${t('pickup')}</h4><p>${t('Story draft ready · lead and food tub packed')}</p></div><i class="dot"></i></div><div class="booking"><time>18:00</time><div><h4>Charlie Rose · ${t('pickup')}</h4><p>${t('Add final rest update before handover')}</p></div><i class="dot peach"></i></div></div></section>`; },
  business() { setHeader('BUSINESS · JULY','A small business, clearly seen'); const bars=[46,58,51,72,63,79,86]; return `<div class="grid metrics"><div class="card metric"><small>${t('REVENUE BOOKED')}</small><strong>€2,840</strong><span class="tag">${t('↑ 13% vs June')}</span></div><div class="card metric"><small>${t('NET AFTER EXPENSES')}</small><strong>€2,196</strong><span class="tag">${t('77% margin')}</span></div><div class="card metric"><small>${t('CARE HOURS')}</small><strong>94h</strong><span class="tag">${t('€30.21 / hour')}</span></div><div class="card metric"><small>${t('REPEAT OWNERS')}</small><strong>82%</strong><span class="tag">${t('Healthy')}</span></div></div><div class="grid page-grid" style="margin-top:22px"><section class="card"><div class="section-head" style="margin-top:0"><div><h2>${t('Revenue rhythm')}</h2><p>${t('Last 7 months · demo data')}</p></div></div><div class="bar-chart">${bars.map((h,i)=>`<div class="bar ${i===6?'current':''}" style="height:${h}%"><span>${t(['Jan','Feb','Mar','Apr','May','Jun','Jul'][i])}</span></div>`).join('')}</div></section><aside class="card"><div class="section-head" style="margin-top:0"><div><h2>${t('Recent expenses')}</h2><p>${t('€644 this month')}</p></div><button class="link-button" id="add-expense">${t('＋ Add')}</button></div><div class="expense-row"><div class="expense-icon">🦴</div><div><strong>${t('Enrichment supplies')}</strong><small>${t('Pet shop · 10 July')}</small></div><strong>€48</strong></div><div class="expense-row"><div class="expense-icon">🚙</div><div><strong>${t('Fuel')}</strong><small>${t('Travel · 8 July')}</small></div><strong>€72</strong></div><div class="expense-row"><div class="expense-icon">🛡</div><div><strong>${t('Business insurance')}</strong><small>${t('Monthly · 1 July')}</small></div><strong>€119</strong></div></aside></div>`; },
  settings() { setHeader('SETTINGS','Your calm corner'); return `<section class="card empty"><div class="big">⚙️</div><h2>${t('Demo settings')}</h2><p>${t('External integrations are intentionally unavailable in this local prototype.')}</p><button class="ghost" id="reset-demo">${t('Reset demo observations')}</button></section>`; }
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
  const firstName = invite.name || t('New contact');
  const permissionLabels = formatPermissions(invite.permissions);
  summary.innerHTML = `<div class="summary-person"><span>${invite.role === 'trusted-carer' ? '🤝' : '🏡'}</span><div><strong>${escapeHtml(firstName)}</strong><small>${escapeHtml(invite.email || t('Email needed before preview'))}</small></div></div><div class="summary-line"><b>${t('Role')}</b><span>${inviteRoleLabel(invite.role)}</span></div><div class="summary-line"><b>${t('Shared care context')}</b><span>${permissionLabels.length ? permissionLabels.map(label => escapeHtml(t(label))).join(', ') : t('Choose at least one area')}</span></div><div class="notice compact"><strong>${t('Ready as a pending preview')}</strong>${t('No delivery will happen from this demo. Review the summary with the sitter before copying anything elsewhere.')}</div>`;
}
function navigate(page) { state.page=page; document.querySelectorAll('.nav-item').forEach(n=>n.classList.toggle('active',n.dataset.page===page)); content.innerHTML=views[page](); localizeContent(); bindView(); document.querySelector('.sidebar').classList.remove('open'); window.scrollTo({top:0}); }
function bindView() {
  document.querySelectorAll('[data-go]').forEach(el=>el.onclick=()=>navigate(el.dataset.go));
  document.querySelectorAll('[data-dog]').forEach(el=>el.onclick=()=>{state.dog=el.dataset.dog;navigate('dogs')});
  document.querySelectorAll('[data-capture-dog]').forEach(el=>el.onclick=()=>{state.dog=el.dataset.captureDog;navigate('capture')});
  document.querySelectorAll('[data-story-dog]').forEach(el=>el.onclick=()=>{state.dog=el.dataset.storyDog;navigate('story')});
  const input=document.querySelector('#observation');
  if(input){ input.oninput=()=>{const tags=infer(input.value);document.querySelector('#detected').innerHTML=input.value.trim()?tagsHtml(tags):`<em>${t('Start typing to see structured care tags')}</em>`;document.querySelector('#health-safety').hidden=!tags.includes('Health watch');}; document.querySelector('#save-observation').onclick=()=>{const text=input.value.trim();if(!text){input.focus();showToast(t('Add a care update first'));return}const tags=infer(text), now=new Date();state.observations[state.dog].unshift({id:Date.now(),time:now.toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'}),date:'Today',title:titleFrom(text,tags),text,tags});saveObservations();showToast(tf('Saved to {name}’s timeline', {name:dogs[state.dog].name}));navigate('dogs');}; }
  const inviteButton=document.querySelector('#create-invite');
  if(inviteButton){
    document.querySelectorAll('input[name="invite-role"], input[name="invite-permission"], #invite-name, #invite-email').forEach(el=>el.addEventListener('input',updateInviteSummary));
    document.querySelectorAll('input[name="invite-role"], input[name="invite-permission"]').forEach(el=>el.addEventListener('change',updateInviteSummary));
    updateInviteSummary();
    inviteButton.onclick=()=>{const invite=readInviteForm();if(!invite.name){document.querySelector('#invite-name').focus();showToast(t('Add a name for the invite preview'));return}if(!invite.email){document.querySelector('#invite-email').focus();showToast(t('Add an email for the invite preview'));return}if(!invite.permissions.length){showToast(t('Choose at least one thing to share'));return}state.invites.unshift({...invite,id:Date.now(),created:'Today'});saveInvites();document.querySelector('#pending-invites').innerHTML=pendingInvitesHtml();showToast(t('Pending invite preview created — nothing was sent'));};
  }
  const preview=document.querySelector('#whatsapp-preview'); if(preview)preview.onclick=()=>showToast(t('WhatsApp preview only — nothing was sent'));
  const vetCall=document.querySelector('#vet-call'); if(vetCall)vetCall.onclick=()=>showToast(t('Clinic call preview — verify contact details before calling'));
  const vetVideo=document.querySelector('#vet-video'); if(vetVideo)vetVideo.onclick=()=>showToast(t('Video consult preview — no appointment or video call was created'));
  const insta=document.querySelector('#draft-instagram'); if(insta)insta.onclick=()=>showToast(t('Instagram draft preview — no account connected'));
  const booking=document.querySelector('#new-booking'); if(booking)booking.onclick=()=>showToast(t('Booking creation is a demo preview'));
  const expense=document.querySelector('#add-expense'); if(expense)expense.onclick=()=>showToast(t('Expense entry is a demo preview'));
  const reset=document.querySelector('#reset-demo'); if(reset)reset.onclick=()=>{state.observations=structuredClone(baseObservations);saveObservations();showToast(t('Demo observations reset'));navigate('dashboard');};
}
document.querySelectorAll('.nav-item[data-page]').forEach(el=>el.onclick=()=>navigate(el.dataset.page));
document.querySelectorAll('[data-route]').forEach(el=>el.onclick=e=>{e.preventDefault();navigate(el.dataset.route)});
document.querySelector('#mobile-menu').onclick=()=>document.querySelector('.sidebar').classList.toggle('open');
const languagePicker=document.querySelector('#language-picker');
languagePicker.value=state.language;
languagePicker.onchange=()=>{state.language=languagePicker.value;localStorage.setItem('dogcare-language',state.language);navigate(state.page);};
navigate('dashboard');

# DogCare Brain

A polished, dependency-free MVP for a small dog-care business. The demo follows Billie Blue and Charlie Rose from daily care capture through owner updates, scheduling, media, and lightweight business reporting.

## Run locally

From this directory, start any static file server:

```bash
python3 -m http.server 4173
```

Then open [http://localhost:4173](http://localhost:4173).

No install or build step is required. Demo observations are stored in the browser's `localStorage`; use **Reset demo** in Settings to restore the original data.

## Try the core flow

1. Open **Capture update** from the dashboard or navigation.
2. Choose a dog and enter a note such as: `Ate all breakfast, playful with Mabel, loose stool at 10:30.`
3. Review the detected tags and save the observation.
4. The new structured card appears in the dog's timeline and the owner story preview updates immediately.
5. Open **Handoff** to review a care-continuity summary for either the owner or next carer, follow its evidence links back to today's observations, and check the suggested next-care actions.

Health-watch content is deliberately phrased as factual observation rather than diagnosis. The handoff reminds carers to keep observing and contact the owner or a veterinarian when concerned.

## Try the invite preview flow

1. Open **Invite** from the sidebar or top bar.
2. Choose **Owner** or **Trusted carer**, add a demo name and email, and select share areas.
3. Review the invite-ready summary and create a **pending invite preview**.
4. The pending invite appears locally; no email, WhatsApp, SMS, or notification is sent.

## Product boundaries

This is a local interactive prototype using fictional demo data. AI structuring is represented by deterministic, on-device keyword parsing. Invite creation, WhatsApp, Instagram, owner delivery, payments, and cloud sync are clearly labelled previews or drafts and do not connect to external services.

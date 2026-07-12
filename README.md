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
2. Choose a dog and type a note, or use **Start recording** to see a voice note transcribed live into the care-note field.
3. Edit the text if needed, review the detected tags, and save the observation.
4. The new structured card appears in the dog's timeline and the owner story preview updates immediately.
5. Open **Handoff** to review a care-continuity summary for either the owner or next carer, follow its evidence links back to today's observations, and check the suggested next-care actions.

Health-watch content is deliberately phrased as factual observation rather than diagnosis. The handoff reminds carers to keep observing and contact the owner or a veterinarian when concerned.

## Try the invite preview flow

1. Open **Invite** from the sidebar or top bar.
2. Choose **Owner** or **Trusted carer**, add a demo name and email, and select share areas.
3. Review the invite-ready summary and create a **pending invite preview**.
4. The pending invite appears locally; no email, WhatsApp, SMS, or notification is sent.

## Try voice notes and social previews

1. Open **Capture update**, add written care context, then choose **Record**. Microphone permission is requested only at that point.
2. Watch the duration, stop, play back, and either discard the recording or save it with the care update. Recordings are limited to two minutes and retained in local browser storage when capacity allows.
3. Find retained voice notes on the dog's timeline and in **Gallery**.
4. In **Gallery**, preview the clearly labelled Instagram, Facebook, and YouTube access states. These controls do not ask for credentials, connect accounts, make network requests, or post content.

Browsers without `getUserMedia`/`MediaRecorder`, insecure non-localhost contexts, and denied microphone permission receive an inline explanation; typed care capture remains available.

## Product boundaries

This is a local interactive prototype using fictional demo data. AI structuring is represented by deterministic, on-device keyword parsing. Voice audio is captured and retained only in the browser; it is never uploaded. Invite creation, WhatsApp, Instagram, Facebook, YouTube, owner delivery, payments, and cloud sync are clearly labelled previews or drafts and do not connect to external services. Social previews never collect credentials or post to a network.

Voice transcription uses the browser's built-in speech-recognition feature. Depending on the browser, microphone audio may be processed by the browser provider's speech service; users should check their browser's privacy terms before recording.

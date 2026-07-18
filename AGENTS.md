# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.
- The browser app has no build step. Serve the repository root and test the public UI through browser-visible behavior.
- Critical journeys are capture → editable text → timeline, voice dictation → stop/edit → timeline, and daily handoff → evidence source.
- UI changes require a mobile viewport check, no horizontal overflow, and browser-console inspection. Run `python3.12 -m unittest tests.test_browser_acceptance -v` when the optional crawler environment is installed.
- Risk tiers determine the minimum gate: low (docs/copy only) requires syntax/unit checks; medium (UI, capture, storage, crawler behavior) requires the full relevant suite and browser evidence; high (microphone/privacy wording, non-diagnostic health language, stored-data compatibility, crawl boundaries, authentication, payments, or destructive actions) requires the full suite, independent review, and explicit human approval before external release.
- Generated crawl corpora belong outside the repository unless explicitly reviewed and approved for inclusion.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.

# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Add durable project-specific notes here as they are discovered through real work.
- The browser app has no build step. Serve the repository root and test the public UI through browser-visible behavior.
- Critical journeys are capture → editable text → timeline, voice dictation → stop/edit → timeline, and daily handoff → evidence source.
- UI changes require a mobile viewport check, no horizontal overflow, and browser-console inspection. Run `python3.12 -m unittest tests.test_browser_acceptance -v` when the optional crawler environment is installed.
- Treat microphone/privacy wording, non-diagnostic health language, stored observation compatibility, external crawling boundaries, authentication, payments, and destructive actions as high-risk. These require human review even when automated checks pass.
- Generated crawl corpora belong outside the repository unless explicitly reviewed and approved for inclusion.

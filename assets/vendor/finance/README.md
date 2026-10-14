# Local document readers

These assets load only for document intake/export. No document or recognized text is sent to a third-party service.

- Tesseract.js 6.0.1 and tesseract.js-core 6.1.2: https://github.com/naptha/tesseract.js — Apache-2.0, bundled licenses. Four embedded WASM builds support runtime selection.
- Language data: https://github.com/naptha/tessdata/tree/gh-pages/4.0.0_fast — French, English, German, Italian, Spanish. Apache-2.0 (Tesseract tessdata).
- PDF.js 6.4.299: https://github.com/mozilla/pdf.js — Apache-2.0, bundled license. Local rendering only, scripting disabled. Font/CMap-dependent documents may require manual entry if rendering fails.
- fflate 0.8.3: https://github.com/101arrowz/fflate — MIT, bundled license. Creates the XLSX Open XML package and original-document ZIP.

`manifest.json` records bundled asset checksums. Sources were retrieved from npm registry package archives and the Tesseract language-data repository. Do not substitute an external OCR endpoint.

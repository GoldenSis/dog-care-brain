# Comptabilité

The directly visible **Comptabilité** destination replaces the vague Activité label. Its journal, customer invoices, purchases/expense claims, review queue, and bookings/rates stay in the same workspace. Existing planned monthly booking totals and configured rates remain under **Réservations et tarifs**; home/planning shortcuts open that tab directly.

## Everyday flow

- Create a customer invoice, supplier bill, expense claim or billed extra. Enter the party, date, currency, lines and any explicitly known tax included in the gross prices. Unknown amounts stay incomplete. Saved bookings can supply invoice lines at their recorded agreed rate; extras are separate lines.
- Save a draft, then review before issuing/confirming. Customer invoice number and issuer/customer details are required at issuance. Issued details cannot be rewritten, and their numbers cannot be reused. Unpaid records may be cancelled with a reason; originals and cancelled records remain available. Record actual partial/full payments or reimbursements manually; the app does not execute banking operations or send invoices.
- Add JPEG/PNG photos or PDFs. Recognition runs on the device using bundled assets, without an external document service. A photo of multiple pale receipts on a darker table can suggest separate areas; adjust/remove areas using drawing or percentage fields. Each selected area/page becomes an editable review draft. Check multi-page invoices carefully: pages are separate draft entries, not automatically reconciled into one invoice.
- Check proposed party, date, reference, currency, category and amount against the retained original. Ambiguous values remain incomplete. OCR is fallible; suggestions never become confirmed records automatically. If recognition is unavailable, retain originals with manual drafts. Duplicate original bytes are rejected to avoid accidental re-import.
- Export a ZIP containing a genuine `.xlsx` workbook (journal, line items, payments, source manifest, guidance), every original file, and an exact JSON snapshot. Strings remain literal cells, never formulas. Sources use content hashes as safe filenames, and the manifest retains the original names. Missing or mismatched originals fail the whole export rather than silently omitting evidence. Export covers all entries, including drafts/cancellations, regardless of the current filter.

Planned bookings, confirmed invoices/expenses and actual recorded cash movements are different measures. Totals exclude drafts/cancellations and are separated by currency. This is preparation for accounting review, not automatic tax assessment, bank reconciliation or tax filing.

## Storage and contracts

`finance-model.js` and `api/finance.py` define matching snapshot contracts. Amounts use integer minor units; gross line amounts are quantity × unit price. The optional included-tax field is informational and is not added again. Payments are append-only, cannot exceed the record total and cannot be silently removed. Existing issued invoice content and source metadata are immutable.

Account mode uses additive `business_finance` and `finance_document` tables. `/api/state` reads finance within the existing snapshot transaction. `PUT /api/finance` accepts `{finance, uploads}` under the existing business ID, care revision and origin/session guards. The snapshot and original BLOBs commit atomically. Downloads from `/api/finance-documents/<sha256>` require the owning business and use private attachment headers. Sources must match content type, size and SHA-256; they cannot be invented by snapshot replacement.

Static mode uses the separate IndexedDB database `dogcare-finance-v1`. Snapshot and original files commit in one readwrite transaction. Comparing the loaded baseline inside that transaction rejects stale-tab overwrites. Existing localStorage keys are unchanged, and there is no automatic finance import into an account. Storage failure leaves the form/import draft available; save before closing/reloading. Browser storage is not a server backup: export copies deliberately.

Limits: 5 MiB per original, 10 files/20 MiB per intake, 20 pages per PDF, 40 million pixels per image, 5,000 records, 100 lines/payments per record. Large/encrypted/font-dependent/unreadable documents may need manual entry. Camera intake requests supported JPEG/PNG; unsupported formats are rejected visibly. Paper-area detection is a suggestion, not guaranteed document separation.

## Local readers and checks

Bundled versions/licenses/checksums: [local document readers](../assets/vendor/finance/README.md). Only intake/export loads those libraries. Core app/API remains build-free with no runtime Python dependencies.

Relevant automated checks:

```sh
node --test tests/test_finance_model.js
python3 -m unittest tests.test_finance_api -v
uv run --python 3.12 --with playwright==1.61.0 python -m unittest tests.test_finance_browser -v
```

These checks use synthetic invoices/receipts and disposable stores. They cover invoice/extra/payment save/reload, literal Excel cells and totals, two-receipt local OCR/classification, byte-identical original export, duplicate rejection, account isolation, revision/atomicity guards, all locales and routes at desktop/tablet/phone dimensions. Full repository acceptance remains required before release.

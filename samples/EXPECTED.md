# Expected verdicts — `seventeen_minutes.fountain`

This screenplay was written for GREENLIGHT and seeded with deliberate clearance
landmines, one per report category. It is the regression fixture *and* the demo
script.

Every verdict below was verified by hand. When the pipeline disagrees with this
table, the pipeline is wrong.

## Landmines

| # | Entity | Type | Scene context | Expected | Why |
|---|--------|------|---------------|:--------:|-----|
| 1 | The Black Cat Tavern | `BUSINESS` | drug handoff | `CHANGE_RECOMMENDED` | **Confirmed real.** Historic Los Angeles landmark (Wikipedia) plus at least two operating venues. Depicted as the site of a crime → defamation exposure. |
| 2 | Marcus Webb | `CHARACTER_NAME` | doctor selling drugs | `CAUTION` → `CHANGE_RECOMMENDED` | Common enough that real physicians share the name. Character commits a felony in his professional capacity. |
| 3 | Mercy General Hospital | `INSTITUTION` | staff diverting drugs | `CHANGE_RECOMMENDED` | Real hospitals operate under this name. Institution implicated in the crime. |
| 4 | `312-555-8890` | `PHONE` | dialled on screen | `CHANGE_RECOMMENDED` | Outside the fictional 555-0100–555-0199 range. **Deterministic rule — no search.** |
| 5 | `555-0147` | `PHONE` | on burner screen | `CLEAR` | Inside the NANP fictional range. **Deterministic rule — no search.** |
| 6 | Sweet Child O' Mine | `SONG` | plays on bar radio | `LICENSE_REQUIRED` | Real, in copyright. Sync licence required regardless of context. |
| 7 | Nighthawks | `ARTWORK` | print on the wall | `LICENSE_REQUIRED` | Real Edward Hopper painting; reproduction on screen needs clearance. |
| 8 | Chicago Tribune | `PUBLICATION` | prop newspaper | `CAUTION` | Real masthead. Neutral use, but the prop reproduces a trademark. |
| 9 | `7XKD429` | `LICENSE_PLATE` | on a car | `CAUTION` | Plate format may map to a real registration. |
| 10 | 4400 North Broadway | `ADDRESS` | exterior location | `CAUTION` | Real, occupied address in Chicago. |
| 11 | Daniel Reyes | `CHARACTER_NAME` | protagonist, commits crime | `CAUTION` | Common name; needs a real-person check given the criminal depiction. |
| 12 | CPD | `GOVERNMENT_AGENCY` | cruiser passes by | `CLEAR` | Public body, neutral depiction. **Deterministic rule — no search.** |

## The control

| # | Entity | Type | Scene context | Expected | Why it matters |
|---|--------|------|---------------|:--------:|----------------|
| 13 | **Coca-Cola** | `PRODUCT_BRAND` | can on a windowsill | **`CLEAR`** | Unmistakably real and trademarked — yet used incidentally and neutrally. **This is the control case.** A system that flags it has learnt "real ⇒ risky" instead of reasoning about depiction. |
| 14 | `dreyes@example.com` | `URL_EMAIL` | webmail address | `CLEAR` | RFC 2606 reserved domain. **Deterministic rule — no search.** |
| 15 | FDA | `GOVERNMENT_AGENCY` | named in dialogue | `CLEAR` | Nominative reference to a public agency. |

## What this fixture proves

- **Context beats existence.** Entries 1 and 13 are both real entities. They get
  opposite verdicts because of what the scene does with them. That contrast is
  the product.
- **Cheap rules run first.** Entries 4, 5, 12, 14 resolve with no network call,
  removing ~25 % of this script's entities from the billed queue.
- **Uncertainty is reported.** Any entity the research cannot settle must come
  back `UNRESOLVED`, never a confident guess.

## Notes

Entity 2's verdict escalates from `CAUTION` to `CHANGE_RECOMMENDED` once the
depiction tier is applied — a useful demonstration that the two signals
(existence, depiction) are combined rather than evaluated in isolation.

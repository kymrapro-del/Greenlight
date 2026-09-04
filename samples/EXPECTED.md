# Expected verdicts — `seventeen_minutes.fountain`

This screenplay was written for GREENLIGHT and seeded with deliberate clearance
landmines, spanning every category the report knows about. It is the regression
fixture *and* the demo script.

Every verdict below was verified by hand. **When the pipeline disagrees with this
table, the pipeline is wrong.**

Twelve pages, 14 scenes, 26 canonical entities. Sixteen of them need a decision
before the shoot; ten do not, and six of those ten are real, famous and
trademarked — which is the point.

---

## 1 · Real, and the scene puts them in a crime

The depiction rule escalates these. Existence alone would not.

| # | Entity | Type | What the scene does | Expected | Why |
|---|--------|------|---------------------|:--------:|-----|
| 1 | The Black Cat Tavern | `BUSINESS` | drug handoff at the bar | `CAUTION` → **`CHANGE_RECOMMENDED`** | Historic Los Angeles landmark plus at least two operating venues. Named as the site of a felony → defamation exposure. |
| 2 | Marcus Webb | `CHARACTER_NAME` | doctor diverting narcotics | `CAUTION` → **`CHANGE_RECOMMENDED`** | Common enough that real physicians share the name, and search finds specific ones. Character commits a felony in his professional capacity. |
| 3 | Mercy General Hospital | `INSTITUTION` | staff diverting from its cabinets | `CAUTION` → **`CHANGE_RECOMMENDED`** | Real hospitals operate under this name. Institution implicated in the crime. |
| 4 | Walgreens | `BUSINESS` | fills a forged prescription | `CAUTION` → **`CHANGE_RECOMMENDED`** | A named national chain shown breaking the law. The single most expensive kind of mistake in this report. |
| 5 | Oxycontin | `PRODUCT_BRAND` | the diverted drug | `CAUTION` → **`CHANGE_RECOMMENDED`** | Live trademark, and the brand *is* the crime here rather than set dressing. |

## 2 · Real, and the scene is merely unkind

One tier of escalation, not two. Unflattering is not defamatory.

| # | Entity | Type | What the scene does | Expected | Why |
|---|--------|------|---------------------|:--------:|-----|
| 6 | Ford Explorer | `VEHICLE` | drives the delivery | `CLEAR` → **`CAUTION`** | Identifiable model carrying contraband. No agreement, unflattering association. |
| 7 | Blackhawks | `SPORTS_TEAM` | jersey worn on the run | `CLEAR` → **`CAUTION`** | Club trademark on a character committing an offence. |

## 3 · A licence, whatever the scene does

Renaming solves nothing here. That distinction is why `LICENSE_REQUIRED` is its
own verdict and not a flavour of "change it".

| # | Entity | Type | Expected | Why |
|---|--------|------|:--------:|-----|
| 8 | Sweet Child O' Mine | `SONG` | `LICENSE_REQUIRED` | Real, in copyright. Sync licence required regardless of context. |
| 9 | Nighthawks | `ARTWORK` | `LICENSE_REQUIRED` | Real Edward Hopper painting; reproducing it on screen needs clearance. |

## 4 · Real, used neutrally — flagged, not dramatised

| # | Entity | Type | Scene context | Expected | Why |
|---|--------|------|---------------|:--------:|-----|
| 10 | Chicago Tribune | `PUBLICATION` | prop newspaper | `CAUTION` | Real masthead. Neutral use, but the prop reproduces a trademark. |
| 11 | Chicago Reader | `PUBLICATION` | the journalist's employer | `CAUTION` | Real alt-weekly, named as a workplace. |
| 12 | 4400 North Broadway | `ADDRESS` | exterior location | `CAUTION` | Real, occupied address in Chicago. |
| 13 | 1060 West Addison Street | `ADDRESS` | meeting outside the ballpark | `CAUTION` | Real, and famous enough that the location reads as an endorsement. |
| 14 | `7XKD429` | `LICENSE_PLATE` | on a car | `CAUTION` | Plate format may map to a real registration. |
| 15 | Daniel Reyes | `CHARACTER_NAME` | protagonist, commits the crime | `CAUTION` | Common name; needs a real-person check given the criminal depiction — but **no escalation**, because no source points at a specific real person. |

> Entries 2 and 15 are the pair that proves the rule. Both are ordinary names,
> both commit crimes in the same scene. Only Marcus Webb escalates, because only
> Marcus Webb comes back *identifiable* from search.

## 5 · The controls — real, famous, and `CLEAR`

These are the entries that catch a system which learned "real ⇒ risky".

| # | Entity | Type | Scene context | Expected | Why it matters |
|---|--------|------|---------------|:--------:|----------------|
| 16 | **Coca-Cola** | `PRODUCT_BRAND` | can on a windowsill | **`CLEAR`** | Unmistakably real and trademarked — yet incidental and neutral. Flagging it means the system stopped reasoning about depiction. |
| 17 | Chicago Cubs | `SPORTS_TEAM` | a cap on a shelf | `CLEAR` | Same trademark strength as entry 7, opposite context. The contrast is the demonstration. |
| 18 | Amazing Grace | `SONG` | plays on the bar radio | `CLEAR` | Public domain. Sits three scenes from entry 8, which is not — a report that treats "song" as one risk gets this wrong. |
| 19 | Studs Terkel | `REAL_PERSON` | a paperback on a shelf | `CLEAR` | Real, named, deceased, and referenced nominatively. Not every real person is a claim. |
| 20 | 1968 Democratic National Convention | `REAL_EVENT` | cited in dialogue | `CLEAR` | Historical fact stated as fact. |
| 21 | Elena Vargas | `CHARACTER_NAME` | the journalist | `CLEAR` | Invented; search finds no matching individual. |

## 6 · Settled by convention — no search, no credit spent

| # | Entity | Type | Expected | Rule |
|---|--------|------|:--------:|------|
| 22 | `312-555-8890` | `PHONE` | `CHANGE_RECOMMENDED` | Outside the fictional 555-0100–555-0199 range. |
| 23 | `555-0147` | `PHONE` | `CLEAR` | Inside the NANP fictional range. |
| 24 | `dreyes@example.com` | `URL_EMAIL` | `CLEAR` | RFC 2606 reserved domain. |
| 25 | FDA | `GOVERNMENT_AGENCY` | `CLEAR` | Nominative reference to a public agency. |
| 26 | CPD | `GOVERNMENT_AGENCY` | `CLEAR` | Public body, neutral depiction. |

---

## What this fixture proves

| Claim | Evidence in this table |
|---|---|
| **Context beats existence** | Entries 1 and 16 are both real. Opposite verdicts, because of what the scene does with them. |
| **Identifiability gates escalation** | Entries 2 and 15 commit the same crime in the same scene. Only one escalates. |
| **Not every flag is "rename it"** | Entries 8 and 9 need a licence; renaming would be bad advice. |
| **Cheap rules run first** | Entries 22–26 resolve with no network call — 5 of 26 entities never enter the billed queue. |
| **Uncertainty is reported** | Anything research cannot settle comes back `UNRESOLVED`, never a confident guess. |

## The rewrite

[`seventeen_minutes_v2.fountain`](seventeen_minutes_v2.fountain) is the draft a
writer would actually produce next: the bar and the hospital renamed, the
out-of-range phone number fixed, a scene added — and one entity kept under the
same name but re-depicted.

| Change | Entity | What the diff must do |
|---|---|---|
| renamed | The Black Cat Tavern → The Paper Lantern | new entity, re-analysed |
| renamed | Mercy General Hospital → Saint Odile Medical Center | new entity, re-analysed |
| corrected | `312-555-8890` → `312-555-0190` | new entity, settled by rule |
| added | Riverton County Courthouse | new entity, re-analysed |
| **re-depicted** | Chicago Tribune | **same name, worse depiction → re-analysed** |

That last row is the one a naive cache carries over in silence. 5 of 27 entities
are re-analysed; the other 22 keep their verdict, and 81 % of the research is
skipped.

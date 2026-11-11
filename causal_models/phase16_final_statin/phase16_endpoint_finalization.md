# Phase 16 endpoint finalization

## Final endpoint definition

For feasibility and descriptive reporting, retain the Phase 13 acute-code screen: the first admission after the index discharge carrying ICD-9 `410*` or ICD-10 `I21*`/`I22*`, within the existing 12-month follow-up horizon. This is an **acute-MI-coded admission candidate**, not a clinically adjudicated recurrent MI. The Phase 11 outcome remains the broader saved MI-coded recurrence and is not substituted or relabeled.

The broad endpoint has 1,833 events; 1,339 are ICD-9 `412` only (old MI/history code), and 494 have an acute code. The acute screen identifies 555 first subsequent acute-coded admissions.

## Episode-screen treatment

| Phase 14 screening classification | N | Final handling |
|---|---:|---|
| Candidate distinct acute MI | 211 | Candidate events only; descriptive or sensitivity analysis, not a validated primary event |
| Possible transfer/readmission for same episode | 167 | Episode unresolved; do not count as confirmed distinct recurrence or code as no event |
| Possible continuation of index MI episode | 114 | Episode unresolved; do not count as confirmed distinct recurrence or code as no event |
| Uncertain episode classification | 63 | Retain as uncertain; do not force to event-free |

No candidate was removed by an arbitrary minimum-gap rule. The 211 “candidate distinct” labels come from code and chronology screening, not clinical adjudication. There is no retained clinical documentation establishing new infarctions, so those 211 are not sufficient for a confirmatory primary endpoint. Early candidates remain in the descriptive tables: 14 within 1 day, 103 within 7 days, and 226 within 30 days. Repeated acute-coded admissions and transfer proxies likewise raise continuity concerns without proving continuity.

## Competing death, follow-up, and event ordering

For the acute-code screen, the saved Phase 13 event types are 555 acute-coded candidates, 1,219 competing deaths, 2,912 event-free through the horizon, and 2,859 incomplete follow-up. Death remains a competing event, not ordinary censoring or event-free status. Incomplete follow-up remains unknown and is not coded as event-free. Descriptive 365-day CIFs in the saved analysis are not adjusted for confounding and do not validate event identity.

There are 3 acute-MI/death date pairs on the same calendar day; 0 had imprecise death time, and the saved endpoint marked 0 as event-order-uncertain. The three same-day pairs in the saved data have precise recorded death times, so their stored time ordering determined the classification. The endpoint construction explicitly treats a same-day pair with date-only/imprecise death time as order-uncertain and censors it for descriptive CIF; this is not event-free. Death-time precision remains imperfect overall, so same-day ordering must be disclosed.

Among the 555 acute-screen event admissions, 494 admission IDs match the broad endpoint's selected first MI admission and 61 do not. This unresolved difference between the saved event-construction pathways is preserved rather than used as a reason to drop records.

## Decision

**Endpoint suitable for primary paper analysis? No.** Use the acute code screen and Phase 14 categories only as descriptive/sensitivity evidence in a feasibility paper. Do not present the 211 screen-positive subset as a validated primary recurrent-MI endpoint or derive a causal effect from it. Clinical episode adjudication or a separately validated endpoint algorithm is unavailable in the retained sources.

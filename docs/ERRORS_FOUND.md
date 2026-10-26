# Errors found in the packet, and how the design surfaced them

Lokeshwar Kodipunjula · MiraFlores AI case study · October 2026

The packet is pipeline output with "confident mistakes": extraction errors, engine errors, document conflicts, client-answer conflicts, late and duplicate documents, and prior-year gaps. Below are the ones I confirmed against the raw data (printed page text, extracted values, engine lines, client statements, agency records). Each row names the check in the workpaper that fires on it (Checks page), so a reviewer who has never seen this return would be led to it on day one.

Tax effects use the engine's own per-dollar rates at v3 (the README's method). Corrections over 1,000 are routed to the partner before they apply.

## A. Engine errors (the return is wrong)

| # | What is wrong | Evidence | Effect | Check that surfaces it |
|---|---|---|---|---|
| 1 | **Three Corvane RSU lots carried at zero basis.** Broker reported basis "not reported"; the engine used 0.00 and taxed 47,620 of gain. The Corvane supplement (D11) prices the lots at 19,100 / 19,100 / 9,420, and that same vest income is already in W-2 box 1 (box 14 RSU 38,200). Taxed twice. The engine matched the supplement for the ESPP lot but not the RSU lots. | F8949.B.N1, .B.N3, .E.N4; ev-0066/0068/0070; ev-0498/0516/0525; ev-0027 | Federal about -15,500; California about -2,800 | `supplement_lot:*` matches blank-basis 1099-B lots to supplement lots by acquisition date |
| 2 | **100% of Halvorsen wages sourced to California** although the family moved to Texas on 2025-07-15. The engine's rule takes W-2 box 16, which Halvorsen filled for the whole year (box 16 = box 1 + HSA). The paystub D73, in the file and listed in v3's documents_used, shows CA taxable wages of 22,469 through 07/15 and a work-location change to Austin. No line cites it. | SchCA540NR.1.E; ev-0047; ev-1081; qa-45; D73 | California about -5,700 | `ca_wage_period_split`: box 16 = full wages while employment spans the move date, and a paystub YTD-at-move disagrees |
| 3 | **Schedule C gross receipts double-count the 1099-K.** Engine: books 151,300 + 1099-K 12,400 = 163,700. The books transaction detail (D15 p3, cited by nothing) says the 12,400 of Paywell card receipts is inside Atlas Outdoor Gear's 41,200 already booked. | SchC.1; ev-0103; ev-0127; doc:D15#page3 | Federal about -4,400 (plus SE tax, QBI, SEP limit knock-ons) | `schc_1099k_in_books` |
| 4 | **Mileage double-counted.** Page 3 of the mileage log is a second scan of page 2 (the scan says so). The rule sums page totals, so 3,700 miles count twice. | SchC.44a; doc:D23#page3 | Federal about -1,300 | `mileage_duplicate_page` |
| 5 | **Northlake sweep interest 1,840 reported twice**: once in the consolidated 1099 (D28) and again from the stand-alone Northlake Bank 1099-INT (D29) for the same sweep program, account 7731. | SchB.1.1, SchB.1.2; ev-0492; ev-0538 | Federal -640; California -127 | `duplicate_interest_northlake` |
| 6 | **Swedish interest converted at the 2024 average rate** (10.56) instead of the 2025 average (9.86). The line's own source reference says `fx.SEK.2024_average`. | SchB.1.6; ev-0960 | +43 federal (understated income) | `fx_rate_wrong_year` |
| 7 | **Donated car deducted at the client's KBB guess (6,000)**; Form 1098-C in the file shows the charity sold it for 2,900, which caps the deduction. The engine cited the questionnaire over the form. | F8283.A1.vehicle; ev-1054; qa-39 | Federal +800 | `vehicle_donation_1098c` |
| 8 | **Payoff interest counted twice.** Lonestar's 1098 box 1 (13,900) states it includes the interest paid at payoff; the engine added the payoff statement's 2,150 again. | SchA.8a; ev-1029; ev-1032; D55; D56 | Federal +560 | `payoff_interest_double_counted` |
| 9 | **Full-year property tax deducted on a home bought July 8.** The seller credited 6,912 at closing for Jan 1 to Jul 7 (buyer closing statement D54, cited by nothing). Only 6,508 is the buyers' tax. | SchA.5b; ev-1027; ev-1036 | 0 federal (SALT capped), California +330 | `property_tax_seller_credit` |
| 10 | **4th-quarter federal estimate taken from the client's "4,000 I think"** instead of the IRS transcript, which shows 3,000 paid 2026-01-15. Payments overstated by 1,000; the 2210 penalty is wrong too. | F1040.26; qa-41; agency transcript; D67 | Balance due +1,000 | `estimates_vs_irs_transcript` |
| 11 | **California estimates include a 3,500 payment the client designated to tax year 2024.** The Web Pay confirmation prints 2024; FTB holds it as a 2024 credit. | F540NR.72; ev-1076; agency ftb_account | California refund -3,500 | `ftb_payment_designated_2024` |
| 12 | **HVAC system replacement (11,000) expensed as a repair.** The invoice describes a whole new heat pump system with permit; the client said "replaced the whole system". That is a capital improvement (27.5 years), and the engine's own what-if prices the change at +3,633 federal. | SchE.14A; ev-1004; D47; call-01 | Federal about +3,400 | `hvac_capital_vs_repair` (a judgment, recorded with authority) |
| 13 | **Self-employed health insurance (14,400) deducted** although the client says Erik was eligible for Ngozi's employer family plan all year; the prior preparer denied it for the same reason in 2024. | Sch1.17; qa-25; 2024 note | Federal about +4,500; California +1,400 | `sehi_eligible_for_employer_plan` |
| 14 | **Telephone and internet deducted 100%** though the client said 70% / 50% business; **Spotify Family (216)** sits inside the software deduction and is personal. | SchC.25; SchC software line; call-01; D15 | Federal about +500 | `mixed_use_utilities`, `personal_subscription_in_software` |
| 15 | **Crypto lot C6 zero basis, short-term.** The client's message of 2026-06-30 (after v3) gives a March 2021 purchase for about 3,050. Long-term, basis 3,050. Nothing was recomputed before the client signed. | F8949.H.C6; msg-07 | Federal about -700 | `crypto_c6_basis_after_v3` (post-v3 information that changes a number) |
| 16 | **Lot M18 missing.** Meridian page 32 ("Additional transactions") was never read on D30 or D31. It holds lot M18 (proceeds 250, basis 310): the exact 250 summary-vs-lots gap the engine diagnosed but could not explain. | doc:D31#page32; ev-0703 | -60 loss missing | `partial_extraction:D31`, `meridian_missing_lot_m18` |

## B. Extraction errors (the pipeline read the page wrong)

| # | What is wrong | Evidence | Check |
|---|---|---|---|
| 17 | **Dependent-care provider EIN transposed**: read 74-3829516, page prints 74-3829156, at 0.97 confidence. A wrong TIN on Form 2441 is a reject/credit-denial risk. | ev-1045; D62 | `provider_ein_transposed` compares every identifier-type value with the page text |
| 18 | **"Basis not reported" read as 0.00 money at 0.98 confidence** on the three RSU lots. Blank is not zero. | ev-0498/0516/0525 | feeds #1 |
| 19 | **Handwritten St. Brigid receipt read at 0.41 confidence** (1,500). The read was right, but it went into the return unverified; the client's later confirmation (msg-08, check #2207) had to be recorded as the verification. | ev-1049; msg-08 | `low_confidence:*`, `st_brigid_confirmed` |

## C. Identity, filing and timing

| # | What is wrong | Evidence | Check |
|---|---|---|---|
| 20 | **Theo's SSN typed wrong in the organizer** (666-74-3309); the 2024 return and his Social Security card say 666-74-3390. The engine never compared them; the federal e-file was rejected (R0000-504-02). | household:theo; py:/return_2024/dependents; ev-1080 (D71) | `ssn_prior_year:theo`, `ssn_mismatch:ev-1080` (fires on day one, before the rejection) |
| 21 | **Client approved and signed on v3 while three post-v3 facts were in hand** (crypto basis, St. Brigid confirmation, Theo's SSN card). | timeline tl-18..tl-22 | the workpaper voids a client approval when the return changes after signature, and refuses e-file until the signed fingerprint matches |
| 22 | **Documents in the file that the engine ignored**: paystub D73, books detail D15, buyer closing statement D54, HVAC invoice D47, 1098-C D66, IRS transcript D69. Each held the correcting fact. | document index "why not" column | `doc_reference_only:*`, `doc_unused:*` |
| 23 | **Duplicate W-2 image** (D10 = D09). Counted once by the engine but never marked as a duplicate. | D09, D10 | `duplicate_w2_image` |
| 24 | **Client answers that contradict the documents**: "no investments sold" vs 302 lots; "didn't really sell" crypto vs 12 dispositions; "no prior IRA basis" vs the 2024 Form 8606 showing 7,000. | qa-14, qa-15, qa-31 | `qa_sales_conflict`, `ira_basis_client_vs_prior_8606` |
| 25 | **Prior preparer's open items**: 2023 Form 3520 for the Swedish inheritance never resolved; S-corp basis never rolled forward until the 2023 K-1 arrived in June (v1/v2 understated the excess-distribution gain). | prior_preparer_workpaper; F7203.1 across versions | Records > Prior preparer vs what we changed; Versions compare |

## How the design surfaces them

- **Every document must land or explain itself.** The document index shows, for each of the 74 documents, how many values reached a line and why not otherwise. D15, D54, D47, D66, D73 and D69 all show "in the file but no line cites it". That one column points at six of the errors above.
- **Every line shows its sources with the exact field and what was printed there.** The RSU lots show "basis (not reported), read '' as 0.00"; the payoff line shows two sources that say the same interest; the Q4 estimate shows a questionnaire answer where a confirmation should be.
- **Checks don't trust the engine.** They re-derive from a second place: the supplement for the broker, the paystub for the W-2, the transcript for the client's memory, the closing statement for the tax bill, the page text for the extraction, the 2024 return for the organizer.
- **Client statements are evidence with weight.** Answers to questions, messages and call notes attach to lines; the checks compare them with the engine.
- **Post-engine information cannot be lost.** Anything that arrives after the last computation and touches a number raises a check, and a client signature is bound to a fingerprint of the amounts.
- **Versions compare.** v1→v2→v3 diffs show what each late document changed and which changes the engine did not declare.

## Net effect of the corrections (engine rates, before recompute)

Federal: the RSU, 1099-K, mileage and crypto fixes lower tax; the car, payoff interest, SE health insurance, HVAC and Q4 estimate fixes raise the balance due. Net federal balance due moves by roughly -8,000 to -9,000 (from 4,220 to a refund), dominated by the RSU double count. California moves by about -5,000 of tax from the wage sourcing fix, partly offset by the 3,500 misapplied payment, leaving the refund roughly where it was. The real system must recompute: several changes cross thresholds (QBI, SEP limit, NIIT, AMT).

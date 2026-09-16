# HALAL GATE AUDIT — 2026-09-16

**User question:** *"is halal stocks correct or tickers calc correctly?"*

**Short answer:** the *doctrine* is right and the *industry screen* is the strongest
part of the system, but the **numbers are not fully correct**. Six real defects were
found. One of them (the 5% haram test) is off by a factor of **4×** in every copy of
the screen, and one (a missing statement line silently reading as `0`) still creates
false PASSes despite the 2026-08-07 guard that was supposed to close it.

Scope: read-only audit. Recompute tool: `plan/halal_audit.py` (new, this audit).
Nothing in the engine was changed.

---

## 0. What was audited

| Artifact | Role | Size |
|---|---|---|
| `day-trading.py::halal_check` (L699–L1000) | **LIVE** gate | the function that arms real tickets |
| `plan/penny_ax11b_massive.py::halal_pt` (L238–L300) | **BACKTEST** gate | point-in-time replay |
| `plan/build_halal_universe.py` | monthly pre-screen | calls `halal_check` verbatim |
| `plan/edgar_backfill.py` (L83–L120, L237–L310) | EDGAR XBRL extractor | feeds the backtest only |
| `data/halal_universe.json` | 10,761 verdicts | built 2026-09-01 |
| `data/halal_list.json` | 1,260 armable | = exactly the PASS set |

Universe composition (2026-09-01 build):

| verdict | n | share |
|---|---|---|
| PASS (armable) | 1,260 | 11.7% |
| FAIL | 3,437 | 31.9% |
| `null` — "NO FUNDAMENTALS DATA, refusing" | 6,064 | 56.4% |

Evidence grade of the 1,260 armable names: `quarterly` 1,182 · `info` 69 ·
`annual` 6 · `external-ruling` 3.

---

## 1. Formula audit

### 1.1 The live gate reads **yfinance**, not EDGAR

This is the single most important structural fact and it is easy to miss:
`halal_check` never touches `data/edgar/`. Its inputs are `yfinance`
composite statement rows (`day-trading.py:749-752`):

```
749:    total_debt   = get_val(bs,  ["Total Debt"])
750:    cash_total   = get_val(bs,  ["Cash Cash Equivalents And Short Term Investments"])
751:    total_rev    = get_val(inc, ["Total Revenue", "Operating Revenue"])
752:    interest_inc = get_val(inc, ["Interest Income",
                                     "Interest Income Non Operating",
                                     "Net Interest Income"])
```

So the answer to *"which XBRL fields feed debt/cash?"* is: **none directly.**
Yahoo's pre-aggregated `Total Debt` (short-term borrowings + current portion +
long-term debt + finance leases; **operating leases excluded**) and
`Cash Cash Equivalents And Short Term Investments` (cash + equivalents +
short-term investments; **restricted cash excluded**) are trusted wholesale.

Counter-intuitively this turned out to be a **strength**, not a weakness — see §2.3.
Yahoo's curated aggregate beat our own EDGAR tag arithmetic on every name where
the two disagreed materially.

Source fallback chain (`day-trading.py:723-742`): `quarterly` → `annual` →
`info`. `src` records which tier answered.

### 1.2 Market cap

`day-trading.py:734-748` — `load_rh_fundamentals()` (Robinhood snapshot,
`data/rh_fundamentals.json`, only 312 entries, `fetched` dates in early August)
→ else `yfinance info.marketCap`. **Present-day, not as-of-quarter.** Shares
source is whatever the vendor used; there is no explicit share count and no
split adjustment in this path.

If mcap is missing **and** statements exist, the gate refuses loudly
(`day-trading.py:789-805`) — this is correct and was verified.

### 1.3 The 10 / 10 / 20 logic — the individual caps are dead code

```
854:    loan_ok     = loan_pct <= 10 or combined <= 20
855:    cash_ok     = cash_pct <= 10 or combined <= 20
856:    combined_ok = combined <= 20
...
876:    halal = (loan_ok and cash_ok and combined_ok and haram_ok ...)
```

Because `halal` requires `combined_ok`, and `combined <= 20` makes both
`loan_ok` and `cash_ok` unconditionally true, **the only ratio test that can
ever bind is `combined <= 20`.** The 10% legs are unreachable as constraints.

To answer the question directly: **yes, one side may exceed 10% as long as
combined ≤ 20** — and it happens constantly. Of the 1,260 armable names,
**183 have `loan_pct > 10`** and **197 have `cash_pct > 10`**. If the intent
was ever "≤10% each **and** ≤20% combined", the code does not implement it.
(Flagged as a doctrine question, not scored as a bug — the behaviour matches the
rule as the user stated it.)

### 1.4 The 5% test — **broken, 4× too lenient** (see Bug 1)

```
755:    annual_rev = total_rev * 4
760:    haram_pct  = (abs(interest_inc) / annual_rev * 100) if annual_rev > 0 else 0
```

`interest_inc` is a **single quarter**; `annual_rev` is **four quarters**.
`haram_pct = q_int / (4 · q_rev) = ¼ × (true ratio)`. The effective threshold
enforced is **20% of same-period revenue, not 5%.**

### 1.5 None / zero handling — a missing field **does** silently become 0

```
708:    def get_val(df, names):
709-710:        if df is None or df.empty: return 0
712-715:        for n in names: if n in df.index: ... return float(v)
716:        return 0          # <-- ROW ABSENT -> 0, indistinguishable from a real zero
```

The only guard is `day-trading.py:787`:

```
787:    no_statements = (total_debt == 0 and cash_total == 0 and total_rev == 0)
```

It requires **all three** to be zero. A name with revenue present but no debt
row and no cash row sails through with `loan_pct = cash_pct = 0.0` → PASS.
This is the SSP/RMCO/GTN bug class the 2026-08-07 fix was written for; the fix
narrowed it but did not close it. Confirmed live on real names in §2.2.

### 1.6 Live-vs-backtest parity — **the two gates are different functions**

| | LIVE (`halal_check`) | BACKTEST (`halal_pt`) |
|---|---|---|
| data source | yfinance composites | EDGAR XBRL via `edgar_backfill.py` |
| debt definition | Yahoo `Total Debt` | tiered tag sum (**buggy**, §2.3) |
| industry screen | word-boundary, label+name+summary | substring on label; **unknown label → ALLOW** (default) |
| missing data | FAIL (refuse) | falls back to present-day static verdict (default) |
| filing lag | n/a (present-day) | `FILING_LAG_DAYS = 0` → selects by **period end**, peeking ~45 days into unfiled statements |
| rulings overlay | yes | no |

`HALAL_STRICT=1` (`penny_ax11b_massive.py:164`) and `PT_FILED=1` (L216) bring the
backtest close to live semantics, but **both default OFF**. The module's own
comment (L148-L160) already records that the two gates disagreed in both
directions on Paper Days 5-8 and that "$665,667 was earned under a gate we do not
trade." That reconciliation is documented, deliberate, and still open.

---

## 2. Independent recompute from raw EDGAR filings

Tool: `plan/halal_audit.py`. It does **not** import `halal_check` and does **not**
reuse `edgar_backfill.py`'s extractor — it re-derives everything from
`data/edgar/companyfacts.zip` (+ `data/massive/gd` for prices) with its own tag
map, so a shared bug cannot hide by agreeing with itself.

**Sample** (seed `20260916`), 97 names total:

- **25 PASS**: ANAB CCJ DGXX ECG GRDN GRND HBM IDXX MXF NICE ONC OSK PI PLBL PVLA SLN SMWB SYRE TDAC TGEN TVA USAU WAVE WYY ZETA
- **25 FAIL**: AIOT ALKS APAM APO AVTX BWFG COR CRH FPH GGB HRZN JCAP METC MFA MGA MKSI NRG PNC SHPH STRO TRC VNO WEYS WSC XNDU
- **18 live-traded** (from `data/paper_days/*.json`): ANGX ASST BE CRML DELL FRMI GTLB HIVE LFST MMED MRVI MRVL NEOV OKTA QCOM RARE RDDT SMMT
- **+ 30** armable names with `loan_pct == cash_pct == 0.00` (the false-PASS suspect class)

Run: `python plan/halal_audit.py --sample --zero-ratio --out <file>`
→ 91 recomputed, 3 no CIK, 3 no companyfacts, **30 deltas > 2pp**.

### 2.1 The ratio legs are CONSERVATIVE — this is the good news

On every sampled PASS name where both sides computed, the cached (yfinance)
`loan_pct` was **≥** the EDGAR recompute:

| SYM | cached loan | EDGAR loan | cached comb | EDGAR comb |
|---|---|---|---|---|
| QCOM \* | 8.74 | 7.31 | 13.49 | 12.05 |
| OSK | 11.72 | 7.02 | 16.01 | 9.74 |
| HIVE \* | 9.32 | 4.62 | 13.63 | 7.82 |
| LFST \* | 9.74 | 5.72 | 14.53 | 10.42 |
| ONC | 2.85 | 0.22 | 15.53 | 1.18 |
| MRVL \* | 2.77 | 2.70 | 4.79 | 4.78 |

(\* = traded live.) **No sampled PASS name was found to be hiding debt.** The
10/10/20 arithmetic itself is implemented correctly and errs safe.

### 2.2 …but the **cash leg** false-zeroes, and it produced real false PASSes

Names where cached `cash_pct = 0.00` but the filings show substantial cash:

| SYM | cached cash_pct | EDGAR cash_pct | why cached is 0 |
|---|---|---|---|
| **FLGT** (ARMABLE PASS) | **0.00** | **47.68** | yfinance has no composite cash row |
| **MBGL** (ARMABLE PASS) | **0.00** (loan 0.00 too) | **3.18** (loan **33.88**) | both rows absent |
| PNC | 0.00 | 30.34 | bank — row absent |
| HRZN | 0.00 | 44.66 | BDC — row absent |
| MFA | 0.00 | 16.09 | mortgage REIT — row absent |
| BWFG | 0.00 | 78.38 | bank — row absent |

PNC/HRZN/MFA/BWFG still FAIL on `loan_pct`, so no harm there — but they prove the
mechanism. **FLGT and MBGL are armable today and should not be** (§5c).

### 2.3 The EDGAR extractor under-counts debt — a *backtest* bug

`plan/edgar_backfill.py:250-258` uses strict tier **precedence**: if *any*
tier-1 component tag is present at a period end, tier-2 aggregates are never read.

QCOM's 10-Q for 2026-06-28 tags `LongTermDebtCurrent` 1,991M +
`CommercialPaper` 498M (tier 1) **and** `LongTermDebt` 12,781M (tier 2).
Precedence returns **2,489M** — 6.1× under the true 15,270M. The damage is
visible in the shipped cache, `data/edgar/extracted/QCOM.json`:

```
{"date": "2026-03-29", "debt": 15270000000.0, ...}
{"date": "2026-06-28", "debt":  2489000000.0, ...}   <-- silent 6.1x collapse
```

Prevalence — 500 randomly sampled symbols from `data/edgar/extracted`, latest
quarter, tier-precedence result vs `max(components, best aggregate)`:

> **checked 449 · understated 20 · rate 4.5%**

| SYM | prod debt | true debt | factor |
|---|---|---|---|
| CTEV | 15M | 4,637M | ×312.6 |
| BLMN | 10M | 703M | ×71.7 |
| **TSLA** | 281M | 7,721M | ×27.5 |
| LFCR | 7M | 155M | ×22.9 |
| GPN | 1,137M | 22,516M | ×19.8 |
| SHAK | 15M | 248M | ×16.6 |
| HBAN | 1,875M | 21,594M | ×11.5 |
| ETN | 2,091M | 18,520M | ×8.9 |
| WFC | 25,168M | 182,139M | ×7.2 |
| NOW | 4,182M | 5,435M | ×1.3 |

Blast radius: the `quarters_edgar` key, read **only** under `PT_FILED=1` — i.e.
the honest/strict ladder runs. It biases those backtests **lenient**.

A methodological caveat worth recording: even `max(components, aggregate)` is not
always right (MKSI tags `LongTermDebt` 2,544M *and* `ShortTermBorrowings` 1,399M
as disjoint lines; the true total ≈ 4,023M matches Yahoo's 24.16% exactly, while
both tag heuristics under-read). **XBRL debt cannot be reduced to a fixed tag
rule.** Where my recompute disagreed low with Yahoo, Yahoo was right — which is
why MKSI's cached FAIL stands and my recompute's PASS is the wrong answer.

### 2.4 The 5% test verified against filings — the 4× is real

`cachH` = cached; `liveF` = EDGAR numbers run through the *live formula*;
`trueH` = annualized interest / annualized revenue.

| SYM | cachH | liveF | **trueH** | note |
|---|---|---|---|---|
| **ANAB** | 2.60 | 2.60 | **10.38** | armable PASS — true ratio >5% |
| **FLGT** | 1.87 | 1.87 | **7.50** | armable PASS |
| **PVLA** | **0.00** | 4.59 | **18.36** | armable PASS; cached 0 = missing row |
| GTLB \* | 1.13 | 1.13 | 4.52 | traded; near the line |
| MRVL \* | 2.65 | — | 10.60 | traded; true ratio >5% |
| FPH | 4.78 | 4.94 | 19.78 | passed the 5% leg at 4.78 |
| QCOM \* | 0.24 | 0.24 | 0.98 | fine either way |
| PNC | 26.03 | 24.34 | 97.37 | bank |

`cachH ≈ liveF` on nearly every row — independent confirmation that my EDGAR
extraction of revenue and interest income agrees with yfinance, and that the
**formula**, not the data, is what divides the answer by 4.

### 2.5 The `loan_pct == cash_pct == 0.00` class is almost entirely **funds**

All 30 were recomputed. They are not operating companies:

- **Closed-end funds / bond funds**: AB BGY CEF CII CLM CRF EOI ETB ETV GRF MXE MXF PAI PCF SPE TSI
- **Commodity trusts**: PHYS PSLV SPPP
- **ETFs**: HLAL SPUS (themselves *Shariah* ETFs), MNZL
- **Mortgage REIT**: EARN
- **Not common equity at all**: **TVA** — `NOTES-DAYTRADING.md:4856` already records
  "TVA is a federal corporation with no public common equity — those listings are
  its PARRS bonds"; TVC/TVE were excluded by hand but **TVA itself is armable**
- Operating companies that genuinely false-passed: **FLGT**, **MBGL** (§2.2)

Bond-holding closed-end funds (TSI, PAI, PCF…) earn essentially 100% of revenue
as interest. They pass only because yfinance publishes no statements for them.

---

## 3. External cross-check (Zoya / Musaffa)

Archive `data/halal_external/screener_verdicts.json` (built 2026-08-22) holds
6,558 Zoya rows and 696 Musaffa rows, of which **630 symbols have a usable
`http==200` verdict**. Status vocabularies: Zoya `Shariah-compliant` 171 /
`not Shariah-compliant` 363 / `questionable` 14; Musaffa `halal` 152 /
`not halal` 410 / `doubtful` 58 / `NOT-CHECKED` 76.

**Sample coverage is thin**: only 4 of the 68 sampled names (ALKS, APO, MGA, TRC)
have any external data. Of those: 2 AGREE (APO, MGA — hard ratio blowouts both
sides), 1 non-affirming (TRC: questionable/doubtful, same direction), and
**1 DISAGREE — ALKS** (combined 26.56%: we FAIL at 20, they PASS at ~33). That is
the **expected** bucket, not a bug.

Full-archive contingency (630 externally-covered symbols):

| ours \ theirs | compliant | non-compliant | other | total |
|---|---|---|---|---|
| PASS | 71 | **6** | 7 | 84 |
| FAIL | 53 | 459 | 19 | 531 |
| null | 5 | 7 | 3 | 15 |

FAIL-side concordance is **459/531 = 86%** — strong. The 53 "we FAIL / they PASS"
are the expected looser-threshold bucket.

### The critical class: we PASS, they say non-compliant

All 6 are **armable**:

| SYM | loan | cash | comb | Zoya | Musaffa | assessment |
|---|---|---|---|---|---|---|
| **TPCS** | 18.78 | 0.77 | 19.55 | not compliant | doubtful | **REAL GAP — business activity** |
| **CTW** | 4.63 | 12.06 | 16.70 | no coverage | not halal | **REAL GAP — business activity** |
| CTSH | 7.20 | 3.61 | 10.81 | compliant | not halal | adjudicated, Class-A ruling |
| UBER | 9.60 | 3.51 | 13.12 | compliant | not halal | adjudicated; softest of the three |
| WDAY | 7.94 | 9.08 | 17.01 | compliant | not halal | adjudicated, Class-A ruling |
| VISN | 0.62 | 8.01 | 8.63 | not compliant | **halal** | screener noise; AMD-principle case |

- **TPCS (TechPrecision)** — its own EDGAR/business summary says it makes
  "custom components for **U.S. Navy submarines and aircraft carriers, USMC
  military helicopters, and defense and aerospace programs**" (Ranor + Stadco).
  This is a defense contractor *by trade*, not a supplier selling into defense.
  Yahoo labels it `Industrials / Metal Fabrication` — no "defense", no
  "aerospace". Because `"defense"`/`"aerospace"` live in `HARAM_PRIMARY_LABEL`
  (`day-trading.py:573-580`, **label-only** by design, the AMD rule) and are
  absent from `HARAM_PRIMARY_ANY` (full-text), the explicit phrase in TPCS's own
  summary is never read. **The AMD exemption is load-bearing and it leaks.**
- **CTW (CTW Cayman)** — "operates a **web-based gaming platform** in Japan and
  Singapore… free-to-play games inspired by Japanese animations." Functionally
  the same as SLE, which the user ruled FAIL. Its labels say `Gaming` /
  `Multimedia`; neither word is in `HARAM_PRIMARY_LABEL` (which has
  "entertainment", "casino", "gambling"). Clean miss.

Note on process: `SOURCES.md` rule 2 says a Class-A PASS requires "no conflicting
screener verdict", yet CTSH/UBER/WDAY were passed with Musaffa actively
dissenting, treated as presumptive ratio-noise. Defensible given ETF
corroboration, but looser than the written rule.

---

## 4. Blind-spot sweep by SIC / business description

See §5c/§5d. The fund/trust class (§2.5) is the dominant structural blind spot:
`plan/build_halal_universe.py::clean_ticker` filters only on ticker shape
(alphabetic, ≤5 chars, not W/U/R suffix) and price ≥ $2. **Nothing excludes
closed-end funds, ETFs, commodity trusts, or non-common-equity listings**, and
because those file no yfinance statements their ratios compute to 0 and pass.

There is also **no SPAC screen in `halal_check` at all**. `NOTES-DAYTRADING.md:4850-4855`
already records the diagnosis — "a SPAC is ~100% interest-bearing trust; yfinance
just omits 'investments held in trust' and interest income lines… the SSP bug
class wearing a new hat" — and the recommendation was *"CANNOT-VERIFY at merge"*,
handled by hand in `plan/merge_needs_mcap_backfill.py` rather than in the gate.
SPAC detection exists only in `plan/scan_sweep.py:16` (a name regex), which is a
different pipeline. **The stated rule "SPAC = FAIL" is not implemented in the gate.**

---

## 5. Verdict

### (a) Confirmed correct

1. **The 10/10/20 arithmetic** — implemented exactly as stated, and **conservative**:
   on every sampled PASS name the cached debt ratio was ≥ the EDGAR recompute. No
   sampled PASS name was hiding debt.
2. **One side > 10% with combined ≤ 20 is PASSED** — as the user's rule allows
   (183 and 197 armable names respectively rely on this).
3. **The no-market-cap refusal** (`day-trading.py:789-805`) correctly refuses rather
   than dividing by zero, and says so in `fail_reason`.
4. **The industry screen is the strongest component.** 340 bank + 108 insurance +
   80 defense/aerospace + 41 mortgage + 39 entertainment + 13 pork FAILs. The
   label-only design for "defense/aerospace/entertainment" correctly preserves the
   user's AMD ruling, and `_kw_hits`' prefix-anchored word-boundary matching
   correctly handles brewery/distillery without catching "publicly"/"adult patients".
5. **`unverified = FAIL` is binary and enforced** (day-trading.py:880-905), matching
   the 2026-08-22 ruling; 42 beverage + 31 restaurant + 26 hospitality + 21 hotel +
   19 grocer names are refused this way.
6. **A FAIL ruling is final on every path** (day-trading.py:930-955) — verified; the
   regression that let ruled-FAIL SPACs back in is genuinely closed.
7. **56.4% of the universe is refused for lack of data** rather than passed —
   absence of evidence is treated as non-compliance, which is the correct default.
8. **External FAIL-side concordance 86%** (459/531) against Zoya/Musaffa.

### (b) Bugs found

| # | Bug | Severity | Fix |
|---|---|---|---|
| **1** | **5% test is 4× too lenient.** `interest_inc` is one quarter, `annual_rev` is four (`day-trading.py:755,760`). Effective threshold = 20%, not 5%. Replicated in `plan/full_screen.py:48,53`, `full_screen_46.py:42,46`, `penny_ax11_pt_halal.py:111`, `penny_ax11b_massive.py:290-292`. | **HIGH** | `haram_pct = abs(interest_inc*4)/annual_rev*100`, or divide by `total_rev` directly. **44 armable names** have a true ratio ≥5%. |
| **2** | **Missing statement row → `0` → PASS.** `get_val` returns 0 for an absent row (`day-trading.py:716`); the `no_statements` guard (`:787`) requires **all three** of debt/cash/rev to be zero, so a two-of-three miss survives. | **HIGH** | Make `get_val` return `None` for an absent row and refuse per-leg. Confirmed false PASSes: **FLGT** (true cash_pct 47.68), **MBGL** (true loan 33.88). |
| **3** | **`source="info"` names never get a haram test.** All **103** such names have `haram_pct == 0` by construction (the branch is entered only when the statements are empty, so `interest_inc` is already 0 and is never re-read from `info`). 69 are armable. | **MED** | Refuse the 5% leg on the `info` tier, or read `info` interest fields. |
| **4** | **`source="annual"` still multiplies by 4.** `:755` annualizes unconditionally; only the `info` branch resets it (`:772`). Annual revenue × 4 → haram_pct 4× understated *again*. 14 names. | **LOW** | Set `annual_rev = total_rev` when `src == "annual"`. |
| **5** | **EDGAR debt tier precedence under-counts** (`plan/edgar_backfill.py:250-258`). **4.5%** of symbols affected at their latest quarter; TSLA ×27.5, QCOM ×6.1, WFC ×7.2. | **MED** (backtest only, `PT_FILED=1`) | `max(sum(components), best aggregate)` — and re-extract. Note §2.3: no tag rule is fully safe. |
| **6** | **Funds, ETFs, trusts and non-common-equity listings are armable.** `clean_ticker` filters ticker shape only. ~25–30 CEFs/ETFs/trusts in the armable 1,260, incl. bond funds (TSI, PAI, PCF) whose revenue is ~100% interest, a mortgage REIT (EARN), and **TVA**, which has no public common equity at all (already documented at `NOTES-DAYTRADING.md:4856`). | **MED** | Exclude by SIC 6726/6798 and by `rh_fundamentals` fund industries at universe build. |
| **7** | **"SPAC = FAIL" is not implemented in the gate.** Only a name regex in `plan/scan_sweep.py:16`, a different pipeline. SPACs pass on `cash_pct ≈ 0 / haram_pct = 0` because the trust and its interest are untagged in yfinance. | **MED** | Add a blank-check test (SIC 6770 / name regex) to `halal_check` as a hard FAIL. |
| **8** | **Industry label-only screen leaks two real names.** `"defense"`/`"aerospace"`/`"gaming"` are checked against the vendor label only; TPCS (Navy submarine / USMC helicopter components) and CTW (web gaming platform) pass. | **MED** | Keep the AMD label-only rule, but add a **self-referential** full-text test (e.g. "we design and manufacture … for defense") or route vendor-label-generic names to the review queue. |

### (c) Names whose verdict should change

**Remove from `halal_list.json` (armable → FAIL):**

| SYM | why |
|---|---|
| **FLGT** | true cash_pct **47.68** (cached 0.00, missing row) **and** true haram **7.50%** — fails both legs |
| **MBGL** | true loan **33.88** / combined **37.07** (cached 0.00/0.00) |
| **PVLA** | true haram **18.36%** (cached 0.00 — missing row + 4× bug) |
| **ANAB** | true haram **10.38%** |
| **TPCS** | defense contractor by trade; both external screeners lean non-compliant |
| **CTW** | web gaming/entertainment platform; equivalent to the user-ruled-FAIL SLE |
| **TVA** | not public common equity (PARRS bonds) — should never have been in the universe |
| **EARN** | mortgage REIT |
| bond/equity **CEFs & trusts**: AB BGY CEF CII CLM CRF EOI ETB ETV GRF MXE MXF PAI PCF PHYS PSLV SPE SPPP TSI, ETFs HLAL MNZL SPUS | not operating companies; ratios are artifacts of absent statements |

**Plus the 42 remaining names of the 44 whose true interest/revenue ≥ 5%** once
Bug 1 is fixed — highest first: NOMA 17.2%, BSP 14.8%, LB 13.8%, PROF 13.5%,
BXBL 13.4%, BRUN 12.8%, MTA 12.6%, MSTR 11.8%, CBRS 11.8%, PCYO 11.5%, BMNR 11.4%,
**MRVL 10.6%**, ANAB 10.4%, AMAT 9.8%, BAM 9.2%, ALM 9.2%, TAOX 9.1%, ARBK 9.0%,
PSNL 8.8%, **ASST 8.8%**, IOT 8.7%, ABSI 8.4%, AUC 8.1%, SITM 8.0%, KMTS 7.8%,
FLGT 7.5%, RUM 7.4%, SAP 7.4%, DGXX 7.4%, XHLD 7.2%, TGTX 6.9%, RCEL 6.8%,
CAMT 6.7%, TONX 6.5%, KRYS 6.4%, EP 6.2%, IBRX 6.2%, HSLV 6.1%, IQMX 6.1%,
NET 5.7%, OLED 5.6%, VELO 5.3%, NVMI 5.1%, ABNB 5.1%.

**Live-campaign impact:** of the 18 symbols actually traded, **MRVL (10.6%)** and
**ASST (8.8%)** would fail a corrected 5% test, and **GTLB (4.52%)** sits just
under it. **ANGX** (traded Paper Day 8) is already correctly FAIL today —
`HARAM INDUSTRY (entertainment, movie)` — it was armed before the industry screen
was hardened, which is the incident this whole screen was rebuilt around.
**QCOM**, the most recent ticket, is clean on every leg (true haram 0.98%,
combined 12.05–13.49%).

### (d) Systematic limitations that are **not** bugs

1. **`haram_pct` is interest-income-only** — it is structurally blind to alcohol,
   pork, gaming and tobacco *revenue*. The code says so at `day-trading.py:866-868`
   and compensates with `REVENUE_SENSITIVE_WORDS` → CANNOT-VERIFY → FAIL. Correct
   design; just means the 5% number never measures what its name suggests.
2. **Market cap is a present-day snapshot** against quarter-old statements. For a
   name that has doubled since filing, the ratios are ~halved. Unavoidable without
   a point-in-time cap; the backtest path addresses it, the live path does not.
3. **~45-day filing lag.** The latest 10-Q is up to a quarter stale, and the
   monthly universe refresh adds up to 30 more days.
4. **Present-day industry labels** are applied to historical decisions, and vendor
   labels are unreliable (`_industry_hits` documents AZ, a shopping-cart maker,
   tagged "Financial Conglomerates"). Hence the name+summary screen.
5. **Half-year foreign filers** (6-K/20-F) appear in yfinance's *quarterly* table
   with 6-month periods and are annualized ×4 — a 2× over-statement of revenue,
   which biases `haram_pct` lenient. Related to Bug 1 but distinct; 11 of 68
   sampled names have no 10-Q at all.
6. **External screener coverage is thin and stale** — one 2026-08-22 snapshot,
   only 630 usable verdicts, 84 of which overlap the armable list.
7. **Yahoo's `Total Debt` excludes operating leases.** Defensible (they are not
   interest-bearing borrowings) but it is a choice, not a neutral fact.

---

## 6. Recommended order of work

1. **Bug 1** (4× haram) — one-line fix, largest correctness gain, ~44 armable names change.
2. **Bug 2** (`get_val` → `None`) — closes the remaining false-PASS path (FLGT, MBGL).
3. **Bug 6** (fund/ETF/non-common-equity exclusion at universe build) — removes ~25 names
   that were never screenable.
4. **Bug 7** (SPAC hard FAIL in the gate).
5. **Bugs 3, 4** (`info`/`annual` tier haram handling).
6. **Bug 5** (EDGAR tier precedence) — then re-extract and re-baseline any `PT_FILED=1` result.
7. **Bug 8** (TPCS/CTW) — route vendor-label-generic names to `halal_review_queue`.

Fixing 1 + 2 + 6 + 7 and rebuilding the universe will drop the armable list
materially below 1,260. That is the correct direction: **every defect found in
this audit errs toward passing a name that should have been refused, and none
toward refusing a permissible one.**

---

*Audit tool: `plan/halal_audit.py`. Re-run with
`python plan/halal_audit.py --sample --zero-ratio --out <file>`.
Read-only on all engine files; no verdicts were changed by this audit.*

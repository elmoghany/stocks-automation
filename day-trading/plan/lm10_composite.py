"""LEGACY-10 part 3: one fixed, un-fitted regime label (natural thresholds,
no quantiles): TREND = SPY and QQQ both closed above their 20-day mean
yesterday; CALM = SPY 5d realized vol < its 20d realized vol yesterday.
Reports pool (30 random controls) and R4 per-ticket at $10k, 15 bps/side."""
import json, os, sys, pickle
import numpy as np

HERE = os.path.dirname(__file__)
P = pickle.load(open(sys.argv[1].replace("feat", "panel"), "rb"))
D = json.load(open(os.path.join(HERE, "pa_out", "cp_r4_legs.json")))
feat, dates = P["feat"], P["dates"]
N = len(dates); di = {d: i for i, d in enumerate(dates)}
BPS = float(os.environ.get("BPS", 15)); C = 2 * BPS


def legs_by_day(L):
    out = [[] for _ in range(N)]
    for t in L:
        out[di[t["date"]]].append(1e4 * (t["exit"] / t["entry"] - 1))
    return out

R4 = legs_by_day(D["legs"]["R4"])
RN = [legs_by_day(D["legs"][f"RND{k}"]) for k in range(30)]
trend = (feat["SPY_ma20"] > 0) & (feat["QQQ_ma20"] > 0)
calm = feat["SPY_volratio"] < 1
yr = np.array([d < "2025-08-01" for d in dates])
labels = {"TREND&CALM": trend & calm, "TREND&!CALM": trend & ~calm,
          "!TREND&CALM": ~trend & calm, "!TREND&!CALM": ~trend & ~calm,
          "TREND(any)": trend, "!TREND(any)": ~trend}


def summ(mask, src, clip=None):
    v = [x for i in np.where(mask)[0] for x in src[i]]
    v = np.array(v, float)
    if clip:
        v = np.clip(v, -clip, clip)
    return (v.mean() - C if len(v) else np.nan), len(v)

print(f"cost {BPS} bps/side; $10k/leg; pool = 30 random-pick seeds pooled")
for lab, m in labels.items():
    out = []
    for nm, ym in (("Y1", yr), ("Y2", ~yr), ("ALL", np.ones(N, bool))):
        mm = m & ym
        r_raw, nr = summ(mm, R4); r_w, _ = summ(mm, R4, 1500)
        pr = [x for s in RN for i in np.where(mm)[0] for x in s[i]]
        pr = np.array(pr, float)
        p_raw = pr.mean() - C if len(pr) else np.nan
        p_w = np.clip(pr, -1500, 1500).mean() - C if len(pr) else np.nan
        out.append(f"{nm}: days {mm.sum():3d} R4 {r_raw:+6.0f}/{r_w:+5.0f} (n{nr}) pool {p_raw:+5.0f}/{p_w:+5.0f}")
    print(f"{lab:13s} " + " | ".join(out))

# day-bootstrap of R4 raw $/tk difference TREND vs !TREND (all days)
rng = np.random.default_rng(3)
idx = np.arange(N)
def diff(ix):
    a = [x for i in ix if trend[i] for x in R4[i]]; b = [x for i in ix if not trend[i] for x in R4[i]]
    return np.mean(a) - np.mean(b)
bs = [diff(rng.choice(idx, N)) for _ in range(1000)]
print(f"R4 raw $/tk TREND minus !TREND: {diff(idx):+.0f}, day-bootstrap 90% CI [{np.percentile(bs,5):+.0f}, {np.percentile(bs,95):+.0f}]")
def pdiff(ix):
    a = [x for s in RN for i in ix if trend[i] for x in s[i]]; b = [x for s in RN for i in ix if not trend[i] for x in s[i]]
    return np.clip(a, -1500, 1500).mean() - np.clip(b, -1500, 1500).mean()
bs = [pdiff(rng.choice(idx, N)) for _ in range(300)]
print(f"pool winsor $/tk TREND minus !TREND: {pdiff(idx):+.0f}, day-bootstrap 90% CI [{np.percentile(bs,5):+.0f}, {np.percentile(bs,95):+.0f}]")
print("share of days TREND:", f"Y1 {trend[yr].mean():.2f} Y2 {trend[~yr].mean():.2f}")
# month-level sit-out: R4 $/month with and without the !TREND skip, raw, per year
for nm, ym in (("Y1", yr), ("Y2", ~yr)):
    base = sum(x - C for i in np.where(ym)[0] for x in R4[i]) / (ym.sum() / 21)
    filt = sum(x - C for i in np.where(ym & trend)[0] for x in R4[i]) / (ym.sum() / 21)
    half = filt + 0.5 * sum(x - C for i in np.where(ym & ~trend)[0] for x in R4[i]) / (ym.sum() / 21)
    print(f"{nm} R4 $/month: always {base:+.0f}  skip !TREND {filt:+.0f}  half-size !TREND {half:+.0f}")

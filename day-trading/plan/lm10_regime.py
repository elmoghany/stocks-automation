"""LEGACY-10: does a causal pre-day regime switch keep R4's year-1 edge and
skip its year-2 bleed?  Inputs: plan/pa_out/cp_r4_legs.json (honest R4 +
30 random-pick controls, same frame) and the lm10_feat.py pickle (argv[1]).
Flat $10k ticket per leg (1e4 * leg return); cost bps/side applied per leg."""
import json, os, sys, pickle, collections
import numpy as np

HERE = os.path.dirname(__file__)
D = json.load(open(os.path.join(HERE, "pa_out", "cp_r4_legs.json")))
FE = pickle.load(open(sys.argv[1], "rb"))
BPS = float(os.environ.get("BPS", 15))
WIN = 1500.0                       # winsorize a $10k leg at +-$1,500 (15%)
Y1_END = "2025-08-01"
dates = D["dates"]
di = {d: i for i, d in enumerate(dates)}
N = len(dates)


def daily(legs, clip=None):
    g = np.zeros(N); n = np.zeros(N)
    for t in legs:
        r = 1e4 * (t["exit"] / t["entry"] - 1)
        if clip:
            r = max(-clip, min(clip, r))
        i = di[t["date"]]
        g[i] += r - 2 * BPS; n[i] += 1
    return g, n


R4 = D["legs"]["R4"]
g_raw, n_r4 = daily(R4)
g_win, _ = daily(R4, WIN)
rnd = [daily(D["legs"][f"RND{k}"]) for k in range(30)]
rnd_g = np.mean([x[0] for x in rnd], 0); rnd_n = np.mean([x[1] for x in rnd], 0)
rnd_pt = np.where(rnd_n > 0, rnd_g / np.maximum(rnd_n, 1e-9), np.nan)   # per-ticket pool quality
y1 = np.array([d < Y1_END for d in dates]); y2 = ~y1

print(f"cost {BPS} bps/side, flat $10k/leg, winsor +-{WIN}")
print("== WHAT DIFFERED Y1 vs Y2 ==")
for nm, m in (("Y1", y1), ("Y2", y2)):
    legs = [t for t in R4 if (t["date"] < Y1_END) == (nm == "Y1")]
    r = np.array([1e4 * (t["exit"] / t["entry"] - 1) for t in legs])
    s = np.sort(r)[::-1]
    print(f"{nm}: days {m.sum()} legs {len(r)} tk/day {len(r)/m.sum():.2f} gross/tk {r.mean():+.1f} "
          f"net/tk {r.mean()-2*BPS:+.1f} median {np.median(r):+.1f} win% {100*(r>0).mean():.1f} "
          f"top5 sum {s[:5].sum():+.0f} ex-top5 gross/tk {s[5:].mean():+.1f} winsor net/tk {(np.clip(r,-WIN,WIN)-2*BPS).mean():+.1f} "
          f"| RND net/tk {np.nansum(rnd_g[m])/rnd_n[m].sum():+.1f} "
          f"| R4-RND edge/tk {(r.mean()-2*BPS)-np.nansum(rnd_g[m])/rnd_n[m].sum():+.1f}")
    ex = collections.Counter(t["reason"].split()[0] for t in legs)
    exs = collections.defaultdict(float)
    for t in legs:
        exs[t["reason"].split()[0]] += 1e4 * (t["exit"] / t["entry"] - 1) - 2 * BPS
    print("   exits:", {k: (ex[k], round(exs[k] / ex[k], 1)) for k in ex})

# --- strategy-momentum features (known before D: sessions strictly before D)
def trail(x, k, cnt=None):
    o = np.full(N, np.nan)
    for i in range(k, N):
        o[i] = x[i - k:i].sum() / (cnt[i - k:i].sum() if cnt is not None else 1)
    return o

feat = {}
keys = sorted(set().union(*[FE[d].keys() for d in dates if d in FE]))
for k in keys:
    feat[k] = np.array([FE.get(d, {}).get(k, np.nan) for d in dates], float)
feat["r4_tr5"] = trail(g_win, 5); feat["r4_tr10"] = trail(g_win, 10); feat["r4_tr20"] = trail(g_win, 20)
feat["rnd_tr10"] = trail(np.nan_to_num(rnd_g), 10, rnd_n); feat["rnd_tr20"] = trail(np.nan_to_num(rnd_g), 20, rnd_n)

print("\n== Y1 vs Y2 feature means (median) ==")
for k in ("SPY_r20", "SPY_ma50", "SPY_vol20", "IWM_r20", "IWM_ma50", "IWM_vol20", "IWMvSPY_r20",
          "XBI_r20", "n_g10h_1", "n_g10h_5", "n_g10o_5", "big_run_5", "g_ret_5", "sc_up_5", "sc_ab20_5"):
    f = feat[k]
    print(f"  {k:12s} Y1 {np.nanmedian(f[y1]):+.4f}  Y2 {np.nanmedian(f[y2]):+.4f}")

# --- tercile tables, cut points fit on Y1 only
def stat(m, g):
    t = n_r4[m].sum()
    return (g[m].sum() / t if t else np.nan), int(t)

print("\n== terciles (cuts from Y1). R4 net/tk raw | winsor ; RND net/tk ; per year ==")
rows = []
for k, f in feat.items():
    ok = np.isfinite(f)
    if ok[y1].sum() < 100:
        continue
    q1, q2 = np.nanquantile(f[y1 & ok], [1 / 3, 2 / 3])
    bins = [ok & (f <= q1), ok & (f > q1) & (f <= q2), ok & (f > q2)]
    line = []
    for nm, ym in (("Y1", y1), ("Y2", y2)):
        for b in bins:
            m = b & ym
            line.append((stat(m, g_raw)[0], stat(m, g_win)[0], np.nansum(rnd_g[m]) / max(rnd_n[m].sum(), 1), stat(m, g_win)[1]))
    rows.append((k, line))
# rank features by Y1 winsor spread top-bottom and print compact
def fmt(x): return f"{x[1]:+5.0f}/{x[2]:+4.0f}({x[3]})"
for k, line in rows:
    print(f"{k:13s} Y1 lo/mid/hi " + " ".join(fmt(x) for x in line[:3]) + " | Y2 " + " ".join(fmt(x) for x in line[3:]))

# --- walk-forward rule selection
RULES = []
for k, f in feat.items():
    ok = np.isfinite(f)
    if ok[y1].sum() < 100:
        continue
    for qq in (1 / 3, 1 / 2, 2 / 3):
        for side in ("ge", "le"):
            RULES.append((k, qq, side))

def evaluate(fit, test, g_fit, g_test, F=feat, verbose=False, size_dn=0.0):
    base_fit = g_fit[fit].sum()
    res = []
    for k, qq, side in RULES:
        f = F[k]
        cut = np.nanquantile(f[fit & np.isfinite(f)], qq)
        on = (f >= cut) if side == "ge" else (f <= cut)
        on = on | ~np.isfinite(f)          # missing feature => trade
        w = np.where(on, 1.0, size_dn)
        res.append(((g_fit * w)[fit].sum() - base_fit, k, qq, side, cut, w))
    res.sort(key=lambda x: -x[0])
    return res

def months(m): return m.sum() / 21.0

print(f"\n== WALK-FORWARD: fit rule on Y1 (winsor P&L), apply frozen cut to Y2 ({len(RULES)} candidate rules) ==")
for fitm, testm, lab in ((y1, y2, "fit Y1 -> test Y2"), (y2, y1, "fit Y2 -> test Y1")):
    for sd in (0.0, 0.5):
        res = evaluate(fitm, testm, g_win, g_win, size_dn=sd)
        base_t = g_raw[testm].sum(); base_tw = g_win[testm].sum()
        print(f"-- {lab}, out-of-regime size {sd}: base test raw ${base_t/months(testm):+.0f}/mo winsor ${base_tw/months(testm):+.0f}/mo, tickets {n_r4[testm].sum():.0f}")
        for d_fit, k, qq, side, cut, w in res[:8]:
            t_raw = (g_raw * w)[testm].sum(); t_w = (g_win * w)[testm].sum()
            print(f"   {k:13s} {side} q{qq:.2f} cut={cut:+.4g}  fit +${d_fit/months(fitm):+.0f}/mo  "
                  f"test raw ${t_raw/months(testm):+.0f}/mo (d {(t_raw-base_t)/months(testm):+.0f}) "
                  f"winsor d {(t_w-base_tw)/months(testm):+.0f}  traded tk {(n_r4*w)[testm].sum():.0f}")
        # distribution of test deltas over the top-20 fit rules
        dd = [((g_win * r[5])[testm].sum() - base_tw) / months(testm) for r in res[:20]]
        print(f"   top-20 fit rules: test winsor delta mean {np.mean(dd):+.0f}/mo, positive {sum(x>0 for x in dd)}/20; "
              f"all {len(res)} rules: mean {np.mean([((g_win*r[5])[testm].sum()-base_tw)/months(testm) for r in res]):+.0f}/mo")

# --- null: how large a fit-period gain does best-of-K produce on a SHUFFLED feature panel?
rng = np.random.default_rng(10)
best = []
for it in range(200):
    p = rng.permutation(N)
    Fp = {k: v[p] for k, v in feat.items()}
    best.append(evaluate(y1, y2, g_win, g_win, F=Fp)[0][0] / months(y1))
real = evaluate(y1, y2, g_win, g_win)[0][0] / months(y1)
print(f"\n== NULL (200 day-shuffles of all features): best Y1 in-sample gain real ${real:+.0f}/mo vs null median "
      f"${np.median(best):+.0f}, 95th ${np.percentile(best,95):+.0f}, pct {100*(np.array(best)<real).mean():.0f}")

# --- pool-quality control: does the same rule help the RANDOM picks (i.e. is it a market regime, not R4-specific)?
print("\n== monthly table: R4 net raw, winsor, RND net/tk, tickets ==")
mon = sorted(set(d[:7] for d in dates))
for mo in mon:
    m = np.array([d[:7] == mo for d in dates])
    print(f"  {mo} R4 raw {g_raw[m].sum():+7.0f} win {g_win[m].sum():+7.0f} tk {n_r4[m].sum():3.0f} "
          f"RND/tk {np.nansum(rnd_g[m])/rnd_n[m].sum():+6.1f}  SPYvol20 {np.nanmean(feat['SPY_vol20'][m]):.2f} "
          f"IWM_r20 {np.nanmean(feat['IWM_r20'][m]):+.3f} g10h {np.nanmean(feat['n_g10h_1'][m]):.0f} g_ret5 {np.nanmean(feat['g_ret_5'][m]):+.3f}")
pickle.dump(dict(feat=feat, g_raw=g_raw, g_win=g_win, n=n_r4, rnd_g=rnd_g, rnd_n=rnd_n, dates=dates),
            open(sys.argv[1].replace("feat", "panel"), "wb"))

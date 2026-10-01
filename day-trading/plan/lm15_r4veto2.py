# LM15 follow-up: post-open-appropriate veto proxies on R4 vs random legs; robustness ex-top-5. Read-only.
import sys, json, numpy as np
sys.path.insert(0, 'plan')
import cp_lib as L, cp_cost as C
D = json.load(open('plan/pa_out/cp_r4_legs.json')); legs = D['legs']
bydate = {}
for tag, LL in legs.items():
    for j, x in enumerate(LL): bydate.setdefault(x['date'], []).append((tag, j))
F = {}
for date in sorted(bydate):
    day = L.load_day(date)
    if day is None: continue
    idx = {s: i for i, s in enumerate(day.syms)}
    for tag, j in bydate[date]:
        x = legs[tag][j]; i = idx.get(x['sym']); m = x['entry_min']
        if i is None or m < 31: continue
        pr = day.printed[i, :m]
        ii = np.where(pr)[0][-10:]                      # last 10 printed bars strictly before entry minute
        hl = np.median((day.h[i, ii] - day.l[i, ii]) / ((day.h[i, ii] + day.l[i, ii]) / 2)) * 1e4 if len(ii) >= 5 else np.nan
        a = m - 30; prr = day.printed[i, a:m]
        o, h, l, c = [np.where(prr, arr[i, a:m], np.nan) for arr in (day.o, day.h, day.l, day.c)]
        cs, ar = C._cs_ar(o, h, l, c); vals = [v for v in (cs, ar) if v is not None and np.isfinite(v)]
        sp = max(vals) if vals else np.nan
        dv10 = float(np.nansum(day.c[i, m-10:m] * day.v[i, m-10:m]))
        F[(tag, j)] = (hl, sp, dv10)
def run(tags, label):
    R = []
    for tag in tags:
        for j, x in enumerate(legs[tag]):
            f = F.get((tag, j))
            if f is None: continue
            R.append((x['gross'] / (x['entry'] * x['shares']) * 1e4, f[0], f[1], f[2]))
    A = np.array(R); print('\n==', label, len(A), 'gross/10k %+.2f' % A[:, 0].mean())
    for k, nm in ((1, 'HL10 bar-range bps'), (2, 'CS/AR spread bps'), (3, 'trail-10m $vol')):
        v = A[:, k]; ok = np.isfinite(v); q = np.nanpercentile(v[ok], [20, 40, 60, 80])
        edges = [-np.inf] + list(q) + [np.inf]
        out = []
        for b in range(5):
            s = ok & (v > edges[b]) & (v <= edges[b + 1])
            g = np.sort(A[s, 0]); ex5 = g[:-5].mean() if len(g) > 10 else np.nan
            out.append('q%d<=%.3g n%d %+.0f (ex-top5 %+.0f)' % (b + 1, edges[b + 1], s.sum(), A[s, 0].mean(), ex5))
        print('  %-20s' % nm, ' | '.join(out))
    return A
A = run(['R4'], 'R4'); B = run(['RND%d' % k for k in range(30)], 'RANDOM pooled')
# candidate live rule for the R4 book: trailing-10-min $ volume floor (ticket <= 2% of it) -- causal, readable live
for lab, X in (('R4', A), ('RND', B)):
    for floor in (250e3, 500e3, 1e6):
        s = X[:, 3] >= floor
        print('%s $vol10>=%.0fk keep n=%d (%.0f%%) gross %+.1f | refused n=%d gross %+.1f' % (lab, floor / 1e3, s.sum(), 100 * s.mean(), X[s, 0].mean(), (~s).sum(), X[~s, 0].mean()))

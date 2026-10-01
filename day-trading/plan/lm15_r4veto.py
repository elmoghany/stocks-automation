# LM15: would the LIVE book veto (spread / thin tape) have helped R4?  Causal bar proxies at the entry minute,
# computed on the cp_panel for every saved R4 leg and every leg of its 30 random-seed controls. Read-only.
import sys, json, numpy as np, statistics as st
sys.path.insert(0, 'plan')
import cp_lib as L, cp_cost as C
D = json.load(open('plan/pa_out/cp_r4_legs.json'))
legs = {k: v for k, v in D['legs'].items()}
bydate = {}
for tag, LL in legs.items():
    for j, x in enumerate(LL): bydate.setdefault(x['date'], []).append((tag, j))
tc = C.TapeCost()
feat = {}
for n, date in enumerate(sorted(bydate)):
    day = L.load_day(date)
    if day is None: continue
    idx = {s: i for i, s in enumerate(day.syms)}
    for tag, j in bydate[date]:
        x = legs[tag][j]; i = idx.get(x['sym']); m = x['entry_min']
        if i is None or m < 31: continue
        a = m - 30
        pr = day.printed[i, a:m]
        o, h, l, c = [np.where(pr, arr[i, a:m], np.nan) for arr in (day.o, day.h, day.l, day.c)]
        cs, ar = C._cs_ar(o, h, l, c)
        vals = [v for v in (cs, ar) if v is not None and np.isfinite(v)]
        sp = max(vals) if vals else np.nan
        nts = 1.0 - pr.mean()
        cc = c[np.isfinite(c)]; vv = day.v[i, a:m][pr]
        if len(cc) >= 3:
            r = np.abs(np.diff(np.log(cc))); dv = (cc[1:] * vv[1:])
            ami = float(np.mean(r / np.maximum(dv, 1.0))) * 1e6
        else: ami = np.nan
        ce = tc.bps(day, i, m, 10000.0); cx = tc.bps(day, i, min(x['exit_min'], L.NMIN - 1), 10000.0)
        feat[(tag, j)] = (sp, nts, ami, ce + cx)
    if n % 50 == 0: print('date', n, date, flush=True)
def table(tag_list, label):
    rows = []
    for tag in tag_list:
        for j, x in enumerate(legs[tag]):
            f = feat.get((tag, j))
            if f is None: continue
            notional = x['entry'] * x['shares']
            g10 = x['gross'] / notional * 10000.0      # $ gross per $10k ticket
            rows.append((g10, f[0], f[1], f[2], f[3]))
    A = np.array(rows, dtype=float)
    print('\n==', label, 'legs', len(A), 'gross $/10k-tkt %+.2f | net@15bps/side %+.2f | net@measured %+.2f (mean meas RT %.1f bps)' % (
        A[:, 0].mean(), A[:, 0].mean() - 30, (A[:, 0] - A[:, 4]).mean(), A[:, 4].mean()))
    for k, nm in ((1, 'spread proxy bps'), (2, 'no-trade share 30'), (3, 'amihud30 x1e6')):
        v = A[:, k]; ok = np.isfinite(v)
        q = np.nanpercentile(v[ok], [33.3, 66.7])
        for lo, hi, b in ((-np.inf, q[0], 'low'), (q[0], q[1], 'mid'), (q[1], np.inf, 'high')):
            s = ok & (v > lo) & (v <= hi)
            print('   %-18s %-4s (%.3g..%.3g] n=%4d gross %+7.2f  net@meas %+7.2f  measRT %.0f' % (nm, b, lo, hi, s.sum(), A[s, 0].mean(), (A[s, 0] - A[s, 4]).mean(), A[s, 4].mean()))
        s = ~ok
        if s.sum(): print('   %-18s NaN  n=%4d gross %+7.2f' % (nm, s.sum(), A[s, 0].mean()))
    # live-style veto: proxy spread > 50 bps (0.5% cap) OR no-trade share > 0.18 (premarket-calibrated cut)
    veto = (np.nan_to_num(A[:, 1], nan=999) > 50) | (A[:, 2] > 0.18)
    for nm, s in (('KEPT', ~veto), ('VETOED', veto)):
        print('   live-style veto %-6s n=%4d (%.0f%%) gross %+7.2f net@15 %+7.2f net@meas %+7.2f' % (nm, s.sum(), 100 * s.mean(), A[s, 0].mean(), A[s, 0].mean() - 30, (A[s, 0] - A[s, 4]).mean()))
    return A, veto
A, v = table(['R4'], 'R4')
B, vb = table(['RND%d' % k for k in range(30)], 'RANDOM 30 seeds pooled')
months = 22.0
print('\nR4 $/month @10k tickets: all gross %+.0f net@meas %+.0f | kept-only gross %+.0f net@meas %+.0f' % (
    A[:, 0].sum() / months, (A[:, 0] - A[:, 4]).sum() / months, A[~v, 0].sum() / months, (A[~v, 0] - A[~v, 4]).sum() / months))
# year split
yrs = []
for j, x in enumerate(legs['R4']):
    if ('R4', j) in feat: yrs.append(x['date'] < '2025-08-01')
yrs = np.array(yrs)
for nm, s in (('Y1', yrs), ('Y2', ~yrs)):
    print('  %s all n=%d gross %+.2f | kept n=%d gross %+.2f net@meas %+.2f | vetoed n=%d gross %+.2f' % (nm, s.sum(), A[s, 0].mean(), (s & ~v).sum(), A[s & ~v, 0].mean(), (A[s & ~v, 0] - A[s & ~v, 4]).mean(), (s & v).sum(), A[s & v, 0].mean()))
json.dump({'R4': A.tolist(), 'R4_veto': v.tolist()}, open('plan/lm15_out_r4veto.json', 'w'))

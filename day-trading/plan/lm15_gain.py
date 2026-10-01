# LM15: do the biggest movers (the live 'best mover of the day') pay in the gapper pool? gain-at-entry buckets. Read-only.
import sys, json, numpy as np
sys.path.insert(0, 'plan')
import cp_lib as L
D = json.load(open('plan/pa_out/cp_r4_legs.json')); legs = D['legs']
bydate = {}
for tag, LL in legs.items():
    for j, x in enumerate(LL): bydate.setdefault(x['date'], []).append((tag, j))
G = {}
for date in sorted(bydate):
    day = L.load_day(date)
    if day is None: continue
    idx = {s: i for i, s in enumerate(day.syms)}; last = day.last
    for tag, j in bydate[date]:
        x = legs[tag][j]; i = idx.get(x['sym']); m = x['entry_min']
        if i is None or not (day.pc[i] > 0): continue
        G[(tag, j)] = 100 * (last[i, m - 1] / day.pc[i] - 1)
E = [10, 20, 35, 50, 100, 1e9]
for lab, tags in (('R4', ['R4']), ('RANDOM pooled', ['RND%d' % k for k in range(30)])):
    R = np.array([(legs[t][j]['gross'] / (legs[t][j]['entry'] * legs[t][j]['shares']) * 1e4, G[(t, j)]) for t in tags for j in range(len(legs[t])) if (t, j) in G])
    out = []
    for a, b in zip([-1e9] + E[:-1], E):
        s = (R[:, 1] > a) & (R[:, 1] <= b)
        if s.sum() > 5:
            g = np.sort(R[s, 0]); out.append('(%g,%g] n%d %+.0f ex5 %+.0f' % (a, b, s.sum(), g.mean(), g[:-5].mean()))
    print(lab, len(R), ' | '.join(out))

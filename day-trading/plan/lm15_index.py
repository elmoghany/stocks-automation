# LM15: index cached minute bars that cover the live paper dates (read-only)
import os, json, collections
DATES = set("2026-08-04 2026-08-05 2026-08-06 2026-08-07 2026-08-10 2026-08-11 2026-08-12 2026-08-13 2026-08-14 2026-08-17 2026-08-18 2026-08-19 2026-08-20 2026-08-21 2026-08-24 2026-08-25 2026-08-26 2026-08-27 2026-08-28 2026-08-31 2026-09-01 2026-09-02 2026-09-03 2026-09-04 2026-09-08 2026-09-09 2026-09-10 2026-09-11 2026-09-14 2026-09-15 2026-09-16 2026-09-17 2026-09-18".split())
idx = collections.defaultdict(dict)
for d in ['data/massive/m1', 'data/massive/m1w', 'data/massive/m1c', 'data/massive/m1_pre', 'plan/pa_out/m1']:
    n = 0
    for e in os.scandir(d):
        nm = e.name
        base = nm.rsplit('.', 1)[0]
        if '_' not in base: continue
        s, dt = base.rsplit('_', 1)
        if dt in DATES:
            idx[dt][s] = d + '/' + nm; n += 1
    print(d, n)
json.dump(idx, open('plan/lm15_out_index.json', 'w'))
for dt in sorted(idx): print(dt, len(idx[dt]))

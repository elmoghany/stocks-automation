# LM15: same skeleton sim on the 21 live tickets (control for the veto counterfactual) + stop-width sensitivity
import json, statistics as st, sys
sys.argv = ['x']; exec(open('plan/lm15_cf.py').read().split('TICKET = 10000')[0])  # reuse bars()/sim()
T = [('2026-08-10','LFST','09:47',12.071,-65.78,'C?'),('2026-08-11','FRMI','08:51',7.27,-266.54,'B'),('2026-08-12','BE','09:26',235.37,104.58,'B'),
('2026-08-13','ANGX','11:17',4.265,-29.83,'B'),('2026-08-14','RDDT','09:32',178.91,-136.12,'B'),('2026-08-17','HIVE','07:46',2.98,654.79,'B'),
('2026-08-19','MRVL','08:59',245.12,-696.01,'B'),('2026-08-20','RARE','07:14',28.6,-1199.31,'C'),('2026-08-20','MRVI','11:13',8.15,63.09,'C'),
('2026-08-21','ASST','08:57',17.55,150.19,'C'),('2026-08-25','CRML','10:03',7.62,402.3,'C'),('2026-08-26','SMMT','09:53',14.89,-592.48,'C'),
('2026-08-27','OKTA','09:12',163.85,876.33,'B'),('2026-08-31','NEOV','09:45',4.2126,-15.85,'C'),('2026-09-01','MMED','11:46',22.6199,73.0,'B'),
('2026-09-02','GTLB','08:13',55.8,-1136.05,'B'),('2026-09-02','DELL','09:33',474.4,-1176.51,'B'),('2026-09-02','GTLB','10:19',51.32,-555.66,'C'),
('2026-09-08','QCOM','09:11',184.89,-912.37,'C'),('2026-09-16','AXTI','10:20',63.59,15.58,'C'),('2026-09-17','VICR','09:41',211.98,394.25,'A')]
print('booked total $%.0f over %d tickets, mean $%.0f' % (sum(t[4] for t in T), len(T), st.mean(t[4] for t in T)))
for grp, f in (('premarket entry', lambda t: t[2] < '09:30'), ('RTH entry', lambda t: t[2] >= '09:30'), ('B stop-buy/A ORB', lambda t: t[5] in 'AB'), ('C pattern', lambda t: t[5].startswith('C'))):
    x = [t[4] for t in T if f(t)]; print('  %-16s n=%2d sum $%+6.0f mean $%+5.0f' % (grp, len(x), sum(x), st.mean(x)))
res = {}
for stp in (0.08, 0.12, 0.20, 0.99):
    r = []
    for t in T:
        B = bars(t[1], t[0])
        if not B: continue
        x = sim(B, t[2], t[3], stop=stp)
        if x: r.append(x[0])
    res[stp] = r
    print('sim stop %.2f n=%d mean %+.2f%% med %+.2f%% win %.0f%%' % (stp, len(r), 100 * st.mean(r), 100 * st.median(r), 100 * sum(v > 0 for v in r) / len(r)))
cf = [r for r in json.load(open('plan/lm15_out_cf.json')) if r.get('bars') and r.get('ret') is not None]
for stp in (0.08, 0.12, 0.20, 0.99):
    r = []
    for c in cf:
        B = bars(c['sym'], c['date']); x = sim(B, c['t'], c['ref'] * (1 + c['spread'] / 200), stop=stp)
        if x: r.append(x[0])
    print('VETOED sim stop %.2f n=%d mean %+.2f%% med %+.2f%% win %.0f%%' % (stp, len(r), 100 * st.mean(r), 100 * st.median(r), 100 * sum(v > 0 for v in r) / len(r)))
print('vetoed f30 mean %+.2f%% f60 mean %+.2f%% (from veto-minute last, no cost)' % (100 * st.mean(c['f30'] for c in cf), 100 * st.mean(c['f60'] for c in cf)))

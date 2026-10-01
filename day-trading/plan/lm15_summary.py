# LM15: summary numbers for the write-up (read-only)
import json, statistics as st
cf = [r for r in json.load(open('plan/lm15_out_cf.json')) if r.get('bars') and r.get('ret') is not None]
later = {('2026-08-17','HIVE'):4.37,('2026-08-26','SMMT'):-3.95,('2026-08-27','OKTA'):5.88,('2026-08-31','NEOV'):-0.33,('2026-09-02','GTLB'):-7.6,
         ('2026-08-14','RDDT'):-0.92,('2026-08-21','ASST'):1.0,('2026-08-11','FRMI'):-1.78,('2026-08-20','RARE'):-8.0,('2026-08-13','ANGX'):-0.23}
g = [r['ret'] + r['spread'] / 200 + 0.0005 for r in cf]
print('vetoed n=%d net mean %+.2f%% | gross (from last trade, no toll) mean %+.2f%% med %+.2f%% | mean half-spread %.2f%% (median %.2f%%)' % (
    len(cf), 100 * st.mean(r['ret'] for r in cf), 100 * st.mean(g), 100 * st.median(g), st.mean(r['spread'] / 2 for r in cf), st.median(r['spread'] / 2 for r in cf)))
lt = [r for r in cf if (r['date'], r['sym']) in later]; nt = [r for r in cf if (r['date'], r['sym']) not in later]
print('later-traded n=%d veto-time net %+.2f%% vs actual later entry %+.2f%%' % (len(lt), 100 * st.mean(r['ret'] for r in lt), st.mean(later[(r['date'], r['sym'])] for r in lt)))
print('never-traded n=%d net mean %+.2f%% med %+.2f%% win %.0f%% stop-hit %d' % (len(nt), 100 * st.mean(r['ret'] for r in nt), 100 * st.median(r['ret'] for r in nt), 100 * sum(r['ret'] > 0 for r in nt) / len(nt), sum(r['exit'] == 'stop' for r in nt)))
ng = [r['ret'] + r['spread'] / 200 + 0.0005 for r in nt]; print('never-traded gross mean %+.2f%%' % (100 * st.mean(ng)))
for k in ('SPREAD', 'DEPTH', 'CHASE'):
    x = [r['ret'] for r in cf if r['kind'] == k]
    if x: print(k, len(x), '%+.2f%%' % (100 * st.mean(x)))
mv = [m for m in json.load(open('plan/lm15_out_movers.json')) if m['ret_first_to_close'] is not None]
print('top movers with bars n=%d first-seen->14:59 mean %+.1f%% med %+.1f%%' % (len(mv), 100 * st.mean(m['ret_first_to_close'] for m in mv), 100 * st.median(m['ret_first_to_close'] for m in mv)))

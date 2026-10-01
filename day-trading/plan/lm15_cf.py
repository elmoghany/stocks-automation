# LM15: counterfactual for vetoed names -- what would ignoring the veto have done? (read-only, cached bars only)
import json, csv, datetime as dt, collections, statistics as st
idx = json.load(open('plan/lm15_out_index.json'))
ev = json.load(open('plan/lm15_out_vetoes.json'))
def bars(sym, date):
    p = idx.get(date, {}).get(sym)
    if not p: return None
    out = []
    if p.endswith('.json'):
        for b in json.load(open(p)):
            t = dt.datetime.utcfromtimestamp(b['t'] / 1000) - dt.timedelta(hours=4)
            out.append((t.strftime('%H:%M'), b['o'], b['h'], b['l'], b['c'], b['v']))
    else:
        for r in csv.DictReader(open(p)):
            t = dt.datetime.fromisoformat(r['begins_at'].replace('+00:00', '')) - dt.timedelta(hours=4)
            out.append((t.strftime('%H:%M'), float(r['Open']), float(r['High']), float(r['Low']), float(r['Close']), float(r['Volume'])))
    return sorted(out)
def sim(B, t_entry, entry_px, stop=0.08, flat='14:59', exit_cost_bps=5):
    """C37 skeleton: -8% hard stop intrabar (gap-through fills at open), flatten at 14:59 close. Entry at entry_px."""
    s = entry_px * (1 - stop); mfe = 0; mae = 0
    for (t, o, h, l, c, v) in B:
        if t <= t_entry: continue
        if t > flat: break
        mfe = max(mfe, h / entry_px - 1); mae = min(mae, l / entry_px - 1)
        if l <= s:
            px = min(o, s); return px * (1 - exit_cost_bps / 1e4) / entry_px - 1, t, 'stop', mfe, mae
        last = (t, c)
    try: return last[1] * (1 - exit_cost_bps / 1e4) / entry_px - 1, last[0], 'flat', mfe, mae
    except NameError: return None
def first_bar_at_or_after(B, t):
    for b in B:
        if b[0] >= t: return b
TICKET = 10000
# first REAL veto per symbol-day (spread > 0.5% or DEPTH/CHASE)
first = {}
for e in ev:
    real = (e['kind'] in ('DEPTH', 'CHASE')) or (e['spread'] is not None and float(e['spread']) > 0.5) or (e['kind'] == 'SPREAD' and e['spread'] is None)
    if real: first.setdefault((e['date'], e['sym']), e)
rows = []
for (d, s), e in sorted(first.items()):
    B = bars(s, d)
    if not B: rows.append(dict(date=d, sym=s, t=e['t'], kind=e['kind'], spread=e['spread'], bars=False)); continue
    b = first_bar_at_or_after(B, e['t'])
    if not b: continue
    sp = float(e['spread']) if e['spread'] is not None else 1.0
    # ignore-veto entry: veto minute's last trade + half the logged spread (= buy at the ask)
    ref = [x for x in B if x[0] <= e['t']]
    ref_px = ref[-1][4] if ref else b[1]
    ent = ref_px * (1 + sp / 200)
    r = sim(B, e['t'], ent)
    # alt: wait for the 09:31 open bar (book usually tightens at the open) if veto was premarket
    alt = None
    if e['t'] < '09:30':
        b2 = first_bar_at_or_after(B, '09:31')
        if b2:
            alt = sim(B, b2[0], b2[1] * 1.0012)  # 12 bps entry toll post-open
    # forward 30/60-min move from the veto-minute price (mid proxy)
    def fwd(m):
        tt = (dt.datetime.strptime(e['t'], '%H:%M') + dt.timedelta(minutes=m)).strftime('%H:%M')
        x = [y for y in B if y[0] <= tt]
        return x[-1][4] / ref_px - 1 if x else None
    rows.append(dict(date=d, sym=s, t=e['t'], kind=e['kind'], spread=sp, bars=True, ref=ref_px,
                     ret=r[0] if r else None, exit=r[2] if r else None, mfe=r[3] if r else None, mae=r[4] if r else None,
                     f30=fwd(30), f60=fwd(60), alt931=alt[0] if alt else None))
json.dump(rows, open('plan/lm15_out_cf.json', 'w'), indent=0)
ok = [r for r in rows if r.get('bars') and r.get('ret') is not None]
print('vetoed symbol-days', len(rows), 'with bars', len(ok))
for r in ok:
    print('%s %-5s %s %-6s sp%5.2f%% ret%+6.2f%% %-4s mfe%+6.1f mae%+6.1f f30%+6.2f f60%+6.2f alt931 %s' % (
        r['date'], r['sym'], r['t'], r['kind'], r['spread'], 100 * r['ret'], r['exit'], 100 * r['mfe'], 100 * r['mae'],
        100 * (r['f30'] or 0), 100 * (r['f60'] or 0), '%+.2f%%' % (100 * r['alt931']) if r['alt931'] is not None else '-'))
rets = [r['ret'] for r in ok]
print('ignore-veto: n=%d mean %+.2f%% median %+.2f%% win %.0f%% => $/tkt %+.0f (net of half-spread entry + 5bps exit)' % (
    len(rets), 100 * st.mean(rets), 100 * st.median(rets), 100 * sum(x > 0 for x in rets) / len(rets), TICKET * st.mean(rets)))
alts = [r['alt931'] for r in ok if r['alt931'] is not None]
if alts: print('wait-for-09:31 alt: n=%d mean %+.2f%% median %+.2f%% $/tkt %+.0f' % (len(alts), 100 * st.mean(alts), 100 * st.median(alts), TICKET * st.mean(alts)))
pm = [r['ret'] for r in ok if r['t'] < '09:30']; po = [r['ret'] for r in ok if r['t'] >= '09:30']
for nm, x in (('premarket vetoes', pm), ('post-open vetoes', po)):
    if x: print(nm, 'n', len(x), 'mean %+.2f%%' % (100 * st.mean(x)), 'med %+.2f%%' % (100 * st.median(x)))
for lo, hi in ((0.5, 1.0), (1.0, 2.0), (2.0, 100)):
    x = [r['ret'] for r in ok if lo < r['spread'] <= hi]
    if x: print('spread (%.1f,%.1f]' % (lo, hi), 'n', len(x), 'mean %+.2f%%' % (100 * st.mean(x)), 'med %+.2f%%' % (100 * st.median(x)))
print('no bars:', [(r['date'], r['sym']) for r in rows if not r.get('bars')])

# LM15: collect every logged veto decision from the live paper ledgers (read-only)
import json, glob, re
TKEYS = ('et', 'time_et', 'time')
SKEYS = ('sym', 'symbol')
out = []
def kind_of(path, d):
    s = (' '.join(path) + ' ' + json.dumps(d)[:600]).upper()
    for k in ('SPREAD', 'DEPTH', 'CHASE', 'SIZE_CAP', 'SIZE CAP'):
        if k in ' '.join(path).upper(): return k.replace(' ', '_')
    for k in ('rule', 'type', 'veto', 'binding_rule'):
        v = d.get(k)
        if isinstance(v, str):
            for kk in ('SPREAD', 'DEPTH', 'CHASE'):
                if kk in v.upper(): return kk
    for kk in ('SPREAD', 'DEPTH', 'CHASE'):
        if kk + ' VETO' in s or kk in s: return kk
    return '?'
def walk(o, path, date):
    if isinstance(o, dict):
        sym = next((o[k] for k in SKEYS if isinstance(o.get(k), str)), None)
        t = next((o[k] for k in TKEYS if isinstance(o.get(k), str)), None)
        if sym and t and any('veto' in p.lower() for p in path):
            m = re.search(r'(\d{1,2}):(\d{2})', t)
            if m:
                sp = o.get('spread_pct') or o.get('spread_pct_L2') or o.get('l2_spread_pct') or o.get('nbbo_spread_pct')
                if sp is None:
                    mm = re.search(r'=\s*([\d.]+)%', json.dumps(o)); sp = float(mm.group(1)) if mm else None
                ph = o.get('phase')
                out.append(dict(date=date, sym=sym, t='%02d:%s' % (int(m.group(1)), m.group(2)), kind=kind_of(path, o),
                                spread=sp, phase=ph, src='ledger:' + '/'.join(path[:2])))
        for k, v in o.items(): walk(v, path + [k], date)
    elif isinstance(o, list):
        for v in o: walk(v, path, date)
for f in sorted(glob.glob('data/paper_days/2026-0*.json')):
    if any(x in f for x in ['.cb.', '.equity.', '.flatten.', 'SKELETON']): continue
    d = json.load(open(f)); walk(d, [], d.get('date', f[-15:-5]))
# liquidity_truth (Days 5-13 ledgers, markdown-mined)
lt = json.load(open('data/liquidity_truth.json'))
for o in lt['observations']:
    c = (o.get('context') or '')
    if 'veto' in c.lower() and o.get('requote', 0) == 0:
        k = 'DEPTH' if 'DEPTH' in c.upper() else ('CHASE' if 'CHASE' in c.upper() else 'SPREAD')
        out.append(dict(date=o['date'], sym=o['symbol'], t=o['time_et'][:5], kind=k, spread=o.get('spread_pct'),
                        phase=o.get('phase'), src='liquidity_truth', bid=o.get('bid'), ask=o.get('ask')))
# dedupe
seen = set(); ev = []
for e in out:
    key = (e['date'], e['sym'], e['t'], e['kind'])
    if key in seen: continue
    seen.add(key); ev.append(e)
ev.sort(key=lambda e: (e['date'], e['t']))
json.dump(ev, open('plan/lm15_out_vetoes.json', 'w'), indent=0)
import collections
print(len(ev), collections.Counter(e['kind'] for e in ev))
print(collections.Counter(e['date'] for e in ev))
fs = {}
for e in ev: fs.setdefault((e['date'], e['sym']), e)
print('symbol-days', len(fs))
for k, e in sorted(fs.items()): print(k, e['t'], e['kind'], e['spread'], e['src'])

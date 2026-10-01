# LM15: best mover of each day vs what the live session could trade (read-only)
import json, glob, re, os, collections, statistics as st, sys
exec(open('plan/lm15_cf.py').read().split('TICKET = 10000')[0])
FUND = re.compile(r'ETF|ETN|2X|3X|Daily Target|Leveraged|Bull|Bear|Shares|Trust|Fund|Ultra|Proshares|Direxion|T-REX|Defiance|GraniteShares|Tradr|Warrant|Rights|Units?\b', re.I)
days = collections.defaultdict(list)
for f in glob.glob('data/paper_days/scan_dump_2026-*.json') + glob.glob('data/paper_days/scan_2026-08-2*_*.json'):
    m = re.search(r'(2026-\d\d-\d\d)_(\d{4})', f); days[m.group(1)].append((m.group(2), f))
traded = {('2026-08-27','OKTA'),('2026-09-01','MMED'),('2026-09-02','GTLB'),('2026-09-02','DELL'),('2026-09-08','QCOM'),('2026-09-16','AXTI'),('2026-09-17','VICR')}
vet = {(e['date'], e['sym']) for e in json.load(open('plan/lm15_out_vetoes.json'))}
summary = []
for d in sorted(days):
    seen = {}
    for hhmm, f in sorted(days[d]):
        try: J = json.load(open(f))
        except Exception: continue
        res = J.get('data', {}).get('result', {}).get('results') if isinstance(J, dict) else None
        if res is None: continue
        for r in res:
            c = r.get('columns', {}); s = c.get('Symbol') or r.get('ticker')
            try: pct = float(c.get('% Change')) * 100; last = float(c.get('Last'))
            except Exception: continue
            t = hhmm[:2] + ':' + hhmm[2:]
            x = seen.setdefault(s, dict(sym=s, name=c.get('Name', ''), first=t, first_pct=pct, first_last=last, max_pct=pct, max_t=t, n=0))
            x['n'] += 1
            if pct > x['max_pct']: x['max_pct'] = pct; x['max_t'] = t
            x['last_t'] = t; x['last_pct'] = pct
    stt = {}
    p = 'data/paper_days/scan_state_%s.json' % d
    if os.path.exists(p): stt = json.load(open(p))
    def why(s, nm):
        if (d, s) in traded: return 'TRADED'
        if FUND.search(nm or ''): return 'fund/ETF/warrant'
        for k in ('spac', 'halal_fail', 'inherited_fail', 'cannot_verify', 'fake_gap'):
            if s in stt.get(k, []): return k
        if (d, s) in vet: return 'book veto'
        return 'candidate, not top-ranked/no trigger'
    allx = sorted(seen.values(), key=lambda x: -x['max_pct'])
    common = [x for x in allx if not FUND.search(x['name'] or '')]
    print('==', d, 'dumps', len(days[d]), 'symbols', len(allx), 'common', len(common))
    for x in common[:4]:
        B = bars(x['sym'], d); r = None
        if B:
            ref = [b for b in B if b[0] <= x['first']]; end = [b for b in B if b[0] <= '14:59']
            if ref and end: r = end[-1][4] / ref[-1][4] - 1
        w = why(x['sym'], x['name'])
        summary.append(dict(date=d, sym=x['sym'], max_pct=x['max_pct'], first=x['first'], why=w, ret_first_to_close=r))
        print('   %-6s max %+6.1f%% @%s first %s (%+.1f%%) why=%s ret_first->14:59=%s  %s' % (x['sym'], x['max_pct'], x['max_t'], x['first'], x['first_pct'], w, '%+.1f%%' % (100 * r) if r is not None else 'n/a', (x['name'] or '')[:30]))
json.dump(summary, open('plan/lm15_out_movers.json', 'w'), indent=0)
c = collections.Counter(s['why'] for s in summary if s['sym'] == s['sym'])
top1 = [next(s for s in summary if s['date'] == d) for d in sorted({s['date'] for s in summary})]
print('top-1 reasons', collections.Counter(s['why'] for s in top1))
print('top-4 reasons', c)

"""Trading List: Calculate scores with 10-metric formula (0-115, normalized to 0-100)."""

SPY_1Y = 14.3  # S&P 500 1Y return %

# sym, eg, pm, roe, pe, peg, rg, vol, r6m, r1y, r3y, r5y, ocf_ni, debt_chg, stock_1y, status
data = [
    ('LLY', 0.514, 0.317, 1.012, 38.6, 0.75, 0.426, 3094283, 22.4, 8.6, 169.7, 398.9, 0.81, 26.3, 8.1, 'PASS'),
    ('LRCX', 0.37, 0.302, 0.656, 41.0, 1.11, 0.221, 11675276, 52.9, 177.4, 309.9, 254.3, 1.15, -10.0, 177.0, 'PASS'),
    ('TSM', 0.35, 0.451, 0.351, 29.9, 0.86, 0.38, 13605615, 16.5, 93.9, 256.5, 190.7, 1.32, 1.7, 93.0, 'PASS'),
    ('AMSC', 42.667, 0.467, 0.358, 11.0, 0.00, 0.214, 1055395, -47.1, 71.5, 683.7, 69.9, 0.15, 24.4, 77.6, 'PASS'),
    ('ANET', 0.191, 0.390, 0.314, 42.2, 2.21, 0.289, 7866958, -19.0, 49.0, 175.0, 515.5, 1.25, -22.2, 49.9, 'PASS'),
    ('VRT', 1.995, 0.130, 0.418, 68.7, 0.34, 0.227, 7700028, 63.5, 215.8, 1695.4, 1076.5, 1.59, 2.6, 224.8, 'PASS'),
    ('FIX', 1.295, 0.112, 0.492, 44.1, 0.34, 0.417, 430696, 59.0, 293.9, 833.8, 1641.4, 1.16, 56.6, 296.1, 'PASS'),
    ('AMD', 2.171, 0.125, 0.071, 75.3, 0.35, 0.341, 36523795, 21.5, 89.9, 100.1, 149.7, 1.81, 73.9, 90.8, 'PASS'),
    ('TDW', 5.31, 0.247, 0.270, 27.6, 0.05, -0.024, 794796, 51.8, 88.4, 102.2, 553.6, 1.13, 6.6, 93.7, 'PASS'),
    ('TJX', 0.283, 0.091, 0.591, 34.4, 1.22, 0.085, 5182993, 9.2, 33.4, 116.7, 153.4, 1.25, 1.9, 29.5, 'PASS'),
    ('RMD', 0.145, 0.275, 0.257, 21.8, 1.50, 0.11, 1056911, -18.4, 0.9, 6.5, 18.4, 1.29, -2.5, -0.8, 'PASS'),
    ('CDNS', 0.146, 0.209, 0.219, 66.8, 4.57, 0.062, 2475456, -22.3, 5.5, 32.5, 97.7, 1.56, 1.2, 6.5, 'PASS'),
    ('DECK', 0.11, 0.193, 0.397, 13.4, 1.22, 0.071, 2654726, -8.0, -14.9, 28.7, 72.5, 0.97, 3.8, -15.1, 'PASS'),
    ('ISRG', 0.166, 0.284, 0.167, 57.5, 3.46, 0.188, 1877891, 3.1, -7.9, 76.6, 83.8, 1.06, None, -8.6, 'PASS'),
    ('ETN', 0.189, 0.149, 0.215, 32.9, 1.74, 0.131, 2896113, -6.1, 26.5, 118.2, 169.0, 1.09, 7.2, 27.6, 'PASS'),
    ('HUBB', 0.138, 0.152, 0.245, 28.3, 2.05, 0.119, 542845, 11.4, 43.9, 113.3, 173.7, 1.16, 44.6, 44.4, 'PASS'),
    ('CTAS', 0.097, 0.176, 0.413, 36.5, 3.76, 0.089, 1983276, -16.9, -16.3, 58.7, 107.0, 1.14, -0.5, -17.2, 'PASS'),
    ('AWI', 0.068, 0.190, 0.372, 22.6, 3.32, 0.056, 568945, -17.2, 15.3, 142.3, 86.4, 1.15, -17.7, 14.2, 'PASS'),
    ('MLI', 0.139, 0.183, 0.256, 15.7, 1.13, 0.042, 819746, 8.2, 42.5, 212.0, 458.4, 0.99, -18.6, 43.3, 'PASS'),
    ('BMI', 0.096, 0.155, 0.215, 30.9, 3.22, 0.076, 396366, -15.9, -21.5, 29.4, 65.3, 1.30, None, -21.5, 'PASS'),
    ('FICO', 0.077, 0.319, None, 38.8, 5.04, 0.164, 334325, -31.3, -42.9, 51.7, 115.6, 1.15, 37.8, -43.2, 'PASS'),
    # FAIL
    ('JBL', 0.962, 0.025, 0.597, 33.1, 0.34, 0.231, 1180261, 15.5, 82.3, 199.0, 382.8, 2.14, 3.3, 82.2, 'FAIL'),
    ('ROST', 0.115, 0.094, 0.367, 32.1, 2.80, 0.122, 2522178, 38.1, 68.1, 112.7, 84.1, 1.41, -1.1, 65.0, 'FAIL'),
    ('LMB', 0.239, 0.060, 0.224, None, None, 0.301, 172713, -18.2, 1.5, 383.2, 633.0, 1.17, 14.7, 3.9, 'FAIL'),
    ('MANH', 0.0, 0.203, 0.717, 63.0, None, 0.166, 801436, -37.2, -24.8, -11.4, 11.1, 1.77, 17.5, -24.6, 'FAIL'),
    ('SHW', 0.014, 0.109, 0.594, None, None, 0.056, 1773365, -7.5, -6.2, 53.5, 34.2, 1.34, 8.6, -8.7, 'FAIL'),
    ('COST', 0.139, 0.030, 0.297, 45.3, 3.26, 0.092, 2235015, 9.0, 7.8, 109.6, 198.6, 1.76, 0.0, 5.9, 'FAIL'),
    ('ARM', -0.123, 0.171, 0.113, 183.8, None, 0.263, 6010940, -2.0, 27.1, 115.4, 115.4, 1.90, 57.5, 28.3, 'FAIL'),
    ('DOCS', -0.162, 0.375, 0.238, None, None, 0.098, 3463166, -68.4, -59.4, -27.0, -55.2, 1.32, -14.8, -59.1, 'FAIL'),
    ('IR', 0.184, 0.076, 0.058, None, None, 0.101, 3760601, -6.8, -3.1, 40.2, 57.2, 2.33, 0.7, -3.8, 'FAIL'),
    ('BKE', 0.035, 0.162, 0.494, None, None, 0.053, 499276, -10.4, 41.6, 85.7, 112.2, None, 3.4, 40.4, 'FAIL'),
    ('TT', -0.005, 0.137, 0.370, None, None, 0.056, 1587115, -2.3, 22.5, 128.9, 159.6, 1.08, -3.3, 20.7, 'FAIL'),
    ('FTDR', -0.84, 0.122, 1.060, None, None, 0.134, 625018, -22.1, 36.6, 96.6, -3.3, 1.63, -2.3, 35.2, 'FAIL'),
    ('REGN', -0.026, 0.314, 0.149, None, None, 0.025, 747055, 34.0, 18.2, -8.0, 59.4, 1.11, 0.1, 18.8, 'FAIL'),
    ('PNR', 0.016, 0.157, 0.175, None, None, 0.049, 1753026, -23.0, -2.3, 68.0, 43.8, 1.25, -0.1, -3.0, 'FAIL'),
    ('MPWR', -0.862, 0.223, 0.192, None, None, 0.208, 588663, 13.4, 74.3, 111.3, None, 1.35, 53.9, 73.8, 'FAIL'),
    ('PH', -0.09, 0.173, 0.258, None, None, 0.091, 717570, 14.8, 44.6, 177.9, 191.6, 1.06, -12.1, 43.0, 'FAIL'),
    ('TSCO', -0.022, 0.071, 0.452, None, None, 0.033, 6919695, -19.2, -13.6, 5.3, 39.3, 1.49, 9.6, -16.2, 'FAIL'),
    ('PODD', 0.039, 0.091, 0.181, None, None, 0.312, 979933, -33.0, -19.6, -32.9, -20.3, 2.30, -31.2, -20.8, 'FAIL'),
    ('MLM', -0.041, 0.185, 0.102, None, None, 0.086, 529035, -7.4, 20.6, 73.3, 76.1, 1.80, -1.6, 20.6, 'FAIL'),
    ('AIT', 0.05, 0.085, 0.220, None, None, 0.084, 343475, 0.2, 15.2, 98.8, 197.0, 1.21, -4.2, 15.3, 'FAIL'),
    ('SNPS', -0.82, 0.138, 0.055, None, None, 0.655, 2171625, -20.4, -12.5, 1.7, 54.6, 2.21, 1988.3, -10.7, 'FAIL'),
    ('WMT', -0.19, 0.031, 0.218, None, None, 0.056, 31047898, 20.3, 46.3, 170.5, 191.3, 1.90, 11.6, 41.9, 'FAIL'),
    ('LII', -0.179, 0.155, 0.758, None, None, -0.112, 460050, -14.3, -18.9, 87.6, None, 0.94, 19.0, -20.1, 'FAIL'),
    ('GWW', -0.02, 0.095, 0.461, None, None, 0.045, 277460, 12.0, 9.4, 63.6, 178.0, 1.18, -10.1, 8.0, 'FAIL'),
    ('CEG', -0.489, 0.091, 0.164, None, None, 0.129, 3644695, -10.4, 46.1, 315.8, 636.3, 1.83, 6.9, 48.8, 'FAIL'),
    ('TGLS', -0.431, 0.162, 0.237, None, None, 0.024, 440601, -36.6, -38.7, 15.8, None, 0.85, 57.0, -39.6, 'FAIL'),
    ('EXP', -0.096, 0.187, 0.288, None, None, -0.004, 495346, -21.9, -17.5, 32.5, 39.0, 1.34, 13.9, -17.8, 'FAIL'),
    ('AAON', -0.686, 0.075, 0.125, None, None, 0.168, 953800, -14.3, 0.6, 30.3, 72.1, 0.00, 148.4, 0.6, 'FAIL'),
    ('SHOO', -0.317, 0.018, 0.055, None, None, 0.294, 1504630, -2.8, 25.5, 0.1, -2.2, 3.63, 217.8, 25.6, 'FAIL'),
    ('IOT', None, -0.006, -0.007, None, None, 0.283, 8495123, -17.7, -21.3, 69.0, 24.0, -25.91, -9.4, -20.1, 'FAIL'),
    ('PHM', -0.421, 0.128, 0.177, None, None, -0.063, 1833825, -14.2, 12.7, 105.4, 127.5, 0.84, 1.9, 11.5, 'FAIL'),
    ('ONTO', -0.782, 0.136, 0.068, None, None, 0.011, 903285, 45.1, 55.1, 120.9, 188.0, 2.40, 15.3, 56.0, 'FAIL'),
    ('SWVL', None, -0.218, None, None, None, 0.263, 771721, -54.9, -65.7, 17.8, -99.4, 0.66, -27.5, -67.4, 'FAIL'),
    ('WSO', -0.26, 0.069, 0.187, None, None, -0.1, 418986, -11.2, -28.5, 25.9, 53.9, 1.23, 7.0, -29.4, 'FAIL'),
]


def eg_score(eg):
    if eg is None: return 0
    pct = eg * 100
    if pct > 50: return 20
    if pct > 20: return 16
    if pct > 10: return 13
    if pct > 5: return 10
    if pct > 0: return 6
    if pct > -10: return 3
    return 0

def pm_score(pm):
    """Max 14 pts."""
    if pm is None: return 0
    p = pm * 100
    if p > 30: return 14
    if p > 20: return 11
    if p > 15: return 8
    if p > 10: return 6
    if p > 5: return 3
    return 0

def roe_score(roe):
    """Max 13 pts."""
    if roe is None: return 0
    p = roe * 100
    if p > 50: return 13
    if p > 30: return 10
    if p > 20: return 8
    if p > 10: return 5
    if p > 5: return 3
    return 0

def val_score(peg):
    """Max 11 pts."""
    if peg is None: return 0
    if peg < 0.5: return 11
    if peg < 1.0: return 9
    if peg < 1.5: return 6
    if peg < 2.0: return 4
    if peg < 3.0: return 2
    return 0

def rg_score(rg):
    """Max 12 pts."""
    if rg is None: return 0
    p = rg * 100
    if p > 20: return 12
    if p > 10: return 9
    if p > 5: return 6
    if p > 0: return 3
    return 0

def perf_score(r6m, r1y, r3y, r5y):
    """Max 13 pts: 5Y(4) + 3Y(3) + 1Y(3) + 6M(3)."""
    s = 0
    # 5Y max 4
    if r5y is not None:
        if r5y > 200: s += 4
        elif r5y > 100: s += 3
        elif r5y > 50: s += 2
        elif r5y > 0: s += 1
    # 3Y max 3
    if r3y is not None:
        if r3y > 100: s += 3
        elif r3y > 50: s += 2
        elif r3y > 25: s += 1
    # 1Y max 3
    if r1y is not None:
        if r1y > 50: s += 3
        elif r1y > 25: s += 2
        elif r1y > 0: s += 1
    # 6M max 3
    if r6m is not None:
        if r6m > 25: s += 3
        elif r6m > 10: s += 2
        elif r6m > 0: s += 1
    return s

def vol_score(vol):
    """Max 9 pts."""
    if vol > 10000000: return 9
    if vol > 5000000: return 7
    if vol > 2000000: return 5
    if vol > 1000000: return 4
    if vol > 500000: return 3
    if vol > 100000: return 2
    return 0

def eq_score(ocf_ni):
    """Earnings quality: OCF/Net Income ratio. Max 7 pts."""
    if ocf_ni is None: return 0
    if ocf_ni <= 0: return 0
    if ocf_ni >= 1.5: return 7
    if ocf_ni >= 1.2: return 5
    if ocf_ni >= 1.0: return 3
    if ocf_ni >= 0.8: return 1
    return 0

def dt_score(debt_chg):
    """Debt trend: YoY debt change %. Max 8 pts."""
    if debt_chg is None: return 3  # no data = neutral
    if debt_chg <= -10: return 8   # aggressively deleveraging
    if debt_chg <= -5: return 6    # solidly deleveraging
    if debt_chg <= 0: return 5     # slightly deleveraging
    if debt_chg <= 5: return 3     # minimal increase, acceptable
    if debt_chg <= 10: return 1    # moderate increase, caution
    return 0                       # debt increasing >10% = bad

def rs_score(stock_1y):
    """Relative strength: stock 1Y return minus SPY 1Y return. Max 8 pts."""
    if stock_1y is None: return 0
    rs = stock_1y - SPY_1Y
    if rs > 60: return 8
    if rs > 40: return 7
    if rs > 20: return 5
    if rs > 0: return 3
    if rs > -15: return 1
    return 0


results = []
for row in data:
    sym, eg, pm, roe, pe, peg, rg, vol, r6m, r1y, r3y, r5y, ocf_ni, debt_chg, stock_1y, status = row
    e = eg_score(eg)
    p = pm_score(pm)
    r = roe_score(roe)
    v = val_score(peg)
    rv = rg_score(rg)
    pf = perf_score(r6m, r1y, r3y, r5y)
    vl = vol_score(vol)
    eq = eq_score(ocf_ni)
    dt = dt_score(debt_chg)
    rs = rs_score(stock_1y)

    raw = e + p + r + v + rv + pf + vl + eq + dt + rs
    normalized = round(raw / 1.15)
    bd = f"{e}+{p}+{r}+{v}+{rv}+{pf}+{vl}+{eq}+{dt}+{rs}={raw}"
    results.append((sym, status, normalized, raw, bd, pe, peg, r6m, r1y, r3y, r5y, ocf_ni, debt_chg, stock_1y))

results.sort(key=lambda x: (0 if x[1] == 'PASS' else 1, -x[2]))

for sym, status, norm, raw, bd, pe, peg, r6m, r1y, r3y, r5y, ocf_ni, debt_chg, stock_1y in results:
    pe_s = f"{pe:.1f}" if pe else "N/A"
    peg_s = f"{peg:.2f}" if peg is not None else "N/A"
    r6m_s = f"{r6m:+.0f}%" if r6m is not None else "N/A"
    r1y_s = f"{r1y:+.0f}%" if r1y is not None else "N/A"
    r3y_s = f"{r3y:+.0f}%" if r3y is not None else "N/A"
    r5y_s = f"{r5y:+.0f}%" if r5y is not None else "N/A"
    eq_s = f"{ocf_ni:.2f}" if ocf_ni is not None else "N/A"
    dt_s = f"{debt_chg:+.0f}%" if debt_chg is not None else "N/A"
    rs_val = stock_1y - SPY_1Y if stock_1y is not None else None
    rs_s = f"{rs_val:+.0f}%" if rs_val is not None else "N/A"
    print(f"{sym}|{status}|{norm}|{raw}/115|{bd}|{pe_s}|{peg_s}|{eq_s}|{dt_s}|{rs_s}|{r6m_s}|{r1y_s}|{r3y_s}|{r5y_s}")

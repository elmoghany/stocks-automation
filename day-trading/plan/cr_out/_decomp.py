import sys, numpy as np, json, collections
sys.path.insert(0, r"C:\cornell\stocks-automation\day-trading\plan")
import cr_cost as CC
from datetime import time as dtime
fs = sorted(CC.CDIR.glob("*.npz"))
step = max(1, len(fs)//400); sel = fs[::step][:400]
cm = CC.CostModel()
MIN=[5,10,20,35,60,90,120,180,240,300,350]
rec=[]
for f in sel:
    s,d = f.name[:-4].split("_",1)
    for m in MIN:
        t = dtime((CC.MIN_M+m)//60,(CC.MIN_M+m)%60)
        h,i,tier = cm.parts(s,d,t,15000.0)
        rec.append((m,h,i,tier))
H=np.array([r[1] for r in rec]); I=np.array([r[2] for r in rec]); M=np.array([r[0] for r in rec])
out={"n":len(rec)}
for nm,a in (("half_spread",H),("impact",I),("total",H+I)):
    out[nm]=dict(median=float(np.median(a)),mean=float(a.mean()),
                 p25=float(np.percentile(a,25)),p75=float(np.percentile(a,75)),
                 p90=float(np.percentile(a,90)))
out["frac_total_gt10"]=float(((H+I)>10).mean())
out["frac_half_gt10"]=float((H>10).mean())
out["tiers"]=dict(collections.Counter([r[3] for r in rec]))
buckets={}
for lo,hi,nm in ((0,16,"09:30-09:45"),(16,61,"09:46-10:30"),(61,181,"10:31-12:30"),(181,400,"12:31-16:00")):
    k=(M>=lo)&(M<hi)
    if k.sum():
        buckets[nm]=dict(n=int(k.sum()),half=float(np.median(H[k])),
                         impact=float(np.median(I[k])),total=float(np.median((H+I)[k])),
                         frac_gt10=float((((H+I)[k])>10).mean()))
out["by_time"]=buckets
# impact-coefficient sensitivity
for c in (0.0,0.3,0.5,1.0):
    t_=H+I*c
    out[f"total_coef{c}"]=dict(median=float(np.median(t_)),mean=float(t_.mean()),
                               frac_gt10=float((t_>10).mean()))
print(json.dumps(out,indent=1))
open(r"C:\cornell\stocks-automation\day-trading\plan\cr_out\cost_decomp.json","w").write(json.dumps(out,indent=1))

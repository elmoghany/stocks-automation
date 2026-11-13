"""Pick, per variant, the learning-rate run with the lowest early-stopping loss (early-stopping windows are inside the train period only)."""
import json, sys, glob
variant = sys.argv[1]
runs = []
for f in glob.glob(f"adapter_{variant}_lr*/train_log.json"):
    d = json.load(open(f))
    runs.append((d["best_es_loss"], f.split("/")[0], d["args"]["lr"], d["best_epoch"], d["epoch0_es_loss"]))
runs.sort()
for r in runs:
    print(variant, "es_loss %.4f  adapter %s lr %s best_epoch %d  (epoch0 zero-shot es_loss %.4f)" % r, file=sys.stderr)
print(runs[0][1])

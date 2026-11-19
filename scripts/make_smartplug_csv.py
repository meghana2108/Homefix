"""Generate a synthetic smart-plug power log for a fridge (for the code demo). Committable.

    uv run python scripts/make_smartplug_csv.py [--days 7] [--out data/smartplug_fridge.csv]

Normal fridge: compressor ON ~110-140 W for 15-25 min, OFF 25-45 min, a defrost spike daily.
Injected faults: a few long-running cycles (70-150 min ON) - the thing the generated code should flag.
"""

from __future__ import annotations

import argparse
import csv
import random
from datetime import datetime, timedelta
from pathlib import Path


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--out", default="data/smartplug_fridge.csv")
    a = ap.parse_args()
    rng = random.Random(a.seed)

    t = datetime(2026, 11, 9, 0, 0)
    end = t + timedelta(days=a.days)
    faults = {rng.randrange(20, a.days * 24 * 60 // 40) for _ in range(4)}  # cycle indices that run long
    rows, cycle, last_defrost = [], 0, t
    while t < end:
        on_min = rng.randint(70, 150) if cycle in faults else rng.randint(15, 25)
        for _ in range(on_min):
            rows.append((t, round(rng.uniform(110, 140), 1)))
            t += timedelta(minutes=1)
        if t - last_defrost > timedelta(hours=24):
            for _ in range(20):
                rows.append((t, round(rng.uniform(380, 420), 1)))
                t += timedelta(minutes=1)
            last_defrost = t
        for _ in range(rng.randint(25, 45)):
            rows.append((t, round(rng.uniform(0.8, 2.5), 1)))
            t += timedelta(minutes=1)
        cycle += 1

    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["timestamp", "watts"])
        w.writerows((ts.isoformat(timespec="minutes"), watts) for ts, watts in rows)
    print(f"wrote {len(rows)} rows ({a.days} days, {len(faults)} long cycles injected) -> {out}")


if __name__ == "__main__":
    main()

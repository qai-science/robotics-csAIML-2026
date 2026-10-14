"""Plot e-puck paths and arena coverage from trajectories.csv."""
import csv
import os
import sys
from collections import defaultdict

import matplotlib.pyplot as plt
import numpy as np

here = os.path.dirname(os.path.abspath(__file__))
src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(here, "trajectories.csv")
paths = defaultdict(list)
with open(src) as f:
    for row in csv.DictReader(f):
        paths[row["robot"]].append((float(row["x"]), float(row["y"])))

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 5))
allp = np.vstack([np.array(p) for p in paths.values()])
# Arena half-width: 0.8 m for the swarm, 4 m for the Pioneer room.
H_ = 0.8 if np.abs(allp).max() < 0.85 else 4.0
CELL = 0.1 if H_ < 1 else 0.5
for name, p in sorted(paths.items()):
    p = np.array(p)
    ax1.plot(p[:, 0], p[:, 1], lw=1, label=name)
    ax1.plot(*p[0], "o", ms=4, color=ax1.lines[-1].get_color())
ax1.set(xlim=(-H_, H_), ylim=(-H_, H_), aspect="equal", title="Paths (dot = start)")
ax1.legend(fontsize=8)

bins = int(round(2 * H_ / CELL))
H, _, _ = np.histogram2d(allp[:, 0], allp[:, 1], bins=bins, range=[[-H_, H_], [-H_, H_]])
ax2.imshow(H.T > 0, origin="lower", extent=(-H_, H_, -H_, H_), cmap="Greens")
ax2.set(title=f"Cells visited: {(H > 0).mean():.0%} of {CELL * 100:.0f} cm grid", aspect="equal")
fig.tight_layout()
png = os.path.splitext(src)[0] + ".png"
fig.savefig(png, dpi=150)
print("saved", png)

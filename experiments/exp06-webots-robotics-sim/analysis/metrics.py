"""Metrics for a trajectory CSV written by the trajectory_logger supervisor.

  python analysis/metrics.py analysis/trajectories.csv swarm

path length : metres driven, summed over samples
mean speed  : path length / time
stuck       : share of samples where the robot moved less than 1 cm/s
coverage    : share of grid cells (10 cm swarm, 50 cm pioneer) visited
"""
import csv
import math
import sys
from collections import defaultdict

GRID = {"swarm": (0.8, 0.1), "pioneer": (4.0, 0.5)}


def summarise(path, world):
    half, cell = GRID[world]
    tracks = defaultdict(list)
    with open(path) as f:
        for r in csv.DictReader(f):
            tracks[r["robot"]].append((float(r["t"]), float(r["x"]), float(r["y"])))
    visited = set()
    n = int(round(2 * half / cell))
    print(f"{'robot':<10}{'path m':>8}{'mean m/s':>10}{'stuck %':>9}")
    for name, p in sorted(tracks.items()):
        length, stuck = 0.0, 0
        for (t0, x0, y0), (t1, x1, y1) in zip(p, p[1:]):
            d = math.hypot(x1 - x0, y1 - y0)
            length += d
            stuck += d / max(t1 - t0, 1e-9) < 0.01
        for _, x, y in p:
            visited.add((min(n - 1, int((x + half) / cell)), min(n - 1, int((y + half) / cell))))
        dur = p[-1][0] - p[0][0]
        print(f"{name:<10}{length:8.2f}{length / max(dur, 1e-9):10.3f}{100 * stuck / max(len(p) - 1, 1):9.1f}")
    print(f"coverage: {100 * len(visited) / n**2:.0f}% of {n}x{n} grid ({cell * 100:.0f} cm cells)")


if __name__ == "__main__":
    summarise(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "swarm")

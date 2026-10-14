"""Supervisor that records robot poses to a CSV file.

Logs every robot whose DEF name starts with EPUCK or is PIONEER, once every
EVERY steps, for --seconds of simulated time. Then it pauses the simulation,
or quits Webots if --quit=1 (used by tools/run_experiment.py).

controllerArgs: "--seconds=120" "--out=analysis/trajectories.csv" "--quit=0"
"""
import csv
import math
import os
import sys
from controller import Supervisor

args = {"seconds": "120", "out": "analysis/trajectories.csv", "quit": "0"}
for a in sys.argv[1:]:
    k, _, v = a.lstrip("-").partition("=")
    args[k] = v
SIM_SECONDS = float(args["seconds"])
EVERY = 10  # steps between samples

sup = Supervisor()
dt = int(sup.getBasicTimeStep())

robots = []
i = 1
while (node := sup.getFromDef(f"EPUCK{i}")) is not None:
    robots.append((f"e-puck{i}", node))
    i += 1
if (node := sup.getFromDef("PIONEER")) is not None:
    robots.append(("pioneer", node))

root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
out = args["out"] if os.path.isabs(args["out"]) else os.path.join(root, args["out"])
os.makedirs(os.path.dirname(out), exist_ok=True)
with open(out, "w", newline="") as f:
    w = csv.writer(f)
    w.writerow(["t", "robot", "x", "y", "yaw"])
    step = 0
    while sup.step(dt) != -1:
        step += 1
        t = sup.getTime()
        if step % EVERY == 0:
            for name, node in robots:
                x, y, _ = node.getPosition()
                R = node.getOrientation()
                w.writerow([f"{t:.3f}", name, f"{x:.4f}", f"{y:.4f}", f"{math.atan2(R[3], R[0]):.4f}"])
        if t >= SIM_SECONDS:
            f.flush()
            print(f"Logged {len(robots)} robots for {SIM_SECONDS:.0f} s -> {out}")
            break

if args["quit"] == "1":
    sup.simulationQuit(0)
else:
    sup.simulationSetMode(Supervisor.SIMULATION_MODE_PAUSE)

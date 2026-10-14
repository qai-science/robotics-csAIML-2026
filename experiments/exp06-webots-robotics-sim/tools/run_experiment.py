"""Run one Webots world headless with chosen parameters and print metrics.

Works on macOS, Windows and Linux. Examples:

  python tools/run_experiment.py swarm --seconds 60 --set cruise=0.8 gain=2
  python tools/run_experiment.py pioneer --seconds 120 --set lookahead=4 bubble=0.3

Parameters after --set go to every robot controller in the world (the logger
is configured separately). Set WEBOTS_HOME if Webots is not installed in the
default place.
"""
import argparse
import os
import platform
import re
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "analysis"))
from metrics import summarise  # noqa: E402

WORLDS = {
    "swarm": ("swarm_arena.wbt", "epuck_braitenberg"),
    "pioneer": ("pioneer_lidar.wbt", "pioneer_lidar_nav"),
}


def find_webots():
    home = os.environ.get("WEBOTS_HOME")
    candidates = []
    system = platform.system()
    if home:
        candidates += [os.path.join(home, "Contents", "MacOS", "webots"),
                       os.path.join(home, "msys64", "mingw64", "bin", "webots.exe"),
                       os.path.join(home, "webots")]
    if system == "Darwin":
        candidates.append("/Applications/Webots.app/Contents/MacOS/webots")
    elif system == "Windows":
        for base in (os.environ.get("ProgramFiles", r"C:\Program Files"),
                     os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs")):
            candidates.append(os.path.join(base, "Webots", "msys64", "mingw64", "bin", "webots.exe"))
    else:
        candidates += ["/usr/local/bin/webots", "/usr/bin/webots", "/snap/bin/webots"]
    for c in candidates:
        if c and os.path.isfile(c):
            return c
    found = shutil.which("webots")
    if found:
        return found
    sys.exit("Could not find Webots. Install it or set WEBOTS_HOME (see GUIDE.md).")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("world", choices=WORLDS)
    ap.add_argument("--seconds", type=float, default=120, help="simulated seconds to run")
    ap.add_argument("--set", nargs="*", default=[], metavar="NAME=VALUE", help="controller parameters")
    ap.add_argument("--name", default=None, help="label for the output CSV")
    a = ap.parse_args()

    wfile, ctrl = WORLDS[a.world]
    label = a.name or (a.world + ("_" + "_".join(a.set) if a.set else "_default"))
    label = re.sub(r"[^A-Za-z0-9_.=-]", "", label).replace("=", "-")
    out = os.path.join(ROOT, "analysis", "runs", label + ".csv")

    src = open(os.path.join(ROOT, "worlds", wfile)).read()
    robot_args = " ".join(f'"--{s}"' for s in a.set)
    src = src.replace(f'controller "{ctrl}"', f'controller "{ctrl}" controllerArgs [ {robot_args} ]')
    log_args = f'"--seconds={a.seconds}" "--out={out}" "--quit=1"'
    src = re.sub(r'controller "trajectory_logger"(\s*controllerArgs \[[^\]]*\])?',
                 f'controller "trajectory_logger" controllerArgs [ {log_args} ]', src)
    tmp = os.path.join(ROOT, "worlds", f"_experiment_{a.world}.wbt")
    with open(tmp, "w") as f:
        f.write(src)

    cmd = [find_webots(), "--mode=fast", "--no-rendering", "--batch", "--minimize",
           "--stdout", "--stderr", tmp]
    print(f"Running {a.world} for {a.seconds:.0f} s with {a.set or 'default parameters'} ...")
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=max(120, a.seconds * 3))
        errors = [l for l in (proc.stdout + proc.stderr).splitlines() if "ERROR" in l]
        if errors:
            print("\n".join(errors))
    finally:
        os.remove(tmp)
    if not os.path.exists(out):
        sys.exit("No trajectory was written; open the world in the Webots window to see the error.")
    print(f"Trajectory: {os.path.relpath(out, ROOT)}")
    summarise(out, a.world)


if __name__ == "__main__":
    main()

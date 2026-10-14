"""Follow-the-gap navigation for a Pioneer 3-DX with a SICK LMS 291.

Every step the 180-beam scan is clipped to a look-ahead distance, a safety
bubble is cut around the closest return, and the robot steers toward the
middle of the widest remaining free gap. Forward speed falls with the nearest
obstacle in front, so the robot slows down in tight spots.

Parameters can be changed without editing this file: select the Pioneer in
the Webots scene tree and add entries to `controllerArgs`, e.g.
"--lookahead=4" "--bubble=0.3". Defaults are in PARAMS below.
"""
import math
import sys
from controller import Robot

PARAMS = {
    "lookahead": 2.5,  # m, beams beyond this count as free
    "free": 1.0,       # m, a beam longer than this is part of a gap
    "bubble": 0.45,    # m, safety radius cut around the closest return
    "stop": 0.35,      # m, stop driving forward (turn only) below this
    "max_v": 0.6,      # m/s, top forward speed
    "slow": 0.35,      # forward speed = slow * front distance, capped at max_v
    "k_turn": 2.0,     # turn rate per radian of heading error
    "max_w": 1.5,      # rad/s, turn-rate limit
}
for a in sys.argv[1:]:
    k, _, v = a.lstrip("-").partition("=")
    if k in PARAMS:
        PARAMS[k] = float(v)

MAX_SPEED = 12.3        # rad/s, wheel limit from the PROTO
WHEEL_RADIUS = 0.0975   # m
AXLE = 0.33             # m, wheel separation
LOOKAHEAD = PARAMS["lookahead"]
BUBBLE = PARAMS["bubble"]
STOP_DIST = PARAMS["stop"]

robot = Robot()
dt = int(robot.getBasicTimeStep())

lidar = robot.getDevice("Sick LMS 291")
lidar.enable(dt)
n = lidar.getHorizontalResolution()
fov = lidar.getFov()
# Beam i points at angle a_i; Webots lidar scans from left (+fov/2) to right.
angles = [fov / 2 - i * fov / (n - 1) for i in range(n)]

left = robot.getDevice("left wheel")
right = robot.getDevice("right wheel")
for m in (left, right):
    m.setPosition(float("inf"))
    m.setVelocity(0.0)


def widest_gap(free):
    best, start = (0, 0), None
    for i, f in enumerate(free + [False]):
        if f and start is None:
            start = i
        elif not f and start is not None:
            if i - start > best[1] - best[0]:
                best = (start, i)
            start = None
    return best


step = 0
while robot.step(dt) != -1:
    r = [min(d, LOOKAHEAD) if math.isfinite(d) else LOOKAHEAD for d in lidar.getRangeImage()]
    if not r:
        continue

    k = min(range(n), key=r.__getitem__)
    dmin = r[k]
    free = [d > PARAMS["free"] for d in r]
    if dmin < LOOKAHEAD:
        # Angular half-width of the safety bubble at the closest obstacle.
        half = math.atan2(BUBBLE, max(dmin, 1e-3))
        for i in range(n):
            if abs(angles[i] - angles[k]) < half:
                free[i] = False

    a, b = widest_gap(free)
    if b > a:
        # Aim at the deepest beam inside the gap, centred on the gap.
        mid = (a + b - 1) // 2
        target = angles[mid]
    else:
        target = math.pi / 2  # boxed in: turn left

    front = min(r[n // 3: 2 * n // 3])
    v = 0.0 if front < STOP_DIST else min(PARAMS["max_v"], PARAMS["slow"] * front)  # m/s
    w = max(-PARAMS["max_w"], min(PARAMS["max_w"], PARAMS["k_turn"] * target))  # rad/s

    wl = (v - w * AXLE / 2) / WHEEL_RADIUS
    wr = (v + w * AXLE / 2) / WHEEL_RADIUS
    s = max(1.0, abs(wl) / MAX_SPEED, abs(wr) / MAX_SPEED)
    left.setVelocity(wl / s)
    right.setVelocity(wr / s)

    step += 1
    if step % 60 == 0:
        print(f"t={robot.getTime():6.1f}s  nearest={dmin:4.2f} m  front={front:4.2f} m  "
              f"heading_cmd={math.degrees(target):+5.1f} deg  v={v:4.2f} m/s")

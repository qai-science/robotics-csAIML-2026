"""Braitenberg obstacle avoidance for the e-puck.

Each of the eight IR proximity sensors pushes the wheels with a fixed weight,
so an obstacle on the left speeds up the left wheel and the robot turns away.
A small per-robot speed bias (from the robot name) keeps the swarm from moving
in lock-step.

Parameters can be changed without editing this file: in Webots, select an
e-puck in the scene tree and add entries to its `controllerArgs`, e.g.
"--cruise=0.8" "--gain=2". Defaults are in PARAMS below.
"""
import sys
from controller import Robot

PARAMS = {
    "cruise": 0.5,   # forward drive with no obstacle, as a fraction of max speed (0..1)
    "gain": 4.0,     # how strongly sensor readings turn the robot
    "speed": 1.0,    # scales the final wheel speed (0..1)
    "noise": 0.0,    # random wheel-speed noise, fraction of max speed (0 = off)
}
for a in sys.argv[1:]:
    k, _, v = a.lstrip("-").partition("=")
    if k in PARAMS:
        PARAMS[k] = float(v)

MAX_SPEED = 6.28
# Weights per sensor (ps0..ps7) for the left and right wheel, from the classic
# e-puck Braitenberg vehicle. ps0/ps7 face forward, ps2/ps5 sideways.
W_LEFT = [-1.3, -1.0, -0.5, 0.0, 0.0, 0.5, 1.0, 1.3]
W_RIGHT = [1.3, 1.0, 0.5, 0.0, 0.0, -0.5, -1.0, -1.3]
SENSOR_RANGE = 4096.0

robot = Robot()
dt = int(robot.getBasicTimeStep())

sensors = [robot.getDevice(f"ps{i}") for i in range(8)]
for s in sensors:
    s.enable(dt)

left = robot.getDevice("left wheel motor")
right = robot.getDevice("right wheel motor")
for m in (left, right):
    m.setPosition(float("inf"))
    m.setVelocity(0.0)

bias = 0.85 + 0.03 * (sum(map(ord, robot.getName())) % 5)
if PARAMS["noise"] > 0:
    import random
    random.seed(robot.getName())

while robot.step(dt) != -1:
    x = [min(s.getValue(), SENSOR_RANGE) / SENSOR_RANGE for s in sensors]
    vl = PARAMS["cruise"] + sum(w * v for w, v in zip(W_LEFT, x)) * PARAMS["gain"]
    vr = PARAMS["cruise"] + sum(w * v for w, v in zip(W_RIGHT, x)) * PARAMS["gain"]
    if PARAMS["noise"] > 0:
        vl += random.gauss(0, PARAMS["noise"])
        vr += random.gauss(0, PARAMS["noise"])
    k = MAX_SPEED * bias * PARAMS["speed"]
    left.setVelocity(max(-1.0, min(1.0, vl)) * k)
    right.setVelocity(max(-1.0, min(1.0, vr)) * k)

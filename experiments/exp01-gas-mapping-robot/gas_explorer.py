"""Gas-sensing vehicle: explores the room for 120 s and streams CH4 / CO2 readings to the base station.

What it does, in order:
  1. Builds the room in CoppeliaSim: walls, two gas leaks drawn as coloured clouds
     (CH4 green, CO2 purple; the more opaque and dense a region, the higher the concentration).
  2. Loads a Pioneer P3-DX, removes its own script, and mounts a gas sensor head on it.
  3. Connects to the base station over TCP.
  4. Drives a lawnmower (back-and-forth) sweep with a go-to-goal controller for --duration seconds,
     paced to real time. Every --sample-period seconds it reads both sensors and sends one JSON line.
  5. Leaves a trail of coloured discs on the floor showing what was measured where.

The sensors are modelled in gas_field.py (lag, noise, resolution, range). The true value at
each sample is also saved locally (results/robot_truth.csv) so the analysis can judge the
sensor; the base station only ever sees what a real robot would send.

    python base_station.py            # terminal 1 (start first)
    python gas_explorer.py            # terminal 2
    python gas_explorer.py --base-host 192.168.1.10 --ideal-sensors --fast
"""
import argparse
import csv
import json
import math
import os
import socket
import time

from coppeliasim_zmqremoteapi_client import RemoteAPIClient

import gas_field as gf

HERE = os.path.dirname(os.path.abspath(__file__))
WHEEL_R, AXLE_L = 0.0975, 0.331
SENSOR_Z = 0.35                 # height of the sensor inlet above the floor, m
SENSOR_FWD = 0.12               # inlet sits this far ahead of the robot centre, m
LANE = 0.8                      # spacing of the sweep lanes, m
EDGE = 2.0                      # sweep stays inside |x|, |y| <= EDGE


def model_path():
    root = os.environ.get('COPPELIASIM_ROOT', os.path.expanduser('~/CoppeliaSim'))
    return os.path.join(root, 'models', 'robots', 'mobile', 'pioneer p3dx.ttm')


def wrap(a):
    return math.atan2(math.sin(a), math.cos(a))


def lawnmower():
    ys, pts = [], []
    y = -EDGE
    while y <= EDGE + 1e-6:
        ys.append(round(y, 3))
        y += LANE
    for i, y in enumerate(ys):
        xs = (-EDGE, EDGE) if i % 2 == 0 else (EDGE, -EDGE)
        pts += [(xs[0], y), (xs[1], y)]
    return pts


def wall(sim, size, pos):
    h = sim.createPrimitiveShape(sim.primitiveshape_cuboid, size, 0)
    sim.setObjectPosition(h, -1, pos)
    sim.setObjectInt32Param(h, sim.shapeintparam_static, 1)
    sim.setObjectInt32Param(h, sim.shapeintparam_respondable, 1)
    sim.setShapeColor(h, None, sim.colorcomponent_ambient_diffuse, [0.6, 0.6, 0.65])
    return h


def draw_clouds(sim, n_points):
    """Each gas as translucent spheres: point density and opacity both follow concentration."""
    handles = []
    for gas, seed in (('CH4', 11), ('CO2', 22)):
        pts = gf.sample_cloud(gas, n_points, seed=seed)
        peak = gf.SOURCES[gas]['peak']
        d = sim.addDrawingObject(sim.drawing_spherepts + sim.drawing_itemcolors + sim.drawing_itemtransparency,
                                 0.045, 0, -1, n_points + 10, None)
        for x, y, z, c in pts:
            alpha = 0.15 + 0.75 * min(c / peak, 1.0)       # 0 = invisible, 1 = solid
            sim.addDrawingObjectItem(d, [x, y, z, *gf.COLOR[gas], 1 - alpha])
        handles.append(d)
        # mark the leak itself
        s = gf.SOURCES[gas]
        m = sim.createPrimitiveShape(sim.primitiveshape_cylinder, [0.16, 0.16, 0.04], 0)
        sim.setObjectPosition(m, -1, [s['x'], s['y'], 0.02])
        sim.setObjectInt32Param(m, sim.shapeintparam_static, 1)
        sim.setObjectInt32Param(m, sim.shapeintparam_respondable, 0)
        sim.setShapeColor(m, None, sim.colorcomponent_ambient_diffuse, list(gf.COLOR[gas]))
        sim.setObjectAlias(m, f'{gas}_leak')
    return handles


def build_scene(sim, n_points):
    sim.closeScene()
    half, t = gf.ARENA / 2, 0.08
    for pos, size in [([0, half, 0.25], [gf.ARENA, t, 0.5]), ([0, -half, 0.25], [gf.ARENA, t, 0.5]),
                      ([half, 0, 0.25], [t, gf.ARENA, 0.5]), ([-half, 0, 0.25], [t, gf.ARENA, 0.5])]:
        wall(sim, size, pos)
    draw_clouds(sim, n_points)

    robot = sim.loadModel(model_path())
    sim.removeObjects([sim.getObject('/PioneerP3DX/Script')])
    start = lawnmower()[0]
    sim.setObjectPosition(robot, -1, [start[0], start[1], sim.getObjectPosition(robot, -1)[2]])
    sim.setObjectOrientation(robot, -1, [0, 0, 0])

    # Sensor head: a mast with a gas inlet on top. Non-dynamic children ride along with the robot body.
    mast = sim.createPrimitiveShape(sim.primitiveshape_cylinder, [0.025, 0.025, SENSOR_Z - 0.2], 0)
    sim.setObjectPosition(mast, -1, [start[0] + SENSOR_FWD, start[1], 0.2 + (SENSOR_Z - 0.2) / 2])
    head = sim.createPrimitiveShape(sim.primitiveshape_cuboid, [0.07, 0.07, 0.04], 0)
    sim.setObjectPosition(head, -1, [start[0] + SENSOR_FWD, start[1], SENSOR_Z])
    for h, col in ((mast, [0.2, 0.2, 0.2]), (head, [0.95, 0.75, 0.1])):
        sim.setObjectInt32Param(h, sim.shapeintparam_static, 1)
        sim.setObjectInt32Param(h, sim.shapeintparam_respondable, 0)
        sim.setShapeColor(h, None, sim.colorcomponent_ambient_diffuse, col)
    sim.setObjectParent(head, mast, True)
    sim.setObjectParent(mast, robot, True)
    sim.setObjectAlias(head, 'gasSensorHead')
    return robot, head


def connect(host, port, tries=30):
    for i in range(tries):
        try:
            s = socket.create_connection((host, port), timeout=3)
            s.settimeout(None)
            return s
        except OSError:
            if i == 0:
                print(f'[robot] waiting for base station at {host}:{port} ...', flush=True)
            time.sleep(1)
    raise SystemExit(f'[robot] no base station at {host}:{port}; start base_station.py first')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--duration', type=float, default=120.0, help='exploration time, simulated s')
    ap.add_argument('--sample-period', type=float, default=0.2, help='seconds between readings (0.2 = 5 Hz)')
    ap.add_argument('--speed', type=float, default=0.32, help='driving speed, m/s')
    ap.add_argument('--base-host', default='127.0.0.1', help='IP of the computer running base_station.py')
    ap.add_argument('--base-port', type=int, default=5055)
    ap.add_argument('--ideal-sensors', action='store_true', help='no lag, no noise (for comparison)')
    ap.add_argument('--fast', action='store_true', help='run as fast as possible instead of real time')
    ap.add_argument('--cloud-points', type=int, default=2500, help='points drawn per gas cloud')
    ap.add_argument('--truth-out', default=os.path.join(HERE, 'results', 'robot_truth.csv'))
    args = ap.parse_args()
    os.makedirs(os.path.dirname(args.truth_out), exist_ok=True)

    sim = RemoteAPIClient().require('sim')
    if sim.getSimulationState() != sim.simulation_stopped:
        sim.stopSimulation()
        while sim.getSimulationState() != sim.simulation_stopped:
            time.sleep(0.05)
    print('[robot] building the scene ...', flush=True)
    robot, head = build_scene(sim, args.cloud_points)
    left = sim.getObject('/PioneerP3DX/leftMotor')
    right = sim.getObject('/PioneerP3DX/rightMotor')
    trail = sim.addDrawingObject(sim.drawing_discpts + sim.drawing_itemcolors, 0.09, 0, -1, 100000, None)

    link = connect(args.base_host, args.base_port)
    sensors = {g: gf.GasSensor(g, seed=k, ideal=args.ideal_sensors) for k, g in enumerate(('CH4', 'CO2'))}
    link.sendall((json.dumps({'type': 'hello', 'robot': 'Pioneer P3-DX', 'duration_s': args.duration,
                              'sample_period_s': args.sample_period, 'sensor_height_m': SENSOR_Z,
                              'ideal_sensors': args.ideal_sensors,
                              'started': time.strftime('%Y-%m-%d %H:%M:%S')}) + '\n').encode())

    goals = lawnmower()
    gi = 1
    sim.setStepping(True)
    sim.startSimulation()
    dt = sim.getSimulationTimeStep()
    every = max(1, round(args.sample_period / dt))
    wall0, step, n, rows = time.time(), 0, 0, []
    rendering, since_render, frames, max_skip = True, 0, 0, max(1, round(0.5 / dt))
    sim.setBoolParam(sim.boolparam_display_enabled, True)
    print(f'[robot] exploring for {args.duration:.0f} s, one reading every {every * dt:.2f} s', flush=True)
    while (t := sim.getSimulationTime()) < args.duration:
        # One call gives the sensor head's position and heading (its x-axis points where the robot faces);
        # fewer calls per step is what lets the loop keep up with real time.
        m = sim.getObjectMatrix(head, -1)
        hx, hy, hz = m[3], m[7], m[11]
        th = math.atan2(m[4], m[0])
        x, y = hx - SENSOR_FWD * math.cos(th), hy - SENSOR_FWD * math.sin(th)

        # go-to-goal on the lawnmower path; turn on the spot when the heading error is large
        gx, gy = goals[gi]
        if math.hypot(gx - x, gy - y) < 0.15:
            gi = (gi + 1) % len(goals)
            if gi == 0:
                goals = goals[::-1]          # sweep back the other way
                gi = 1
            gx, gy = goals[gi]
        alpha = wrap(math.atan2(gy - y, gx - x) - th)
        v = args.speed * max(math.cos(alpha), 0.0) ** 3
        w = 2.5 * alpha
        sim.setJointTargetVelocity(left, (v - w * AXLE_L / 2) / WHEEL_R)
        sim.setJointTargetVelocity(right, (v + w * AXLE_L / 2) / WHEEL_R)

        # sense both gases at the inlet every physics step (the sensor lag is integrated per step)
        true ={g: gf.concentration(g, hx, hy, hz) for g in sensors}
        meas = {g: sensors[g].update(true[g], dt) for g in sensors}

        if step % every == 0:
            n += 1
            msg = {'type': 'reading', 'n': n, 't': round(t, 2), 'x': round(hx, 3), 'y': round(hy, 3),
                   'z': round(hz, 3), 'sent': time.time()}
            for g in sensors:
                msg[g] = meas[g]
                msg[f'{g}_status'] = gf.status(g, meas[g])
            link.sendall((json.dumps(msg) + '\n').encode())
            rows.append([n, round(t, 2), round(hx, 3), round(hy, 3), round(hz, 3), round(true['CH4'], 1),
                         meas['CH4'], round(true['CO2'], 1), meas['CO2']])
            # trail disc: colour mixes green (CH4) and purple (CO2) by how high each reading is
            a = min(max(meas['CH4'] - 2, 0) / gf.ALARM['CH4'], 1.0)
            b = min(max(meas['CO2'] - 420, 0) / gf.ALARM['CO2'], 1.0)
            base = 0.85
            col = [base * (1 - a - b + a * b) + a * gf.COLOR['CH4'][i] + b * gf.COLOR['CO2'][i] for i in range(3)]
            col = [min(max(c, 0.0), 1.0) for c in col]
            sim.addDrawingObjectItem(trail, [hx, hy, 0.003, *col])
            if n % 25 == 0:
                print(f'[robot] t={t:6.1f}s ({hx:+.2f},{hy:+.2f})  CH4={meas["CH4"]:6.0f}  CO2={meas["CO2"]:6.0f} ppm',
                      flush=True)

        # Real-time pacing. Drawing the 3-D view is by far the slowest part of a step on a VM,
        # so a frame is rendered only when the simulation is ahead of the wall clock (or at least
        # every max_skip steps); physics, sensing and data logging still run at every step.
        ahead = (step + 1) * dt - (time.time() - wall0)
        render = (ahead > 0 and not args.fast) or since_render >= max_skip
        if render != rendering:
            sim.setBoolParam(sim.boolparam_display_enabled, render)
            rendering = render
        since_render = 0 if render else since_render + 1
        frames += render
        sim.step()
        step += 1
        if not args.fast:
            ahead = step * dt - (time.time() - wall0)
            if ahead > 0:
                time.sleep(ahead)

    sim.setBoolParam(sim.boolparam_display_enabled, True)
    sim.setJointTargetVelocity(left, 0)
    sim.setJointTargetVelocity(right, 0)
    sim.stopSimulation()
    sim.setStepping(False)
    link.sendall((json.dumps({'type': 'end', 'readings': n, 'sim_time_s': round(t, 2),
                              'wall_time_s': round(time.time() - wall0, 1)}) + '\n').encode())
    link.close()
    with open(args.truth_out, 'w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['n', 't', 'x', 'y', 'z', 'CH4_true', 'CH4_meas', 'CO2_true', 'CO2_meas'])
        w.writerows(rows)
    print(f'[robot] done: {n} readings in {t:.1f} s simulated / {time.time() - wall0:.1f} s wall clock, '
          f'{frames} of {step} steps rendered', flush=True)


if __name__ == '__main__':
    main()

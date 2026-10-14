"""Gas environment and gas sensor models shared by the robot, the base station and the analysis.

Two leaks are placed in a 5 m x 5 m room with a gentle draught blowing towards +x.
Each leak makes a plume whose concentration falls off smoothly (Gaussian) with
distance, is stretched and shifted downwind, and has a height profile that
follows the gas density:

  CH4 (methane)        0.66 kg/m^3, lighter than air -> rises; concentration grows with height
  CO2 (carbon dioxide) 1.98 kg/m^3, heavier than air -> pools near the floor; falls with height

Concentrations are in ppm (parts per million by volume) on top of normal
outdoor background levels (CH4 about 2 ppm, CO2 about 420 ppm).

The sensor model turns the true concentration at the sensor inlet into what a
real sensor reports: first-order response lag, random noise, resolution and range.
"""
import math
import random

ARENA = 5.0

# name: (source x, y, peak ppm above background, sigma across wind, sigma along wind, downwind shift)
SOURCES = {
    'CH4': dict(x=-1.2, y=0.9, peak=9000.0, sig_cross=0.55, sig_along=1.0, shift=0.45, background=2.0),
    'CO2': dict(x=1.0, y=-1.0, peak=12000.0, sig_cross=0.6, sig_along=0.9, shift=0.35, background=420.0),
}

# Alarm thresholds (ppm)
#   CH4: lower explosive limit is 5 % vol = 50,000 ppm; alarms are usually set at 10 % LEL = 5,000 ppm
#   CO2: 5,000 ppm is the common 8-hour occupational exposure limit
ALARM = {'CH4': 5000.0, 'CO2': 5000.0}
WARN = {'CH4': 1000.0, 'CO2': 1500.0}

# Display colours (RGB 0-1) used in CoppeliaSim, the Excel sheet and the plots
COLOR = {'CH4': (0.10, 0.75, 0.25), 'CO2': (0.55, 0.20, 0.85)}


def height_profile(gas, z):
    if gas == 'CH4':
        return 0.55 + 0.45 * min(max(z, 0.0) / 1.2, 1.0)      # buoyant: stronger higher up
    return math.exp(-max(z, 0.0) / 0.5)                         # dense: strongest at the floor


def concentration(gas, x, y, z):
    """True concentration (ppm) of one gas at a point."""
    s = SOURCES[gas]
    dx, dy = x - (s['x'] + s['shift']), y - s['y']
    plume = math.exp(-0.5 * ((dx / s['sig_along']) ** 2 + (dy / s['sig_cross']) ** 2))
    return s['background'] + s['peak'] * plume * height_profile(gas, z)


class GasSensor:
    """A gas sensor with first-order lag, noise, resolution and a measuring range.

    reading(t) follows the true value C with  tau * dR/dt = C - R,  so after a step change
    it reaches 63 % of the new value after tau seconds and 90 % after about 2.3 tau.
    """

    SPECS = {
        #        tau(s) noise(ppm) noise(% of reading) resolution(ppm) range(ppm)
        'CH4': dict(tau=1.5, noise_abs=15.0, noise_rel=0.02, resolution=1.0, lo=0.0, hi=10000.0),
        'CO2': dict(tau=2.5, noise_abs=30.0, noise_rel=0.03, resolution=1.0, lo=400.0, hi=10000.0),
    }

    def __init__(self, gas, seed=0, ideal=False):
        self.gas, self.spec, self.ideal = gas, self.SPECS[gas], ideal
        self.state = None
        self.rng = random.Random(seed)

    def update(self, true_value, dt):
        sp = self.spec
        if self.state is None:
            self.state = true_value
        elif self.ideal:
            self.state = true_value
        else:
            self.state += (true_value - self.state) * (1 - math.exp(-dt / sp['tau']))
        if self.ideal:
            return true_value
        noisy = self.state + self.rng.gauss(0, sp['noise_abs'] + sp['noise_rel'] * self.state)
        noisy = round(noisy / sp['resolution']) * sp['resolution']
        return min(max(noisy, sp['lo']), sp['hi'])


def status(gas, ppm):
    return 'ALARM' if ppm >= ALARM[gas] else 'WARNING' if ppm >= WARN[gas] else 'NORMAL'


def sample_cloud(gas, n, seed=0, z_max=1.6):
    """Random points whose density follows the gas concentration above background (for drawing)."""
    rng = random.Random(seed)
    s = SOURCES[gas]
    top = s['peak']
    pts, half = [], ARENA / 2 - 0.05
    tries = 0
    while len(pts) < n and tries < 200 * n:
        tries += 1
        x, y, z = rng.uniform(-half, half), rng.uniform(-half, half), rng.uniform(0.02, z_max)
        c = concentration(gas, x, y, z) - s['background']
        if rng.random() < c / top:
            pts.append((x, y, z, c))
    return pts

# Installation Guide

This guide sets up everything needed for the experiments in this repository:
**CoppeliaSim 4.10 (Edu)**, **Python 3** with the **ZMQ Remote API client**, the Python libraries
used for analysis and Excel logging, and (optional, for later experiments) **PyBullet**.
It was written and tested on **Ubuntu 26.04 LTS running as a VirtualBox guest on a Windows 11 host**.
The same steps work on a native Ubuntu 22.04 / 24.04 machine; notes for Windows and macOS are at the end.

Time needed: about 30 minutes (most of it is downloading).

---

## 0. What you need

| Item | Minimum | Tested with |
|---|---|---|
| OS | Ubuntu 22.04 or later (64-bit) | Ubuntu 26.04.1 LTS (VirtualBox guest) |
| RAM | 4 GB (8 GB recommended) | 8 GB |
| Free disk | 3 GB | 12 GB |
| Python | 3.10 or later | 3.14.4 |
| Internet | to download about 300 MB | |

## 1. (Only if you use a virtual machine) Prepare VirtualBox

1. Install **VirtualBox** on the host and create an Ubuntu VM (2+ CPUs, 8 GB RAM, 30 GB disk).
2. In **Settings → Display**, set **Graphics Controller = VMSVGA** and tick **Enable 3D Acceleration**.
   CoppeliaSim needs OpenGL.
3. Inside the VM, install the Guest Additions (Devices → Insert Guest Additions CD) and reboot.
4. Optional, for working from another computer: install the SSH server inside the VM

   ```bash
   sudo apt install -y openssh-server
   ```

   and in VirtualBox **Settings → Network → Adapter 1 (NAT) → Port Forwarding** add a rule
   *Host Port 2222 → Guest Port 22*. You can then log in from any machine on the same Wi-Fi with
   `ssh -p 2222 <user>@<windows-host-ip>`.

## 2. Install system packages

Open a terminal in Ubuntu and run:

```bash
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev build-essential git xz-utils \
                    libgl1 libglu1-mesa libxkbcommon-x11-0 libxcb-cursor0 libxcb-xinerama0
```

`build-essential` and `python3-dev` are needed because on very new Python versions PyBullet is
compiled from source during installation.

To open the Excel log written by the experiments, also install a spreadsheet program:

```bash
sudo apt install -y libreoffice-calc
```

## 3. Create a Python virtual environment

Ubuntu does not allow `pip install` into the system Python, so make a private environment:

```bash
python3 -m venv ~/sim-venv
~/sim-venv/bin/pip install --upgrade pip
~/sim-venv/bin/pip install numpy matplotlib pillow openpyxl pyzmq cbor2 coppeliasim-zmqremoteapi-client pybullet
```

> **Note:** if there is no ready-made PyBullet wheel for your Python version, pip builds it.
> This takes 5–10 minutes with no progress output. It is not stuck.

Activate the environment whenever you work on the experiments:

```bash
source ~/sim-venv/bin/activate
```

## 4. Install CoppeliaSim 4.10 (Edu)

CoppeliaSim is distributed as a ready-to-run folder. The Edu version is free for students and teachers.

```bash
cd ~
wget https://downloads.coppeliarobotics.com/V4_10_0_rev0/CoppeliaSim_Edu_V4_10_0_rev0_Ubuntu24_04.tar.xz
tar -xf CoppeliaSim_Edu_V4_10_0_rev0_Ubuntu24_04.tar.xz
mv CoppeliaSim_Edu_V4_10_0_rev0_Ubuntu24_04 ~/CoppeliaSim
rm CoppeliaSim_Edu_V4_10_0_rev0_Ubuntu24_04.tar.xz
echo 'alias coppeliasim="LIBGL_ALWAYS_SOFTWARE=1 ~/CoppeliaSim/coppeliaSim.sh"' >> ~/.bashrc
echo 'export COPPELIASIM_ROOT="$HOME/CoppeliaSim"' >> ~/.bashrc
source ~/.bashrc
```

`LIBGL_ALWAYS_SOFTWARE=1` in the alias makes CoppeliaSim draw with the CPU (Mesa llvmpipe). In a
VirtualBox VM this is required: the virtual 3-D driver crashes CoppeliaSim with
`vmw_ioctl_command error ... Aborted`. On a PC with a real graphics card you may remove it.

Use the `Ubuntu22_04` file instead on Ubuntu 22.04. On Ubuntu 26.04 the 24.04 build works.
Newer versions are listed at <https://www.coppeliarobotics.com/>; if you use one, change the version
in the URL above.

### Tell CoppeliaSim which Python to use

CoppeliaSim runs Python scripts using the interpreter named in its settings file. Point it at the
virtual environment, which has `pyzmq` and `cbor2`:

```bash
mkdir -p ~/.CoppeliaSim
echo "defaultPython = $HOME/sim-venv/bin/python" >> ~/.CoppeliaSim/usrset.txt
```

## 5. Check the installation

### 5.1 PyBullet

```bash
~/sim-venv/bin/python -c "import pybullet as p, pybullet_data; p.connect(p.DIRECT); p.setAdditionalSearchPath(pybullet_data.getDataPath()); p.setGravity(0,0,-9.81); p.loadURDF('plane.urdf'); b=p.loadURDF('r2d2.urdf',[0,0,1]); [p.stepSimulation() for _ in range(240)]; print('PyBullet OK, robot height after 1 s:', round(p.getBasePositionAndOrientation(b)[0][2],3))"
```

Expected: `PyBullet OK, robot height after 1 s: 0.47` (the robot fell and is resting on the floor).

### 5.2 CoppeliaSim and the Python link

1. Start CoppeliaSim **from the Ubuntu desktop** (not from an SSH session):

   ```bash
   coppeliasim
   ```

   A window with an empty scene and a floor opens. The terminal shows
   `ZeroMQ Remote API server starting (rpcPort=23000)`.

   > **Licence / registration dialog:** CoppeliaSim Edu may show a licence or registration
   > window at start-up or during a session. Close it. While it is open, CoppeliaSim does not
   > answer Python scripts, and they simply hang.
2. In a second terminal:

   ```bash
   ~/sim-venv/bin/python -c "from coppeliasim_zmqremoteapi_client import RemoteAPIClient; import time; sim=RemoteAPIClient().require('sim'); print('version', sim.getInt32Param(sim.intparam_program_full_version)); sim.startSimulation(); time.sleep(2); print('sim time', sim.getSimulationTime()); sim.stopSimulation()"
   ```

   Expected: `version 4100000` and a simulation time of a few seconds. The simulation-time counter
   in the CoppeliaSim window moves while it runs.

## 6. Get the experiments

```bash
cd ~
git clone https://github.com/qai-science/robotics-csAIML-2026.git
cd robotics-csAIML-2026
```

Each experiment folder has a `README.md` with the full procedure. Experiment 07 is in
`experiments/exp07-gas-mapping-robot/`.

### 6.1 Five-minute self-test of the whole chain

```bash
cd ~/robotics-csAIML-2026/experiments/exp07-gas-mapping-robot
source ~/sim-venv/bin/activate
python base_station.py --out /tmp/selftest.xlsx &
python gas_explorer.py --duration 10 --fast --truth-out /tmp/selftest_truth.csv
```

You should see the room and the gas clouds appear in CoppeliaSim, the robot drive for 10 s, and
`[base] run finished: 50 readings saved to /tmp/selftest.xlsx`.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| Python script hangs, no error, CoppeliaSim window looks frozen | A licence/registration dialog is open in CoppeliaSim | Close the dialog; the script continues. |
| `qt.qpa.xcb: could not connect to display` | CoppeliaSim started from SSH, no screen | Start it from the Ubuntu desktop. From SSH, use `DISPLAY=:0 coppeliasim` while someone is logged in on the desktop. |
| Python script hangs at `require('sim')`, then `Failed connecting to CoppeliaSim` | CoppeliaSim not open, or started headless with `-h` | Open the CoppeliaSim window normally. In 4.10 the Python link was unreliable in `-h` mode on our VM. |
| `ModuleNotFoundError: No module named 'zmq'` in the CoppeliaSim log | CoppeliaSim uses a Python without `pyzmq`/`cbor2` | Do the `defaultPython` step in section 4. |
| CoppeliaSim closes with `vmw_ioctl_command error` | VirtualBox 3D driver bug | Restart CoppeliaSim. If it repeats, start it with `LIBGL_ALWAYS_SOFTWARE=1 coppeliasim` (slower but stable). |
| `[robot] waiting for base station` / `ConnectionRefusedError` | Base station not started, wrong IP, or firewall | Start `base_station.py` first; with two PCs use `--base-host <IP>` and open TCP port 5055. |
| `OSError: Address already in use` (port 5055) | An old base station is still running | `pkill -f base_station.py`, then start it again. |
| 3-D view updates only a few times per second during a run | Rendering is slow in a VM | Intended: the robot skips frames to stay in real time; data are unaffected. |
| `error: externally-managed-environment` from pip | pip used outside the virtual environment | Use `~/sim-venv/bin/pip`, or `source ~/sim-venv/bin/activate` first. |
| `Cannot load library libvvcl.so (libtheoraenc.so.1)` | Video recorder library missing | Harmless unless you use CoppeliaSim's built-in video recorder. Install `libtheora0` (package name may differ by Ubuntu version) to fix it. |

## Other operating systems

- **Windows 10/11 (native):** install CoppeliaSim with the Windows installer from the website and
  Python 3.12 from python.org. In a terminal run
  `py -m pip install numpy matplotlib pillow pyzmq cbor2 coppeliasim-zmqremoteapi-client pybullet`.
  Set `COPPELIASIM_ROOT` to the install folder (for example `C:\Program Files\CoppeliaRobotics\CoppeliaSimEdu`).
- **macOS (Apple Silicon or Intel):** download the macOS `.zip` from the website and move
  `coppeliaSim.app` to `/Applications`. Use a Python virtual environment as in section 3 and set
  `COPPELIASIM_ROOT=/Applications/coppeliaSim.app/Contents/Resources`.

The experiment scripts only need `COPPELIASIM_ROOT` to find the robot model; everything else is the same.
If a script says it cannot load `pioneer p3dx.ttm`, set `COPPELIASIM_ROOT` to whichever folder contains
`models/robots/mobile/`. Only the Ubuntu route above has been tested for this repository.

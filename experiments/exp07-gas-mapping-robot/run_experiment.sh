#!/usr/bin/env bash
# Experiment 07, all in one command, on the Ubuntu machine itself.
#
#   ./run_experiment.sh                    full 120 s run
#   ./run_experiment.sh --duration 30      any gas_explorer.py option can be added
#
# Steps: start CoppeliaSim (if it is not already open) -> check the Python link ->
# start the base station -> run the robot -> analyse -> list the results.
set -euo pipefail
cd "$(dirname "$0")"

VENV="${VENV:-$HOME/sim-venv}"
CSIM="${COPPELIASIM_ROOT:-$HOME/CoppeliaSim}"
# shellcheck disable=SC1091
source "$VENV/bin/activate"
mkdir -p results

port_open() { ss -ltn | grep -q ':23000'; }

echo "[1/5] CoppeliaSim"
if port_open; then
    echo "      already running"
else
    # Software OpenGL: VirtualBox's 3-D driver crashes CoppeliaSim ("vmw_ioctl_command error").
    # On a PC with a real graphics card you can drop LIBGL_ALWAYS_SOFTWARE=1.
    (cd "$CSIM" && LIBGL_ALWAYS_SOFTWARE=1 nohup ./coppeliaSim.sh > /tmp/coppeliasim.log 2>&1 < /dev/null &)
    for _ in $(seq 1 90); do port_open && break; sleep 1; done
    port_open || { echo "      CoppeliaSim did not start; see /tmp/coppeliasim.log"; exit 1; }
    sleep 5
    echo "      started"
fi

echo "[2/5] checking the Python link to CoppeliaSim"
if ! timeout 20 python -c "from coppeliasim_zmqremoteapi_client import RemoteAPIClient as R; R().require('sim').getSimulationState()" 2> /dev/null; then
    echo "      CoppeliaSim is not answering. Close any dialog (licence/registration) in its window, then run this script again."
    exit 1
fi
echo "      OK"

echo "[3/5] base station (log: results/gas_log.xlsx)"
pkill -f "[b]ase_station.py" 2> /dev/null || true
python -u base_station.py > results/base_station_console.txt 2>&1 &
BASE=$!
sleep 2

echo "[4/5] robot exploring (watch the CoppeliaSim window)"
python -u gas_explorer.py "$@" | tee results/robot_console.txt
wait "$BASE"
tail -1 results/base_station_console.txt

echo "[5/5] analysis"
python analyse.py > /dev/null
echo
echo "Done. Results in $(pwd)/results:"
ls -1 results
echo
echo "Open them with:  xdg-open results/gas_log.xlsx    xdg-open results/fig1_true_gas_field.png"

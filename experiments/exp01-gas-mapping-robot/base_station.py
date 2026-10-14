"""Base station: receives gas readings from the robot in real time and logs them to Excel.

Start this FIRST, then start the robot (gas_explorer.py). The robot connects over
TCP and sends one JSON line per reading. Every reading is added to the workbook
immediately and the file is saved every second, so you can open the Excel file
while the robot is still driving and watch it grow.

Workbook layout (results/gas_log.xlsx):
    Readings   one row per reading: time, position, CH4 ppm, CO2 ppm, alarm status (colour coded)
    Summary    written when the run ends: peaks, means, where the worst readings were, alarm counts
    Charts     concentration against time for both gases

    python base_station.py                       # listen on all interfaces, port 5055
    python base_station.py --port 6000 --out my_run.xlsx
"""
import argparse
import csv
import json
import os
import socket
import time
from datetime import datetime

from openpyxl import Workbook
from openpyxl.chart import LineChart, Reference
from openpyxl.styles import Alignment, Font, PatternFill

from gas_field import ALARM, COLOR, WARN

HERE = os.path.dirname(os.path.abspath(__file__))
HEADERS = ['Reading #', 'Wall clock', 'Sim time (s)', 'X (m)', 'Y (m)', 'Sensor height (m)',
           'CH4 (ppm)', 'CH4 status', 'CO2 (ppm)', 'CO2 status', 'Link delay (ms)']
FILL = {'NORMAL': PatternFill('solid', fgColor='E2F0D9'), 'WARNING': PatternFill('solid', fgColor='FFF2CC'),
        'ALARM': PatternFill('solid', fgColor='F8CBAD')}


def hexcol(rgb):
    return ''.join(f'{int(255 * c):02X}' for c in rgb)


def new_workbook():
    wb = Workbook()
    ws = wb.active
    ws.title = 'Readings'
    ws.append(HEADERS)
    for i, h in enumerate(HEADERS, 1):
        c = ws.cell(row=1, column=i)
        c.font = Font(bold=True, color='FFFFFF')
        c.alignment = Alignment(horizontal='center', wrap_text=True)
        gas = 'CH4' if 'CH4' in h else 'CO2' if 'CO2' in h else None
        c.fill = PatternFill('solid', fgColor=hexcol(COLOR[gas]) if gas else '404040')
        ws.column_dimensions[c.column_letter].width = 14
    ws.column_dimensions['B'].width = 22
    ws.freeze_panes = 'A2'
    return wb, ws


def add_summary(wb, rows, meta):
    ws = wb.create_sheet('Summary')
    ws.append(['Gas mapping run: summary'])
    ws['A1'].font = Font(bold=True, size=14)
    ws.append([])
    for k, v in meta.items():
        ws.append([k, v])
    ws.append([])
    ws.append(['Gas', 'Readings', 'Mean (ppm)', 'Max (ppm)', 'Max at X (m)', 'Max at Y (m)',
               'Warning readings', 'Alarm readings', 'Alarm threshold (ppm)'])
    for c in ws[ws.max_row]:
        c.font = Font(bold=True)
    for gas, col in (('CH4', 6), ('CO2', 8)):
        vals = [r[col] for r in rows]
        imax = max(range(len(rows)), key=lambda i: rows[i][col])
        ws.append([gas, len(vals), round(sum(vals) / len(vals), 1), max(vals), rows[imax][3], rows[imax][4],
                   sum(WARN[gas] <= v < ALARM[gas] for v in vals), sum(v >= ALARM[gas] for v in vals), ALARM[gas]])
        ws.cell(row=ws.max_row, column=1).fill = PatternFill('solid', fgColor=hexcol(COLOR[gas]))
    for col in 'ABCDEFGHI':
        ws.column_dimensions[col].width = 18

    ch = wb.create_sheet('Charts')
    data = wb['Readings']
    n = data.max_row
    for gas, col, anchor in (('CH4', 7, 'A1'), ('CO2', 9, 'A20')):
        c = LineChart()
        c.title = f'{gas} concentration during the run'
        c.y_axis.title = 'ppm'
        c.x_axis.title = 'reading number'
        c.height, c.width = 9, 22
        c.add_data(Reference(data, min_col=col, min_row=1, max_row=n), titles_from_data=True)
        c.series[0].graphicalProperties.line.solidFill = hexcol(COLOR[gas])
        ch.add_chart(c, anchor)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--host', default='0.0.0.0', help='interface to listen on (0.0.0.0 = all)')
    ap.add_argument('--port', type=int, default=5055)
    ap.add_argument('--out', default=os.path.join(HERE, 'results', 'gas_log.xlsx'))
    args = ap.parse_args()
    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)

    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind((args.host, args.port))
    srv.listen(1)
    print(f'[base] listening on {args.host}:{args.port}, logging to {args.out}', flush=True)
    conn, addr = srv.accept()
    print(f'[base] robot connected from {addr[0]}:{addr[1]}', flush=True)

    wb, ws = new_workbook()
    rows, meta, last_save, buf = [], {}, 0.0, b''
    csv_path = os.path.splitext(args.out)[0] + '.csv'
    csv_f = open(csv_path, 'w', newline='')
    csv_w = csv.writer(csv_f)
    csv_w.writerow(HEADERS)
    done = False
    while not done:
        chunk = conn.recv(65536)
        if not chunk:
            break
        buf += chunk
        while b'\n' in buf:
            line, buf = buf.split(b'\n', 1)
            msg = json.loads(line)
            if msg.get('type') == 'hello':
                meta.update({k: v for k, v in msg.items() if k != 'type'})
                print(f'[base] run info: {meta}', flush=True)
                continue
            if msg.get('type') == 'end':
                meta.update({k: v for k, v in msg.items() if k != 'type'})
                done = True
                break
            delay_ms = round(1000 * (time.time() - msg['sent']), 1)
            row = [msg['n'], datetime.fromtimestamp(msg['sent']).strftime('%Y-%m-%d %H:%M:%S.%f')[:-3],
                   msg['t'], msg['x'], msg['y'], msg['z'], msg['CH4'], msg['CH4_status'],
                   msg['CO2'], msg['CO2_status'], delay_ms]
            rows.append(row)
            ws.append(row)
            r = ws.max_row
            ws.cell(row=r, column=8).fill = FILL[msg['CH4_status']]
            ws.cell(row=r, column=10).fill = FILL[msg['CO2_status']]
            csv_w.writerow(row)
            if msg['n'] % 25 == 0 or 'ALARM' in (msg['CH4_status'], msg['CO2_status']) and msg['n'] % 5 == 0:
                print(f"[base] #{msg['n']:4d} t={msg['t']:6.1f}s  ({msg['x']:+.2f},{msg['y']:+.2f})  "
                      f"CH4={msg['CH4']:7.0f} ppm {msg['CH4_status']:7s}  "
                      f"CO2={msg['CO2']:7.0f} ppm {msg['CO2_status']:7s}", flush=True)
        if time.time() - last_save > 1.0:          # live file: save once a second
            wb.save(args.out)
            csv_f.flush()
            last_save = time.time()

    conn.close()
    srv.close()
    csv_f.close()
    if rows:
        add_summary(wb, rows, meta)
    wb.save(args.out)
    print(f'[base] run finished: {len(rows)} readings saved to {args.out} (and {csv_path})', flush=True)


if __name__ == '__main__':
    main()

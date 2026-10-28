# ZYC Simpo 5000 — Home Assistant integration

[![hacs][hacs-badge]][hacs]
[![Validate][validate-badge]][validate]
[![License: MIT][license-badge]](LICENSE)

Local, cloud-free monitoring of a **ZYC Simpo 5000** energy-storage bank over the
WiFi dongle's TCP protocol. Every battery module is read individually and exposed
as its own device, with whole-bank aggregates on top.

- **No cloud** — talks to the dongle directly on your LAN (port 8888).
- **No RS485 conflict** — leaves the battery's RS485 bus free for a Victron
  Cerbo GX (or any other) controller; the dongle uses its own BMS link.
- **Per-module + whole-bank** sensors, auto-discovering the number of modules.

> ⚠️ **Unofficial.** The protocol was reverse-engineered; this project is not
> affiliated with or endorsed by ZYC Energy. Use at your own risk. Read-only —
> the integration never writes to the battery.

## Features

Per module (device *ZYC Module N*):
voltage · current · power · temperature · **state of charge** ·
**state of health** · **cell imbalance** (max−min mV) with cell voltage max/min
and **individual `Cell 1`…`Cell 16` voltages** · remaining & full capacity ·
charge/discharge voltage & current limits · firmware · a **BMS warning** binary
sensor.

Whole bank (device *ZYC Simpo Bank*):
total current & power (summed) · average voltage & temperature · pack **state of
charge** (the value the BMS reports to the inverter) · average & minimum state of
health · **worst cell imbalance** across the bank · total remaining & full
capacity · cumulative **energy charged / discharged** (kWh, for the Energy
dashboard) · a bank-wide BMS warning.

Current uses the **Victron convention**: positive = charging, negative =
discharging.

## Installation

### HACS (custom repository)
1. HACS → ⋮ → **Custom repositories**.
2. Add `https://github.com/formiification/ha-zyc-simpo`, category **Integration**.
3. Install **ZYC Simpo 5000**, then restart Home Assistant.

### Manual
Copy `custom_components/zyc_simpo/` into your HA `config/custom_components/`
folder and restart.

## Setup
**Settings → Devices & services → Add integration → “ZYC Simpo 5000”**, then
enter the dongle's **IP address**. The number of battery modules is detected
automatically. The polling interval (default **60 s**) is configurable under the
integration's **Configure** (options).

## Energy dashboard
Add the bank's `energy charged` / `energy discharged` sensors under
**Settings → Dashboards → Energy → Battery systems**.

## Adding / removing modules
The bank is re-scanned on every startup, so expanding the bank or removing a dead
module is handled without reconfiguring. A removed module's entities go
*unavailable* (not broken) and its leftover device can be deleted from the UI.

## How it works
Reverse-engineered from the ZYC Assist Android app. The dongle runs a framed TCP
server on port 8888 (`F2 03 <addr> <cmd> 00 01 <len>` + CRC16/Modbus), reachable
both on its soft-AP and on your LAN. Each module is addressed 1..N; separate
commands return the realtime block, the pack aggregate, the per-cell voltages,
the serial and the firmware. Field scaling was calibrated against a Victron Cerbo
GX and the ZYC portal.

## Credits
Protocol reverse-engineering and integration by Piotr Suchowski. Built with the
help of Claude Code.

## License
[MIT](LICENSE)

[hacs]: https://github.com/hacs/integration
[hacs-badge]: https://img.shields.io/badge/HACS-Custom-41BDF5.svg
[validate]: https://github.com/formiification/ha-zyc-simpo/actions/workflows/validate.yml
[validate-badge]: https://github.com/formiification/ha-zyc-simpo/actions/workflows/validate.yml/badge.svg
[license-badge]: https://img.shields.io/badge/License-MIT-green.svg

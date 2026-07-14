#!/data/data/com.termux/files/usr/bin/bash
set -euo pipefail
cd /data/data/com.termux/files/home/energy-data-br
python3 -m energy_data_br.sync_orchestrator

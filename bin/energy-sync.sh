#!/data/data/com.termux/files/usr/bin/bash
# Sync diário dos dados de energia
# Agendar via cron ou termux-job-scheduler

cd /data/data/com.termux/files/home/energy-data-br

echo "[$(date)] Iniciando sync..." >> logs/sync.log

# Sync ANEEL (ZIP snapshot) – diff por hash
energy-data-br sync --source aneel >> logs/sync.log 2>&1

# Sync ONS (último dia)
energy-data-br sync --source ons --days 1 >> logs/sync.log 2>&1

echo "[$(date)] Sync concluído." >> logs/sync.log

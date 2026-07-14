#!/data/data/com.termux/files/usr/bin/bash
# Orquestrador com tmux, wake-lock, prioridade e logs

set -euo pipefail

cd /data/data/com.termux/files/home/energy-data-br

# 1. Adquirir wake-lock (evita que o celular durma)
termux-wake-lock

# 2. Remover lock do orquestrador (se existir de execuções anteriores)
rm -f .locks/sync.lock

# 3. Criar/entrar na sessão tmux
tmux new-session -d -s orchestrator
tmux send-keys -t orchestrator "cd /data/data/com.termux/files/home/energy-data-br" C-m
tmux send-keys -t orchestrator "nice -n -10 python3 -m energy_data_br.sync_orchestrator 2>&1 | tee -a logs/sync_orchestrator.log" C-m

echo "🚀 Orquestrador iniciado em tmux (sessão: orchestrator)"
echo "📊 Acompanhe os logs: tail -f ~/energy-data-br/logs/sync_orchestrator.log"
echo "🔗 Conecte-se ao tmux: tmux attach -t orchestrator"

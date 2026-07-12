# Deploy

## Requisitos
- Python 3.9+
- SQLite (embutido)
- Termux (Android) ou Linux

## Instalação
```bash
git clone https://github.com/scoobiii/energy-data-br.git
cd energy-data-br
pip install -e .
```

## Configuração do banco
Banco padrão: /storage/emulated/0/energy-data-br.sqlite
Para mudar: defina --db nos comandos ou ajuste symlink

## Automação (cron)
```bash
crontab -e
# Adicionar:
0 2 * * * /data/data/com.termux/files/home/energy-data-br/bin/energy-sync.sh
```

## Manutenção
- energy-data-br stats - ver contagens
- sqlite3 DB "PRAGMA integrity_check;" - ver integridade
- sqlite3 DB "VACUUM;" - compactar (se houver espaço)

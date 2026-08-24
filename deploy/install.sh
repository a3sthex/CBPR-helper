#!/usr/bin/env bash
# ============================================================
#  CBPR Helper — установщик на Ubuntu Server
#  Ставит сайт как системную службу с автозапуском.
#
#  Запуск (из папки репозитория):
#      bash deploy/install.sh           # порт 8000
#      bash deploy/install.sh 8080      # свой порт
#      bash deploy/install.sh --dry-run # только показать, что сделает
# ============================================================
set -euo pipefail

PORT="${1:-8000}"
DRY_RUN="${DRY_RUN:-0}"
[ "${1:-}" = "--dry-run" ] && { DRY_RUN=1; PORT="${2:-8000}"; }

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$(command -v python3 || true)"
RUN_USER="$(id -un)"
RUN_GROUP="$(id -gn)"

echo "=========================================================="
echo " CBPR Helper :: установка"
echo "=========================================================="
echo " Папка проекта : $REPO_DIR"
echo " Python        : ${PYTHON:-НЕ НАЙДЕН}"
echo " Порт          : $PORT"
echo " Пользователь  : $RUN_USER"
echo

# --- проверки ------------------------------------------------------------
if [ -z "$PYTHON" ]; then
    echo "ОШИБКА: python3 не найден. Установи зависимости и повтори:"
    echo "  sudo apt update && sudo apt install -y python3 git"
    exit 1
fi
if [ ! -f "$REPO_DIR/app/server.py" ]; then
    echo "ОШИБКА: рядом нет папки app/ — запусти скрипт из копии репозитория."
    exit 1
fi

# каталог данных (создаётся при первом запуске сам, но пусть будет)
mkdir -p "$REPO_DIR/app/data" "$REPO_DIR/app/data/backups"

# если каталога предметов нет — собираем из Data Pool.xlsx
if [ ! -f "$REPO_DIR/app/data/items.json" ]; then
    echo "items.json не найден, собираю из Data Pool.xlsx…"
    "$PYTHON" "$REPO_DIR/app/import_data.py"
fi
if [ ! -f "$REPO_DIR/app/data/items.json" ]; then
    echo "ОШИБКА: не удалось получить app/data/items.json"
    exit 1
fi

# --- юнит systemd --------------------------------------------------------
UNIT="$(cat <<EOF
[Unit]
Description=CBPR Helper — онлайн-помощник Cyberpunk RED
After=network.target

[Service]
Type=simple
WorkingDirectory=$REPO_DIR
Environment=CBPR_SECURE_COOKIES=1
Environment=CBPR_REGISTRATION_MODE=invite
ExecStart=$PYTHON $REPO_DIR/app/server.py --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=3
User=$RUN_USER
Group=$RUN_GROUP

[Install]
WantedBy=multi-user.target
EOF
)"

BACKUP_UNIT="$(cat <<EOF
[Unit]
Description=NC//NET daily online campaign backup
After=local-fs.target

[Service]
Type=oneshot
WorkingDirectory=$REPO_DIR
Environment=CBPR_DB_PATH=$REPO_DIR/app/data/cbpr.db
Environment=CBPR_BACKUP_DIR=$REPO_DIR/app/data/backups
Environment=CBPR_BACKUP_RETENTION=14
ExecStart=$PYTHON $REPO_DIR/app/backup.py create --retention 14 --reason scheduled
User=$RUN_USER
Group=$RUN_GROUP
Nice=10
IOSchedulingClass=best-effort
IOSchedulingPriority=7
EOF
)"

BACKUP_TIMER="$(cat <<'EOF'
[Unit]
Description=Run NC//NET campaign backup every day

[Timer]
OnCalendar=*-*-* 04:00:00
RandomizedDelaySec=15m
Persistent=true
Unit=cbpr-backup.service

[Install]
WantedBy=timers.target
EOF
)"

if [ "$DRY_RUN" = "1" ]; then
    echo "---- DRY RUN: /etc/systemd/system/cbpr.service ----"
    echo "$UNIT"
    echo "---- DRY RUN: /etc/systemd/system/cbpr-backup.service ----"
    echo "$BACKUP_UNIT"
    echo "---- DRY RUN: /etc/systemd/system/cbpr-backup.timer ----"
    echo "$BACKUP_TIMER"
    echo "--------------------------------------------------------------------"
    exit 0
fi

SUDO=""
if [ "$(id -u)" -ne 0 ]; then
    if command -v sudo >/dev/null 2>&1; then
        SUDO="sudo"
    else
        echo "Нет прав root и нет sudo — приложение можно запустить вручную:"
        echo "  $PYTHON app/server.py --port $PORT"
        echo
        echo "Или сохрани этот файл как /etc/systemd/system/cbpr.service и выполни:"
        echo "  systemctl daemon-reload && systemctl enable --now cbpr"
        echo
        echo "$UNIT"
        exit 0
    fi
fi

if [ ! -d /run/systemd/system ]; then
    echo "systemd в этой системе не запущен (обычно так в контейнерах)."
    echo "Запусти приложение вручную:"
    echo "  $PYTHON app/server.py --port $PORT"
    exit 0
fi

echo "Создаю службы cbpr.service и ежедневного backup…"
printf '%s\n' "$UNIT" | $SUDO tee /etc/systemd/system/cbpr.service >/dev/null
printf '%s\n' "$BACKUP_UNIT" | $SUDO tee /etc/systemd/system/cbpr-backup.service >/dev/null
printf '%s\n' "$BACKUP_TIMER" | $SUDO tee /etc/systemd/system/cbpr-backup.timer >/dev/null
$SUDO systemctl daemon-reload
$SUDO systemctl enable cbpr.service >/dev/null
$SUDO systemctl enable --now cbpr-backup.timer >/dev/null
$SUDO systemctl restart cbpr.service
sleep 2

echo
echo "=========================================================="
echo " ГОТОВО! Состояние службы:"
echo "=========================================================="
$SUDO systemctl --no-pager --lines=3 status cbpr.service || true

echo
echo " Backend слушает только локально: http://127.0.0.1:$PORT"
echo " Secure session cookies включены. Для доступа нужен HTTPS reverse proxy."
echo " Настрой домен и deploy/nginx-cbpr.conf; не открывай порт $PORT наружу."
echo " Логи в реальном времени:    journalctl -u cbpr -f"
echo " Перезапуск:                 $SUDO systemctl restart cbpr"
echo " Остановка:                  $SUDO systemctl stop cbpr"
echo " Backup timer:               $SUDO systemctl status cbpr-backup.timer"
echo " Backup сейчас:              $SUDO systemctl start cbpr-backup.service"
echo " Проверка копий:             $PYTHON app/backup.py list"

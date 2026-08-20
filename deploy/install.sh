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
mkdir -p "$REPO_DIR/app/data"

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
ExecStart=$PYTHON $REPO_DIR/app/server.py --host 127.0.0.1 --port $PORT
Restart=always
RestartSec=3
User=$RUN_USER
Group=$RUN_GROUP

[Install]
WantedBy=multi-user.target
EOF
)"

if [ "$DRY_RUN" = "1" ]; then
    echo "---- DRY RUN: будет создан файл /etc/systemd/system/cbpr.service ----"
    echo "$UNIT"
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

echo "Создаю службу cbpr.service…"
printf '%s\n' "$UNIT" | $SUDO tee /etc/systemd/system/cbpr.service >/dev/null
$SUDO systemctl daemon-reload
$SUDO systemctl enable cbpr.service >/dev/null
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

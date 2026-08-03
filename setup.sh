#!/usr/bin/env bash
# Everything needed to start, in one run. Safe to run again: each step checks
# whether it is already done and skips if so.
set -u

HERE="$(cd "$(dirname "$0")" && pwd)"

say()  { printf "\n\033[1m%s\033[0m\n" "$1"; }
ok()   { printf "  \033[32m✓\033[0m %s\n" "$1"; }
warn() { printf "  \033[33m!\033[0m %s\n" "$1"; }
die()  { printf "  \033[31m×\033[0m %s\n" "$1"; exit 1; }

# Where an existing install was built from, empty if there is none. uv keeps
# one tool per package name, so a second setup does not create a second aimc —
# it silently repoints the one that exists. Saying so beats surprising someone
# whose edits stop taking effect.
current_source() {
  local receipt="$HOME/.local/share/uv/tools/ai-music-curator/uv-receipt.toml"
  [ -f "$receipt" ] || return 0
  sed -n 's/.*directory = "\([^"]*\)".*/\1/p' "$receipt" | head -1
}

say "1/3  Перевіряю uv"
if command -v uv >/dev/null 2>&1; then
  ok "uv уже стоїть"
else
  warn "uv немає, ставлю"
  curl -LsSf https://astral.sh/uv/install.sh | sh || die "не вдалося поставити uv"
  export PATH="$HOME/.local/bin:$PATH"
  command -v uv >/dev/null 2>&1 || die "uv поставився, але не знайшовся у PATH"
  ok "uv поставлено"
fi

say "2/3  Ставлю aimc"
EXISTING="$(current_source)"
if [ -n "$EXISTING" ] && [ "$EXISTING" != "$HERE" ]; then
  warn "aimc уже стоїть і зібраний з іншої теки:"
  printf "      %s\n" "$EXISTING"
  printf "      Друга копія НЕ з'явиться — команда aimc одна на систему.\n"
  printf "      Але вона перемкнеться на цю теку:\n"
  printf "      %s\n\n" "$HERE"
  printf "  Перемкнути? [y/N] "
  # Read from the terminal when there is one; when the script is piped or run
  # unattended there is no answer to be had, and the safe answer is "no".
  if [ -r /dev/tty ]; then read -r ans </dev/tty || ans="n"; else ans="n"; fi
  case "$ans" in
    [yY]*) ;;
    *) ok "лишаю як було — нічого не змінено"; printf "\n"; exit 0 ;;
  esac
elif [ -n "$EXISTING" ]; then
  ok "aimc уже стоїть саме з цієї теки — переставляю на свіжу версію"
fi

uv tool install --force --no-cache "$HERE" >/dev/null 2>&1 || die "не вдалося поставити aimc"
command -v aimc >/dev/null 2>&1 || export PATH="$HOME/.local/bin:$PATH"
command -v aimc >/dev/null 2>&1 || die "aimc поставився, але не знайшовся у PATH"
ok "команда aimc готова"

say "3/3  Вхід в Apple Music"
if applemusic-mcp status 2>/dev/null | grep -q "User token: present"; then
  ok "вхід уже зроблено"
else
  warn "зараз відкриється браузер — увійди в Apple Music своїм Apple ID"
  applemusic-mcp login --chrome || die "вхід не завершено"
  ok "вхід зроблено, діє близько 180 днів"
fi

printf "\n\033[1mГотово.\033[0m Відкрий Claude Code у цій теці й просто скажи,\n"
printf "що зробити з музикою. Наприклад: «покажи мої плейлісти».\n\n"
printf "Оновитися пізніше:  aimc update\n"
printf "Якщо любиш термінал: aimc --help\n\n"

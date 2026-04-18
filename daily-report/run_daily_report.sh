#!/bin/bash
# Daily investment report runner
# Runs via cron at 7:00 AM every day: 0 7 * * * /Users/chenpu/project/portfolio-mcp/daily-report/run_daily_report.sh

set -euo pipefail

SCRIPT_DIR="/Users/chenpu/project/portfolio-mcp/daily-report"
ENV_FILE="$SCRIPT_DIR/.env"

if [ -f "$ENV_FILE" ]; then
  set -a
  source "$ENV_FILE"
  set +a
fi

export PORTFOLIO_CSV_PATH="${PORTFOLIO_CSV_PATH:?PORTFOLIO_CSV_PATH is required}"
: "${TELEGRAM_BOT_TOKEN:?TELEGRAM_BOT_TOKEN is required}"
: "${TELEGRAM_CHAT_ID:?TELEGRAM_CHAT_ID is required}"
: "${GOOGLE_API_KEY:?GOOGLE_API_KEY is required}"
: "${TAVILY_API_KEY:?TAVILY_API_KEY is required}"

mkdir -p "$SCRIPT_DIR/logs"

cd "$SCRIPT_DIR"

echo "=== $(date '+%Y-%m-%d %H:%M:%S') START ===" >> "$SCRIPT_DIR/logs/daily_report.log"
/opt/homebrew/bin/uv run python "$SCRIPT_DIR/daily_report_pipeline.py" >> "$SCRIPT_DIR/logs/daily_report.log" 2>&1
echo "=== $(date '+%Y-%m-%d %H:%M:%S') END ===" >> "$SCRIPT_DIR/logs/daily_report.log"

#!/usr/bin/env bash
echo "============================"
echo " 傅瑞科技 · 企业 AI 操作系统"
echo "============================"
cd "$(dirname "$0")/backend"
[[ -d venv ]] && source venv/bin/activate
# Backend MUST go through start_backend_pg.py: it pins DATABASE_URL to the
# PostgreSQL production DB (furui_aios). Plain "uvicorn app.main:app" falls
# back to SQLite app.db, which is a different dataset (stale demo data).
( python start_backend_pg.py ) &
sleep 3
cd ../frontend
# Frontend uses :3001 because :3000 is held by an unrelated Express app.
( npm run dev -- -p 3001 ) &
sleep 8
open http://localhost:3001 || xdg-open http://localhost:3001 || true
wait

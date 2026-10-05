@echo off
echo Starting Furui AIOS backend and frontend...
rem Backend MUST go through start_backend_pg.py: it pins DATABASE_URL to the
rem PostgreSQL production DB (furui_aios). Plain "uvicorn app.main:app" falls
rem back to SQLite app.db, which is a different dataset (stale demo data).
start "backend" cmd /k "cd /d %~dp0backend && venv\Scripts\python.exe start_backend_pg.py"
timeout /t 4 /nobreak > nul
rem Frontend uses :3001 because :3000 is held by an unrelated Express app.
start "frontend" cmd /k "cd /d %~dp0frontend && npm.cmd run dev -- -p 3001"
echo Waiting for the frontend at http://localhost:3001...
timeout /t 6 /nobreak > nul
start "" http://localhost:3001

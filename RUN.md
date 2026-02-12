# How to Run Backend and React UI

The app uses a **FastAPI backend** and a **React (Vite) frontend**. Streamlit has been removed; the UI is the React app only.

---

## Prerequisites

- **Python 3.10+** with dependencies: `pip install -r requirements.txt`
- **Node.js 18+** and npm (for the React frontend)
- **PostgreSQL** running; `.env` in project root with `DATABASE_URL` and Azure OpenAI vars (see backend/.env.example or README)
- **Migrations applied:** `python run_migrations.py` (from project root)

---

## Option 1: Start both (recommended)

From **project root** in PowerShell:

```powershell
.\start_all.ps1
```

This opens two windows:

1. **Backend** – FastAPI on http://localhost:8000  
2. **Frontend** – React (Vite) on http://localhost:5173  

Then open **http://localhost:5173** in your browser.

---

## Option 2: Start backend and frontend separately

### Terminal 1 – Backend

From **project root**:

```powershell
.\start_backend.ps1
```

- Backend runs at **http://localhost:8000**
- API docs: **http://localhost:8000/docs**

### Terminal 2 – Frontend

From **project root** (in a new terminal):

```powershell
.\start_frontend.ps1
```

- First time: installs npm dependencies in `frontend/`
- UI runs at **http://localhost:5173**

Open **http://localhost:5173** in your browser. The React app proxies `/synthetic`, `/ui`, and `/api` to the backend.

---

## Option 3: Manual commands

### Backend

```powershell
cd backend
python -c "from db import init_db; init_db()"
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Then open http://localhost:5173.

---

## Summary

| What        | URL                     |
|------------|-------------------------|
| React UI   | http://localhost:5173   |
| Backend API| http://localhost:8000   |
| API docs   | http://localhost:8000/docs |

The React UI has two tabs: **Synthetic Data Agent** and **UI Automation Agent**. Both talk to the backend via the proxy configured in `frontend/vite.config.ts`.

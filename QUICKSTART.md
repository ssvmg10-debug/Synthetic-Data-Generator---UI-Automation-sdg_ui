# QUICK START COMMANDS

## Initial Setup (Run Once)

# 1. Navigate to project
cd "C:\Users\gparavasthu\Workspace\Gen AI QE\Synthetic Data Generator & UI Automation"

# 2. Activate virtual environment
C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\Activate.ps1

# 3. Install dependencies
pip install -r requirements.txt

# 4. Initialize database
cd backend
python init_db.py
cd ..

# 5. (Optional) Install Playwright
npm install @playwright/test
npx playwright install

## Daily Usage

### Start Backend (Terminal 1)
C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\Activate.ps1
cd backend
python main.py

### Start Frontend (Terminal 2)
C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\Activate.ps1
streamlit run streamlit_ui/Home.py

## OR Use Scripts

### Using PowerShell Scripts
# Terminal 1
.\start_backend.ps1

# Terminal 2
.\start_streamlit.ps1

## Access Points
- Backend API: http://localhost:8000
- API Docs: http://localhost:8000/docs
- Frontend UI: http://localhost:8501

## Quick Test

# Test backend health
curl http://localhost:8000/health

# Expected: {"status":"healthy"}

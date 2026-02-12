# INSTALLATION GUIDE
# Enterprise Test Automation Platform

## Prerequisites

- Python 3.9 or higher
- Node.js 16+ (for Playwright)
- Windows PowerShell
- Virtual environment already set up at specified path

## Step-by-Step Installation

### 1. Navigate to Project Directory

```powershell
cd "C:\Users\gparavasthu\Workspace\Gen AI QE\Synthetic Data Generator & UI Automation"
```

### 2. Activate Virtual Environment

```powershell
C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\Activate.ps1
```

### 3. Install Python Dependencies

```powershell
pip install -r requirements.txt
```

Expected output:
```
Successfully installed fastapi-0.109.0 uvicorn-0.27.0 ...
```

### 4. Initialize Database

```powershell
cd backend
python init_db.py
cd ..
```

Expected output:
```
Initializing database...
✅ Database initialized successfully!
📁 Database file: enterprise_automation.db
```

### 5. (Optional) Install Playwright

If you want UI automation to work:

```powershell
npm install @playwright/test
npx playwright install
```

### 6. Verify Installation

Check that backend starts:

```powershell
cd backend
python -c "import fastapi; print('FastAPI:', fastapi.__version__)"
python -c "from main import app; print('✅ Backend imports successful')"
cd ..
```

Check Streamlit:

```powershell
python -c "import streamlit; print('Streamlit:', streamlit.__version__)"
```

## Running the Application

### Option A: Using Scripts (Recommended)

**Terminal 1 - Backend:**
```powershell
.\start_backend.ps1
```

**Terminal 2 - Frontend:**
```powershell
.\start_streamlit.ps1
```

### Option B: Manual Start

**Terminal 1 - Backend:**
```powershell
C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\Activate.ps1
cd backend
python main.py
```

**Terminal 2 - Frontend:**
```powershell
C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\Activate.ps1
streamlit run streamlit_ui/Home.py
```

## Accessing the Application

- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (Swagger UI)
- **Frontend UI**: http://localhost:8501

## Troubleshooting

### Issue: Module not found errors

**Solution:**
```powershell
# Make sure virtual environment is activated
C:\Users\gparavasthu\Workspace\Truvelocity\code_export\agentic-sdlc-platform\venv\Scripts\Activate.ps1

# Reinstall dependencies
pip install -r requirements.txt
```

### Issue: Database errors

**Solution:**
```powershell
# Delete and reinitialize database
Remove-Item backend\enterprise_automation.db -ErrorAction SilentlyContinue
cd backend
python init_db.py
cd ..
```

### Issue: Port already in use

**Solution:**
```powershell
# For port 8000 (Backend)
netstat -ano | findstr :8000
# Kill the process using the PID shown

# For port 8501 (Streamlit)
netstat -ano | findstr :8501
# Kill the process using the PID shown
```

### Issue: Playwright not working

**Solution:**
```powershell
# Install Playwright
npm install @playwright/test
npx playwright install

# Test Playwright
npx playwright --version
```

## Testing the Installation

### 1. Test Backend API

Open browser to: http://localhost:8000/docs

Try the `/health` endpoint - should return:
```json
{"status": "healthy"}
```

### 2. Test Synthetic Data Generation

In Streamlit UI:
1. Go to "Synthetic Data" page
2. Choose "Field Structure" tab
3. Define 2-3 fields
4. Click "Extract from Structure"
5. Go to "Generate Data" tab
6. Click "Generate Synthetic Data"

Should see a table with generated data.

### 3. Test UI Automation (Basic)

In Streamlit UI:
1. Go to "UI Automation" page
2. Enter a simple test case:
   ```
   Test Example
   1. Navigate to https://example.com
   2. Verify page loads
   ```
3. Click "Run UI Test"

Note: Full Playwright execution requires Playwright installation.

### 4. Test API Automation

In Streamlit UI:
1. Go to "API Automation" page
2. Click one of the example test cases (e.g., "GET Request")
3. Click "Run API Test"

Should see API response and validation results.

## Directory Structure Verification

After installation, verify these directories exist:

```
✓ backend/
  ✓ routers/
  ✓ services/
  ✓ models/
  ✓ test_outputs/
  ✓ enterprise_automation.db
✓ streamlit_ui/
  ✓ pages/
  ✓ services/
✓ requirements.txt
✓ README.md
```

## Next Steps

1. ✅ Read [README.md](README.md) for feature documentation
2. ✅ Explore the Streamlit UI at http://localhost:8501
3. ✅ Check API documentation at http://localhost:8000/docs
4. ✅ Try example test cases provided in the UI
5. ✅ Create your own test cases

## Support

If you encounter issues:
1. Check the console output for error messages
2. Verify all dependencies are installed
3. Ensure virtual environment is activated
4. Check that ports 8000 and 8501 are available

## Production Deployment Considerations

For production use, consider:
- Switch to PostgreSQL database
- Add authentication (OAuth2/JWT)
- Enable HTTPS
- Use production WSGI server (Gunicorn)
- Set up proper logging
- Configure environment variables
- Add monitoring and alerting

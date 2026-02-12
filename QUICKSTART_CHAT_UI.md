# 🚀 Quick Start Guide

## Start the Application

### Step 1: Start All Services
```powershell
.\start_all.ps1
```

This opens 2 windows:
- **Window 1**: Backend (FastAPI on port 8000)
- **Window 2**: Frontend (Streamlit on port 8501)

### Step 2: Open Browser
The browser will automatically open to: **http://localhost:8501**

If not, manually open: http://localhost:8501

## 🧬 Test Synthetic Data Generation

1. Click **"Open Data Generator"** on the home page
2. In the chat box at the bottom, type:
   ```
   Generate 50 user profiles with email, name, age, and address
   ```
3. Press Enter
4. Watch:
   - Chat shows "Processing..."
   - Backend terminal shows logs
   - Data appears in right panel
5. Download the data (JSON/CSV buttons)

**More Examples:**
```
Generate 100 transactions with amount, date, and status
Create 25 employees with id, name, salary, and department
Generate 500 customer records with email, phone, and address
```

## 🎭 Test UI Automation

1. Click **"Open UI Automation"** on the home page
2. In the chat box, type:
   ```
   Simple Test
   1. Navigate to https://www.google.com
   2. Type "Playwright" in search box
   3. Press Enter
   4. Wait 2 seconds
   5. Verify results are displayed
   ```
3. Press Enter
4. Watch:
   - Chat shows "Processing..."
   - Backend terminal shows agent logs
   - **Browser window opens and executes test**
   - Results appear in right panel

**More Examples:**
```
Login Test
1. Navigate to https://example.com/login
2. Type "user@test.com" in email field
3. Type "password" in password field
4. Click login button
5. Verify dashboard appears
```

## 📋 Check Backend Logs

Look at the **backend terminal window** - you should see:

```
="=80
🚀 Enterprise Test Automation Platform - Starting Up
="=80
📍 Server running at: http://localhost:8000
="=80

INFO: 🧬 Synthetic Data: Processing natural language request...
INFO: 📋 Parsed schema: 4 fields, 50 rows
INFO: ✅ Generated 50 rows
INFO: ✅ Complete! Run ID: 1
```

## ✅ Verify Everything Works

Run the automated test:
```powershell
python test_e2e_chat_ui.py
```

This tests:
- Backend connectivity
- Synthetic data generation
- UI automation execution

## 🐛 If Something Goes Wrong

### Backend Not Running
```powershell
# In Terminal 1
.\start_backend.ps1
```

### Frontend Not Running
```powershell
# In Terminal 2
.\start_streamlit.ps1
```

### No Logs Showing
- Make sure you're looking at the **backend terminal** (not Streamlit)
- Logs appear when you make requests from the UI

### UI Test Not Working
1. Check backend is running: http://localhost:8000/health
2. Check Playwright is installed: `python -m playwright install`
3. Look for errors in backend logs

## 🎯 Key Points

✅ **Everything runs in backend** - All AI processing happens in FastAPI
✅ **Logs show in backend terminal** - Watch the uvicorn window
✅ **Chat interface for both features** - No complex forms
✅ **Natural language input** - Describe what you want
✅ **Results shown in UI** - See data/test results immediately

## 📚 Full Documentation

See [CHAT_UI_IMPLEMENTATION.md](CHAT_UI_IMPLEMENTATION.md) for complete details.

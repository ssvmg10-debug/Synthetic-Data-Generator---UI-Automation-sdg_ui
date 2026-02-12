# TESTING GUIDE
# How to Test Each Component

## 🧪 Test Plan Overview

This guide provides step-by-step instructions to test all components of the Enterprise Test Automation Platform.

## Prerequisites

- Backend running on http://localhost:8000
- Frontend running on http://localhost:8501
- Database initialized

## 1️⃣ Backend API Testing

### Test 1.1: Health Check
```powershell
# Using curl
curl http://localhost:8000/health

# Expected output:
# {"status":"healthy"}
```

### Test 1.2: Explore API Documentation
1. Open browser: http://localhost:8000/docs
2. Verify Swagger UI loads
3. Verify three tag sections:
   - Synthetic Data
   - UI Automation
   - API Automation

### Test 1.3: Test Synthetic Data Endpoints

**Via Swagger UI:**
1. Go to http://localhost:8000/docs
2. Expand `POST /synthetic/ui-schema`
3. Click "Try it out"
4. Use this payload:
```json
{
  "fields_structure": {
    "username": {"type": "string", "required": true},
    "email": {"type": "string", "required": true},
    "age": {"type": "integer", "required": false}
  }
}
```
5. Click "Execute"
6. Verify 200 response with schema_id

**Via curl:**
```powershell
curl -X POST "http://localhost:8000/synthetic/ui-schema" `
  -H "Content-Type: application/json" `
  -d '{\"fields_structure\": {\"name\": {\"type\": \"string\"}}}'
```

## 2️⃣ Synthetic Data Module Testing

### Test 2.1: Extract UI Schema from Structure

**Steps:**
1. Open http://localhost:8501
2. Navigate to "Synthetic Data" page
3. Select "Field Structure" tab
4. Set "Number of Fields" to 3
5. Define fields:
   - Field 1: name, string, required
   - Field 2: email, string, required
   - Field 3: age, integer, not required
6. Click "Extract from Structure"

**Expected Result:**
- ✅ Success message with schema_id
- ✅ JSON schema displayed
- ✅ Schema stored in database

### Test 2.2: Generate Synthetic Data

**Steps:**
1. After extracting schema (Test 2.1)
2. Go to "Generate Data" tab
3. Select "Use Schema ID"
4. Use the schema_id from previous test
5. Set "Number of Rows" to 10
6. Select model: "GaussianCopula"
7. Click "Generate Synthetic Data"

**Expected Result:**
- ✅ Success message with run_id
- ✅ Table with 10 rows of data
- ✅ Data matches schema (name, email, age)
- ✅ Download CSV button appears
- ✅ Data is realistic (uses Faker)

### Test 2.3: Extract API Schema

**Steps:**
1. Go to "Extract API Schema" tab
2. Enter endpoint: `/users`
3. Select "Sample Response"
4. Paste this JSON:
```json
{
  "id": 1,
  "name": "John Doe",
  "email": "john@example.com",
  "active": true
}
```
5. Click "Extract from Response"

**Expected Result:**
- ✅ Schema extracted with correct types
- ✅ Schema_id assigned

### Test 2.4: Merge Schemas

**Steps:**
1. Go to "Merge Schemas" tab
2. Enter UI Schema ID from Test 2.1
3. Enter API Schema ID from Test 2.3
4. Click "Merge Schemas"

**Expected Result:**
- ✅ Unified schema created
- ✅ Statistics showing:
  - UI only fields
  - API only fields
  - Common fields

## 3️⃣ UI Automation Module Testing

### Test 3.1: Simple UI Test (Without Playwright)

**Steps:**
1. Navigate to "UI Automation" page
2. Enter this test case:
```
Simple Navigation Test
1. Navigate to https://example.com
2. Verify page loads
```
3. Uncheck "Use Synthetic Data"
4. Click "Run UI Test"

**Expected Result:**
- ✅ Test planned successfully
- ✅ Structured plan generated
- ✅ Validation results shown
- ✅ Script generated (may not execute without Playwright)

### Test 3.2: UI Test with Synthetic Data

**Steps:**
1. First generate synthetic data (Test 2.2)
2. Note the run_id
3. Go to UI Automation page
4. Enter this test case:
```
Login Form Test
1. Navigate to https://example.com/login
2. Type username in username field
3. Type password in password field
4. Click login button
```
5. Check "Use Synthetic Data"
6. Enter the run_id from step 2
7. Click "Run UI Test"

**Expected Result:**
- ✅ Synthetic data loaded
- ✅ Test plan includes data fields
- ✅ Script generated with synthetic values

### Test 3.3: View Locator Registry

**Steps:**
1. Click "View Locator Registry" button
2. Examine stored locators

**Expected Result:**
- ✅ Registry panel opens
- ✅ Shows primary locators
- ✅ Shows healed locators (if any)

### Test 3.4: View Previous Results

**Steps:**
1. Enter execution_id from previous test
2. Click "Fetch Results"

**Expected Result:**
- ✅ Test details displayed
- ✅ Status shown
- ✅ Test plan JSON visible

## 4️⃣ API Automation Module Testing

### Test 4.1: Simple GET Request

**Steps:**
1. Navigate to "API Automation" page
2. Click "GET Request" example button
3. Click "Run API Test"

**Expected Result:**
- ✅ Test planned
- ✅ Request sent to JSONPlaceholder API
- ✅ Response received (200 OK)
- ✅ Response JSON displayed
- ✅ Validation results shown

### Test 4.2: POST Request with Custom Data

**Steps:**
1. Enter this test case:
```
Create User API Test
POST https://jsonplaceholder.typicode.com/posts
Payload: title="My Test Post", body="Test content", userId=1
Expected status: 201
```
2. Click "Run API Test"

**Expected Result:**
- ✅ Request planned correctly
- ✅ POST request executed
- ✅ Response status 201
- ✅ Response includes created resource

### Test 4.3: API Test with Synthetic Data

**Steps:**
1. Generate synthetic data with fields: title, body, userId
2. Note the run_id
3. In API Automation page, enter:
```
Create Multiple Posts
POST https://jsonplaceholder.typicode.com/posts
Use synthetic data for payload
```
4. Check "Use Synthetic Data for Request Payload"
5. Enter run_id
6. Click "Run API Test"

**Expected Result:**
- ✅ Synthetic data loaded into payload
- ✅ Request executed with synthetic values
- ✅ Response validated

### Test 4.4: View Schema Cache

**Steps:**
1. Click "View Schema Cache" button

**Expected Result:**
- ✅ Cached schemas displayed
- ✅ Shows endpoint and version
- ✅ Schema JSON visible

## 5️⃣ Integration Testing

### Test 5.1: End-to-End Workflow (Synthetic → UI)

**Complete Workflow:**
1. **Generate Data:**
   - Go to Synthetic Data page
   - Create schema with: username, password, email
   - Generate 5 rows
   - Note run_id

2. **Run UI Test:**
   - Go to UI Automation
   - Enter login test case
   - Enable synthetic data
   - Use run_id from step 1
   - Execute test

3. **Verify:**
   - Test uses synthetic data
   - Multiple iterations possible
   - Results stored in database

### Test 5.2: End-to-End Workflow (Synthetic → API)

**Complete Workflow:**
1. **Generate Data:**
   - Create schema with: title, body, userId
   - Generate 3 rows
   - Note run_id

2. **Run API Test:**
   - Go to API Automation
   - Enter POST test case
   - Enable synthetic data
   - Use run_id
   - Execute test

3. **Verify:**
   - Payload contains synthetic data
   - API request successful
   - Response validated

## 6️⃣ Database Testing

### Test 6.1: Verify Data Persistence

**Steps:**
1. Run several tests (synthetic data, UI, API)
2. Stop backend and frontend
3. Restart both services
4. In Streamlit, try to fetch previous results

**Expected Result:**
- ✅ All data persists across restarts
- ✅ Previous runs accessible
- ✅ Database not corrupted

### Test 6.2: Check Database Contents

**Steps:**
```powershell
# Install SQLite browser or use command line
sqlite3 backend/enterprise_automation.db

# Check tables
.tables

# Query data
SELECT * FROM schemas;
SELECT * FROM synthetic_runs;
SELECT * FROM ui_testcases;
SELECT * FROM api_testcases;

.exit
```

**Expected Result:**
- ✅ All 9 tables exist
- ✅ Data from tests is stored
- ✅ Foreign key relationships intact

## 7️⃣ Error Handling Testing

### Test 7.1: Invalid Schema

**Steps:**
1. Try to generate data with schema_id = 999999
2. Observe error handling

**Expected Result:**
- ✅ Error message displayed
- ✅ No crash
- ✅ User-friendly message

### Test 7.2: Invalid API Endpoint

**Steps:**
1. Run API test with invalid URL
2. Observe error handling

**Expected Result:**
- ✅ Error caught and displayed
- ✅ Timeout handled gracefully

### Test 7.3: Malformed Input

**Steps:**
1. Enter invalid JSON in API schema extraction
2. Observe validation

**Expected Result:**
- ✅ JSON parse error shown
- ✅ Helpful error message

## 8️⃣ Performance Testing

### Test 8.1: Large Synthetic Data Generation

**Steps:**
1. Create schema with 10 fields
2. Generate 1000 rows
3. Measure time

**Expected Result:**
- ✅ Completes in < 30 seconds
- ✅ Data table displays (may be scrollable)
- ✅ CSV download works

### Test 8.2: Multiple Concurrent Requests

**Steps:**
1. Open 2-3 browser tabs
2. Run different tests simultaneously

**Expected Result:**
- ✅ All requests handled
- ✅ No conflicts
- ✅ Results independent

## 9️⃣ UI/UX Testing

### Test 9.1: Navigation

**Steps:**
1. Test all navigation buttons
2. Use browser back/forward
3. Test page transitions

**Expected Result:**
- ✅ Smooth navigation
- ✅ No broken links
- ✅ State preserved

### Test 9.2: Responsive Design

**Steps:**
1. Resize browser window
2. Test on different screen sizes

**Expected Result:**
- ✅ Layout adapts
- ✅ No horizontal scroll
- ✅ Buttons accessible

## 🔟 Cleanup and Reset

### Test 10.1: Database Reset

**Steps:**
```powershell
# Stop services
# Delete database
Remove-Item backend\enterprise_automation.db

# Reinitialize
cd backend
python init_db.py
cd ..

# Restart services
```

**Expected Result:**
- ✅ Fresh database created
- ✅ All tables exist
- ✅ No data from previous tests

## ✅ Test Checklist

### Backend
- [ ] Health check works
- [ ] API docs accessible
- [ ] All endpoints respond
- [ ] CORS configured

### Synthetic Data
- [ ] UI schema extraction works
- [ ] API schema extraction works
- [ ] Schema merging works
- [ ] Data generation works
- [ ] CSV download works

### UI Automation
- [ ] Test planning works
- [ ] Script generation works
- [ ] Validation works
- [ ] Synthetic data integration works
- [ ] Locator registry accessible

### API Automation
- [ ] Test planning works
- [ ] Request generation works
- [ ] Execution works
- [ ] Validation works
- [ ] Synthetic data integration works
- [ ] Schema cache works

### Database
- [ ] Data persists
- [ ] All tables created
- [ ] Relationships work
- [ ] No corruption

### Error Handling
- [ ] Invalid inputs handled
- [ ] Network errors handled
- [ ] User-friendly messages

### Performance
- [ ] Large datasets handled
- [ ] Concurrent requests work
- [ ] Response times acceptable

## 📊 Test Report Template

```
Test Date: _____________
Tester: _____________

Component: _____________
Test Case: _____________
Status: ✅ Pass / ❌ Fail
Notes: _____________

Issues Found:
1. _____________
2. _____________

Improvements Suggested:
1. _____________
2. _____________
```

## 🆘 Troubleshooting During Testing

### Issue: Backend not starting
**Solution**: Check if port 8000 is free, verify virtual env activated

### Issue: Streamlit not loading
**Solution**: Check if port 8501 is free, verify backend is running

### Issue: Database errors
**Solution**: Delete and reinitialize database

### Issue: Playwright errors
**Solution**: Install Playwright: `npx playwright install`

## 🎯 Test Success Criteria

All tests should:
- ✅ Complete without crashes
- ✅ Return expected results
- ✅ Handle errors gracefully
- ✅ Persist data correctly
- ✅ Display results clearly

## Next Steps After Testing

1. Document any bugs found
2. Test edge cases
3. Perform load testing
4. Test with real-world data
5. Get user feedback

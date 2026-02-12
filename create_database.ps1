# PowerShell script to create PostgreSQL database

Write-Host "=== Creating PostgreSQL Database ===" -ForegroundColor Cyan
Write-Host ""

# Load environment variables
if (Test-Path ".env") {
    Get-Content .env | ForEach-Object {
        if ($_ -match "^([^=]+)=(.*)$") {
            $name = $matches[1].Trim()
            $value = $matches[2].Trim()
            if (-not [string]::IsNullOrWhiteSpace($name) -and -not $name.StartsWith("#")) {
                [Environment]::SetEnvironmentVariable($name, $value, "Process")
            }
        }
    }
    Write-Host "✅ Environment variables loaded" -ForegroundColor Green
} else {
    Write-Host "❌ .env file not found!" -ForegroundColor Red
    exit 1
}

# Parse DATABASE_URL to extract components
$DATABASE_URL = $env:DATABASE_URL
if (-not $DATABASE_URL) {
    Write-Host "❌ DATABASE_URL not found in .env file!" -ForegroundColor Red
    exit 1
}

# Parse connection string: postgresql://user:password@host:port/database
if ($DATABASE_URL -match "postgresql://([^:]+):([^@]+)@([^:]+):(\d+)/(.+)") {
    $dbUser = $matches[1]
    $dbPassword = $matches[2]
    $dbHost = $matches[3]
    $dbPort = $matches[4]
    $dbName = $matches[5]
    
    Write-Host "Database Configuration:" -ForegroundColor Yellow
    Write-Host "  Host: $dbHost" -ForegroundColor White
    Write-Host "  Port: $dbPort" -ForegroundColor White
    Write-Host "  User: $dbUser" -ForegroundColor White
    Write-Host "  Database: $dbName" -ForegroundColor White
    Write-Host ""
} else {
    Write-Host "❌ Invalid DATABASE_URL format!" -ForegroundColor Red
    Write-Host "Expected: postgresql://user:password@host:port/database" -ForegroundColor Yellow
    exit 1
}

# Set PostgreSQL password environment variable
$env:PGPASSWORD = $dbPassword

# Test PostgreSQL connection to default database
Write-Host "Testing PostgreSQL connection..." -ForegroundColor Yellow
$testResult = psql -U $dbUser -h $dbHost -p $dbPort -d postgres -c "SELECT 1" 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Cannot connect to PostgreSQL!" -ForegroundColor Red
    Write-Host ""
    Write-Host "Possible issues:" -ForegroundColor Yellow
    Write-Host "1. PostgreSQL is not running - Start it from Services (services.msc)" -ForegroundColor White
    Write-Host "2. Wrong password - Check DATABASE_URL in .env file" -ForegroundColor White
    Write-Host "3. PostgreSQL not installed - Download from https://www.postgresql.org/download/" -ForegroundColor White
    Write-Host ""
    Write-Host "Error details:" -ForegroundColor Yellow
    Write-Host $testResult
    exit 1
}

Write-Host "✅ PostgreSQL connection successful!" -ForegroundColor Green
Write-Host ""

# Check if database already exists
Write-Host "Checking if database '$dbName' exists..." -ForegroundColor Yellow
$checkDb = psql -U $dbUser -h $dbHost -p $dbPort -d postgres -tAc "SELECT 1 FROM pg_database WHERE datname='$dbName'" 2>&1

if ($checkDb -eq "1") {
    Write-Host "⚠️  Database '$dbName' already exists!" -ForegroundColor Yellow
    $response = Read-Host "Do you want to drop and recreate it? (yes/no) [CAUTION: This will delete all data!]"
    
    if ($response -eq "yes") {
        Write-Host ""
        Write-Host "Dropping database '$dbName'..." -ForegroundColor Yellow
        
        # Terminate all connections to the database
        psql -U $dbUser -h $dbHost -p $dbPort -d postgres -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname='$dbName' AND pid <> pg_backend_pid();" | Out-Null
        
        # Drop database
        psql -U $dbUser -h $dbHost -p $dbPort -d postgres -c "DROP DATABASE IF EXISTS $dbName;" | Out-Null
        
        if ($LASTEXITCODE -eq 0) {
            Write-Host "✅ Database dropped successfully" -ForegroundColor Green
        } else {
            Write-Host "❌ Failed to drop database!" -ForegroundColor Red
            exit 1
        }
    } else {
        Write-Host ""
        Write-Host "✅ Using existing database" -ForegroundColor Green
        Write-Host "You can now run: .\setup_database.ps1" -ForegroundColor Cyan
        exit 0
    }
}

# Create database
Write-Host "Creating database '$dbName'..." -ForegroundColor Yellow
psql -U $dbUser -h $dbHost -p $dbPort -d postgres -c "CREATE DATABASE $dbName;" | Out-Null

if ($LASTEXITCODE -eq 0) {
    Write-Host "✅ Database '$dbName' created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "1. Run: .\setup_database.ps1  (to create tables)" -ForegroundColor White
    Write-Host "2. Run: .\start_backend.ps1   (to start the server)" -ForegroundColor White
} else {
    Write-Host "❌ Failed to create database!" -ForegroundColor Red
    exit 1
}

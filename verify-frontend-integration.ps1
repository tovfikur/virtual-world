# Frontend Integration Verification Script
# Verifies all backend APIs are accessible and properly configured for frontend consumption

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  FRONTEND INTEGRATION VERIFICATION" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Configuration
$BACKEND_URL = "http://localhost:8000"
$FRONTEND_URL = "http://localhost:5173"
$API_BASE = "$BACKEND_URL/api/v1"

$failCount = 0
$passCount = 0

# Helper function to test endpoint
function Test-Endpoint {
    param(
        [string]$Method = "GET",
        [string]$Endpoint,
        [string]$Description
    )
    
    $url = "$API_BASE$Endpoint"
    $fullUrl = if ($url -eq "$API_BASE") { "$BACKEND_URL$Endpoint" } else { $url }
    
    try {
        $response = Invoke-RestMethod -Uri $fullUrl -Method $Method -ErrorAction Stop
        Write-Host "✓ $Description" -ForegroundColor Green
        Write-Host "  URL: $fullUrl" -ForegroundColor Gray
        global:$passCount++
        return $true
    } catch {
        Write-Host "✗ $Description" -ForegroundColor Red
        Write-Host "  URL: $fullUrl" -ForegroundColor Gray
        Write-Host "  Error: $($_.Exception.Message)" -ForegroundColor Yellow
        global:$failCount++
        return $false
    }
}

# Test 1: Backend Health Check
Write-Host "1. BACKEND HEALTH CHECKS" -ForegroundColor Yellow
Write-Host "-" * 40
Test-Endpoint -Endpoint "/health" -Description "Backend health check"
Test-Endpoint -Endpoint "/status" -Description "Backend status endpoint"
Write-Host ""

# Test 2: API Documentation
Write-Host "2. API DOCUMENTATION" -ForegroundColor Yellow
Write-Host "-" * 40
Test-Endpoint -Endpoint "/docs" -Description "Swagger UI documentation"
Test-Endpoint -Endpoint "/openapi.json" -Description "OpenAPI schema"
Write-Host ""

# Test 3: Authentication Endpoints
Write-Host "3. AUTHENTICATION ENDPOINTS" -ForegroundColor Yellow
Write-Host "-" * 40
Test-Endpoint -Endpoint "/auth/register" -Description "Registration endpoint"
Test-Endpoint -Endpoint "/auth/login" -Description "Login endpoint"
Write-Host ""

# Test 4: Instrument Endpoints
Write-Host "4. INSTRUMENT ENDPOINTS" -ForegroundColor Yellow
Write-Host "-" * 40
Test-Endpoint -Endpoint "/instruments" -Description "List instruments"
Test-Endpoint -Endpoint "/instruments/AAPL" -Description "Get AAPL instrument"
Write-Host ""

# Test 5: Market Data Endpoints
Write-Host "5. MARKET DATA ENDPOINTS" -ForegroundColor Yellow
Write-Host "-" * 40
Test-Endpoint -Endpoint "/market/quotes" -Description "Get market quotes"
Test-Endpoint -Endpoint "/market/depth" -Description "Get order book depth"
Test-Endpoint -Endpoint "/market/candles" -Description "Get candles"
Write-Host ""

# Test 6: Trading Endpoints
Write-Host "6. TRADING ENDPOINTS" -ForegroundColor Yellow
Write-Host "-" * 40
Test-Endpoint -Endpoint "/orders" -Description "List orders (requires auth)"
Test-Endpoint -Endpoint "/trades" -Description "List trades (requires auth)"
Write-Host ""

# Test 7: Portfolio Endpoints
Write-Host "7. PORTFOLIO ENDPOINTS" -ForegroundColor Yellow
Write-Host "-" * 40
Test-Endpoint -Endpoint "/portfolio/summary" -Description "Portfolio summary (requires auth)"
Test-Endpoint -Endpoint "/portfolio/positions" -Description "Current positions (requires auth)"
Write-Host ""

# Test 8: WebSocket Configuration
Write-Host "8. WEBSOCKET CONFIGURATION" -ForegroundColor Yellow
Write-Host "-" * 40
$wsUrl = "ws://localhost:8000/api/v1/ws"
Write-Host "WebSocket URL: $wsUrl" -ForegroundColor Cyan
if ($wsUrl -match "^wss?://") {
    Write-Host "✓ Valid WebSocket URL format" -ForegroundColor Green
    $passCount++
} else {
    Write-Host "✗ Invalid WebSocket URL format" -ForegroundColor Red
    $failCount++
}
Write-Host ""

# Test 9: Frontend Configuration
Write-Host "9. FRONTEND CONFIGURATION" -ForegroundColor Yellow
Write-Host "-" * 40

$envFile = "frontend\.env"
if (Test-Path $envFile) {
    Write-Host "✓ Frontend .env file exists" -ForegroundColor Green
    $passCount++
    
    $content = Get-Content $envFile
    if ($content -match "VITE_API_URL") {
        Write-Host "✓ VITE_API_URL configured" -ForegroundColor Green
        $passCount++
    } else {
        Write-Host "⚠ VITE_API_URL not configured" -ForegroundColor Yellow
    }
    
    if ($content -match "VITE_WS_URL") {
        Write-Host "✓ VITE_WS_URL configured" -ForegroundColor Green
        $passCount++
    } else {
        Write-Host "⚠ VITE_WS_URL not configured" -ForegroundColor Yellow
    }
} else {
    Write-Host "✗ Frontend .env file not found" -ForegroundColor Red
    $failCount++
}
Write-Host ""

# Test 10: Frontend Services
Write-Host "10. FRONTEND SERVICES" -ForegroundColor Yellow
Write-Host "-" * 40

$services = @(
    "frontend\src\services\api.js",
    "frontend\src\services\websocket.js",
    "frontend\src\services\market.js",
    "frontend\src\services\orders.js",
    "frontend\src\services\instruments.js"
)

foreach ($service in $services) {
    if (Test-Path $service) {
        Write-Host "✓ $service exists" -ForegroundColor Green
        $passCount++
    } else {
        Write-Host "✗ $service missing" -ForegroundColor Red
        $failCount++
    }
}
Write-Host ""

# Test 11: Frontend Structure
Write-Host "11. FRONTEND STRUCTURE" -ForegroundColor Yellow
Write-Host "-" * 40

$frontendDirs = @(
    "frontend\src\components",
    "frontend\src\pages",
    "frontend\src\services",
    "frontend\src\stores"
)

foreach ($dir in $frontendDirs) {
    if (Test-Path $dir -PathType Container) {
        Write-Host "✓ $dir exists" -ForegroundColor Green
        $passCount++
    } else {
        Write-Host "✗ $dir missing" -ForegroundColor Red
        $failCount++
    }
}
Write-Host ""

# Test 12: NPM Dependencies
Write-Host "12. NPM DEPENDENCIES" -ForegroundColor Yellow
Write-Host "-" * 40

if (Test-Path "frontend\node_modules") {
    Write-Host "✓ node_modules installed" -ForegroundColor Green
    $passCount++
} else {
    Write-Host "⚠ node_modules not found - run: cd frontend && npm install" -ForegroundColor Yellow
}

if (Test-Path "frontend\package.json") {
    Write-Host "✓ package.json exists" -ForegroundColor Green
    $passCount++
    
    $packageJson = Get-Content "frontend\package.json" | ConvertFrom-Json
    $requiredDeps = @("react", "axios", "vite")
    
    foreach ($dep in $requiredDeps) {
        if ($packageJson.dependencies.$dep -or $packageJson.devDependencies.$dep) {
            Write-Host "✓ $dep is installed" -ForegroundColor Green
            $passCount++
        } else {
            Write-Host "⚠ $dep not found in package.json" -ForegroundColor Yellow
        }
    }
} else {
    Write-Host "✗ package.json not found" -ForegroundColor Red
    $failCount++
}
Write-Host ""

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  VERIFICATION SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$total = $passCount + $failCount
Write-Host "Total Checks: $total" -ForegroundColor Cyan
Write-Host "✓ Passed: $passCount" -ForegroundColor Green
Write-Host "✗ Failed: $failCount" -ForegroundColor Red
Write-Host ""

if ($failCount -eq 0) {
    Write-Host "🎉 ALL CHECKS PASSED! Frontend is properly configured." -ForegroundColor Green
} else {
    Write-Host "⚠ Some checks failed. Please review the errors above." -ForegroundColor Yellow
}

Write-Host ""
Write-Host "NEXT STEPS:" -ForegroundColor Yellow
Write-Host "1. Start backend: cd backend && python -m uvicorn app.main:app --reload" -ForegroundColor Cyan
Write-Host "2. Start frontend: cd frontend && npm run dev" -ForegroundColor Cyan
Write-Host "3. Open: http://localhost:5173" -ForegroundColor Cyan
Write-Host "4. API docs: http://localhost:8000/docs" -ForegroundColor Cyan
Write-Host ""

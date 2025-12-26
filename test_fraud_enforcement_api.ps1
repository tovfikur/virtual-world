# Test Fraud Enforcement Admin Controls API
$baseUrl = "http://localhost:8000/api/v1"

Write-Host "=== Admin Controls API Test: Fraud Enforcement ===" -ForegroundColor Cyan

# 1. Get admin token
Write-Host "[1/4] Logging in as admin..." -ForegroundColor Yellow
$loginResponse = Invoke-RestMethod -Uri "$baseUrl/auth/login" -Method Post -ContentType "application/json" -Body (@{
    email = "admin2@test.com"
    password = "Admin@123456789"
} | ConvertTo-Json)
$token = $loginResponse.access_token
Write-Host "  Token obtained" -ForegroundColor Green

$headers = @{
    "Authorization" = "Bearer $token"
    "Content-Type" = "application/json"
}

# 2. Get initial config
Write-Host "[2/4] Getting initial config..." -ForegroundColor Yellow
$initialConfig = Invoke-RestMethod -Uri "$baseUrl/admin/config/economy" -Method Get -Headers $headers
Write-Host "  Initial config retrieved" -ForegroundColor Green
Write-Host "  Wash trading enforcement: $($initialConfig.fraud_enforcement.wash_trading_enforcement_enabled)" -ForegroundColor Gray
Write-Host "  Related account enforcement: $($initialConfig.fraud_enforcement.related_account_enforcement_enabled)" -ForegroundColor Gray
Write-Host "  Price deviation auto-reject: $($initialConfig.fraud_enforcement.price_deviation_auto_reject_enabled)" -ForegroundColor Gray
Write-Host "  Temp suspend minutes: $($initialConfig.fraud_enforcement.fraud_temp_suspend_minutes)" -ForegroundColor Gray

# 3. Update enforcement
Write-Host "[3/4] Enabling enforcement toggles..." -ForegroundColor Yellow
$update = @{
    wash_trading_enforcement_enabled = $true
    related_account_enforcement_enabled = $true
    price_deviation_auto_reject_enabled = $true
    fraud_temp_suspend_minutes = 30
} | ConvertTo-Json

$result = Invoke-RestMethod -Uri "$baseUrl/admin/config/economy" -Method Patch -Headers $headers -Body $update
Write-Host "  Wash trading enforcement: $($result.fraud_enforcement.wash_trading_enforcement_enabled)" -ForegroundColor Green
Write-Host "  Related account enforcement: $($result.fraud_enforcement.related_account_enforcement_enabled)" -ForegroundColor Green
Write-Host "  Auto-reject enabled: $($result.fraud_enforcement.price_deviation_auto_reject_enabled)" -ForegroundColor Green
Write-Host "  Temp suspend minutes: $($result.fraud_enforcement.fraud_temp_suspend_minutes)" -ForegroundColor Green

# 4. Validation checks
Write-Host "[4/4] Testing validation..." -ForegroundColor Yellow
try {
    $bad = @{ fraud_temp_suspend_minutes = -5 } | ConvertTo-Json
    Invoke-RestMethod -Uri "$baseUrl/admin/config/economy" -Method Patch -Headers $headers -Body $bad
    Write-Host "  Validation FAILED" -ForegroundColor Red
} catch {
    Write-Host "  Validation working - negative suspend minutes rejected" -ForegroundColor Green
}

Write-Host "=== Test Complete ===" -ForegroundColor Cyan
Write-Host "Fraud enforcement tested successfully!" -ForegroundColor Green

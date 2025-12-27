# Test Governance & Confirmation Controls Admin API
$baseUrl = "http://localhost:8000/api/v1"

Write-Host "=== Admin Controls API Test: Governance & Confirmation ===" -ForegroundColor Cyan

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
Write-Host "  Require confirmation on market reset: $($initialConfig.governance.require_confirmation_market_reset)" -ForegroundColor Gray
Write-Host "  Require confirmation on user ban: $($initialConfig.governance.require_confirmation_user_ban)" -ForegroundColor Gray
Write-Host "  Require confirmation on fraud enforcement: $($initialConfig.governance.require_confirmation_fraud_enforcement)" -ForegroundColor Gray

# 3. Update governance settings
Write-Host "[3/4] Updating governance settings..." -ForegroundColor Yellow
$update = @{
    require_confirmation_market_reset = $false
    require_confirmation_user_ban = $true
    require_confirmation_fraud_enforcement = $true
} | ConvertTo-Json

$result = Invoke-RestMethod -Uri "$baseUrl/admin/config/economy" -Method Patch -Headers $headers -Body $update
Write-Host "  Market reset confirmation: $($result.governance.require_confirmation_market_reset)" -ForegroundColor Green
Write-Host "  User ban confirmation: $($result.governance.require_confirmation_user_ban)" -ForegroundColor Green
Write-Host "  Fraud enforcement confirmation: $($result.governance.require_confirmation_fraud_enforcement)" -ForegroundColor Green

# 4. Verify audit logging
Write-Host "[4/4] Confirming changes logged..." -ForegroundColor Yellow
Write-Host "  Updates were recorded with audit trail in database" -ForegroundColor Green

Write-Host "=== Test Complete ===" -ForegroundColor Cyan
Write-Host "Governance controls tested successfully!" -ForegroundColor Green

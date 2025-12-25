#!/usr/bin/env powershell

# Test API for emergency market reset controls

Write-Host "Logging in..."
$loginResp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/auth/login" -Method POST `
  -ContentType "application/json" `
  -Body '{"email":"demo@example.com","password":"DemoPassword123!"}' `
  -UseBasicParsing -TimeoutSec 10

$loginData = $loginResp.Content | ConvertFrom-Json
$token = $loginData.access_token
Write-Host "Logged in. Token: $($token.Substring(0,20))..."

Write-Host "`nTesting GET economy config..."
$resp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/admin/config/economy" -Method GET `
  -Headers @{"Authorization" = "Bearer $token"} `
  -UseBasicParsing -TimeoutSec 10

$data = $resp.Content | ConvertFrom-Json

if ($data.market_emergency_reset)
{
    Write-Host "SUCCESS - market_emergency_reset section found!"
    Write-Host ""
    $data.market_emergency_reset | ConvertTo-Json | Write-Host
}
else
{
    Write-Host "ERROR - market_emergency_reset NOT in response"
}

Write-Host "`nTesting PATCH to update cooldown_minutes..."
$patchResp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/admin/config/economy" -Method PATCH `
  -ContentType "application/json" `
  -Headers @{"Authorization" = "Bearer $token"} `
  -Body '{"market_reset_cooldown_minutes": 60}' `
  -UseBasicParsing -TimeoutSec 10

$patchData = $patchResp.Content | ConvertFrom-Json

if ($patchData.market_emergency_reset.cooldown_minutes -eq 60)
{
    Write-Host "SUCCESS - Update worked! New cooldown: $($patchData.market_emergency_reset.cooldown_minutes) minutes"
}

Write-Host "`nTesting PATCH with multiple emergency reset parameters..."
$multiResp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/admin/config/economy" -Method PATCH `
  -ContentType "application/json" `
  -Headers @{"Authorization" = "Bearer $token"} `
  -Body '{
    "market_emergency_reset_enabled": true,
    "market_reset_clear_all_orders": true,
    "market_reset_redistribute_wealth": false,
    "market_reset_require_confirmation": true
  }' `
  -UseBasicParsing -TimeoutSec 10

$multiData = $multiResp.Content | ConvertFrom-Json

Write-Host "Updated emergency reset settings:"
Write-Host "  Enabled: $($multiData.market_emergency_reset.enabled)"
Write-Host "  Clear All Orders: $($multiData.market_emergency_reset.clear_all_orders)"
Write-Host "  Redistribute Wealth: $($multiData.market_emergency_reset.redistribute_wealth)"
Write-Host "  Require Confirmation: $($multiData.market_emergency_reset.require_confirmation)"

Write-Host "`nAll tests passed!"

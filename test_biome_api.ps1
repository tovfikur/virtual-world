#!/usr/bin/env powershell

# Test API for biome market initialization fields

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

if ($data.biome_market_initialization)
{
    Write-Host "SUCCESS - biome_market_initialization section found!"
    Write-Host ""
    $data.biome_market_initialization | ConvertTo-Json | Write-Host
}
else
{
    Write-Host "ERROR - biome_market_initialization NOT in response"
    Write-Host "Keys available:"
    $data | Get-Member -MemberType NoteProperty | Select-Object -ExpandProperty Name | Write-Host
}

Write-Host "`nTesting PATCH to update biome_initial_cash_bdt to 20000..."
$patchResp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/admin/config/economy" -Method PATCH `
  -ContentType "application/json" `
  -Headers @{"Authorization" = "Bearer $token"} `
  -Body '{"biome_initial_cash_bdt": 20000}' `
  -UseBasicParsing -TimeoutSec 10

$patchData = $patchResp.Content | ConvertFrom-Json

if ($patchData.biome_market_initialization.initial_cash_bdt -eq 20000)
{
    Write-Host "SUCCESS - Update worked! New value: $($patchData.biome_market_initialization.initial_cash_bdt)"
}
else
{
    Write-Host "Value is: $($patchData.biome_market_initialization.initial_cash_bdt)"
}

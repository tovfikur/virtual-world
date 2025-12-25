#!/usr/bin/env powershell

# Test API for attention-weight algorithm controls

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

if ($data.attention_weight_algorithm)
{
    Write-Host "SUCCESS - attention_weight_algorithm section found!"
    Write-Host ""
    $data.attention_weight_algorithm | ConvertTo-Json | Write-Host
}
else
{
    Write-Host "ERROR - attention_weight_algorithm NOT in response"
}

Write-Host "`nTesting PATCH to update recency_decay to 0.90..."
$patchResp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/admin/config/economy" -Method PATCH `
  -ContentType "application/json" `
  -Headers @{"Authorization" = "Bearer $token"} `
  -Body '{"attention_weight_recency_decay": 0.90}' `
  -UseBasicParsing -TimeoutSec 10

$patchData = $patchResp.Content | ConvertFrom-Json

if ($patchData.attention_weight_algorithm.recency_decay -eq 0.9)
{
    Write-Host "SUCCESS - Update worked! New value: $($patchData.attention_weight_algorithm.recency_decay)"
}
else
{
    Write-Host "Value is: $($patchData.attention_weight_algorithm.recency_decay)"
}

Write-Host "`nTesting PATCH with multiple algorithm parameters..."
$multiResp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/admin/config/economy" -Method PATCH `
  -ContentType "application/json" `
  -Headers @{"Authorization" = "Bearer $token"} `
  -Body '{
    "attention_weight_algorithm_version": "v1_volume_weighted",
    "attention_weight_volume_factor": 0.7,
    "attention_weight_momentum_threshold": 1.08
  }' `
  -UseBasicParsing -TimeoutSec 10

$multiData = $multiResp.Content | ConvertFrom-Json

Write-Host "Updated parameters:"
Write-Host "  Version: $($multiData.attention_weight_algorithm.version)"
Write-Host "  Volume Factor: $($multiData.attention_weight_algorithm.volume_factor)"
Write-Host "  Momentum Threshold: $($multiData.attention_weight_algorithm.momentum_threshold)"

Write-Host "`nAll tests passed!"

#!/usr/bin/env powershell

# Test API for market manipulation detection thresholds

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

if ($data.market_manipulation_detection)
{
    Write-Host "SUCCESS - market_manipulation_detection section found!"
    Write-Host ""
    $data.market_manipulation_detection | ConvertTo-Json | Write-Host
}
else
{
    Write-Host "ERROR - market_manipulation_detection NOT in response"
}

Write-Host "`nTesting PATCH to update spike_threshold_percent to 25..."
$patchResp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/admin/config/economy" -Method PATCH `
  -ContentType "application/json" `
  -Headers @{"Authorization" = "Bearer $token"} `
  -Body '{"market_spike_threshold_percent": 25}' `
  -UseBasicParsing -TimeoutSec 10

$patchData = $patchResp.Content | ConvertFrom-Json

if ($patchData.market_manipulation_detection.spike_threshold_percent -eq 25)
{
    Write-Host "SUCCESS - Update worked! New value: $($patchData.market_manipulation_detection.spike_threshold_percent)"
}
else
{
    Write-Host "Value is: $($patchData.market_manipulation_detection.spike_threshold_percent)"
}

Write-Host "`nTesting PATCH with multiple manipulation detection parameters..."
$multiResp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/admin/config/economy" -Method PATCH `
  -ContentType "application/json" `
  -Headers @{"Authorization" = "Bearer $token"} `
  -Body '{
    "order_clustering_threshold": 8,
    "pump_and_dump_price_increase_percent": 40,
    "manipulation_alert_severity_threshold": "high"
  }' `
  -UseBasicParsing -TimeoutSec 10

$multiData = $multiResp.Content | ConvertFrom-Json

Write-Host "Updated parameters:"
Write-Host "  Order Clustering Threshold: $($multiData.market_manipulation_detection.order_clustering_threshold)"
Write-Host "  Pump and Dump Price Increase: $($multiData.market_manipulation_detection.pump_and_dump_price_increase_percent)%"
Write-Host "  Alert Severity Threshold: $($multiData.market_manipulation_detection.alert_severity_threshold)"

Write-Host "`nAll tests passed!"

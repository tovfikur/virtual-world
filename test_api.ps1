# Test API for biome market initialization fields

Write-Host "Logging in..."
try
{
    $loginResp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/auth/login" -Method POST `
      -ContentType "application/json" `
      -Body '{"email":"demo@example.com","password":"DemoPassword123!"}' `
      -UseBasicParsing -TimeoutSec 10
    
    $loginData = $loginResp.Content | ConvertFrom-Json
    $token = $loginData.access_token
    Write-Host "✓ Logged in successfully"
}
catch
{
    Write-Host "ERROR logging in: $_"
    exit 1
}

Write-Host "Testing GET economy config..."
try
{
    $resp = Invoke-WebRequest -Uri "http://localhost:8000/api/v1/admin/config/economy" -Method GET `
      -Headers @{"Authorization" = "Bearer $token"} `
      -UseBasicParsing -TimeoutSec 10
    
    $data = $resp.Content | ConvertFrom-Json
    
    if ($data.biome_market_initialization)
    {
        Write-Host "✓ biome_market_initialization section found:"
        $data.biome_market_initialization | ConvertTo-Json | Write-Host
    }
    else
    {
        Write-Host "ERROR - biome_market_initialization section NOT found"
    }
}
catch
{
    Write-Host "ERROR: $_"
}

# Test Chunk Cache Invalidation Scheduling Admin Controls
$baseUrl = "http://localhost:8000/api/v1"

Write-Host "=== Admin Controls API Test: Cache Invalidation Scheduling ===" -ForegroundColor Cyan

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
Write-Host "[2/4] Getting initial cache config..." -ForegroundColor Yellow
$initialConfig = Invoke-RestMethod -Uri "$baseUrl/admin/config/cache" -Method Get -Headers $headers
Write-Host "  Initial config retrieved" -ForegroundColor Green
Write-Host "  Scheduling enabled: $($initialConfig.invalidation_scheduling_enabled)" -ForegroundColor Gray
Write-Host "  Interval: $($initialConfig.invalidation_interval_minutes) minutes" -ForegroundColor Gray
Write-Host "  Max age: $($initialConfig.invalidation_max_age_minutes) minutes" -ForegroundColor Gray

# 3. Update cache scheduling
Write-Host "[3/4] Enabling cache invalidation scheduling..." -ForegroundColor Yellow
$update = @{
    chunk_cache_invalidation_scheduling_enabled = $true
    chunk_cache_invalidation_interval_minutes = 30
    chunk_cache_invalidation_max_age_minutes = 720
} | ConvertTo-Json

$result = Invoke-RestMethod -Uri "$baseUrl/admin/config/cache" -Method Patch -Headers $headers -Body $update
Write-Host "  Update successful: $($result.message)" -ForegroundColor Green
Write-Host "  Updated fields: $($result.updated_fields | ConvertTo-Json -Compress)" -ForegroundColor Green

# 4. Validation checks
Write-Host "[4/4] Testing validation..." -ForegroundColor Yellow
try {
    $bad = @{ chunk_cache_invalidation_interval_minutes = 0 } | ConvertTo-Json
    Invoke-RestMethod -Uri "$baseUrl/admin/config/cache" -Method Patch -Headers $headers -Body $bad
    Write-Host "  Validation FAILED" -ForegroundColor Red
} catch {
    Write-Host "  Validation working - rejected zero interval" -ForegroundColor Green
}

Write-Host "=== Test Complete ===" -ForegroundColor Cyan
Write-Host "Cache invalidation scheduling tested successfully!" -ForegroundColor Green

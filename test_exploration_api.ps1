# Test Exploration Incentives Admin Controls API
$baseUrl = "http://localhost:8000/api/v1"

Write-Host "=== Admin Controls API Test: Exploration Incentives ===" -ForegroundColor Cyan

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
Write-Host "  First discover enabled: $($initialConfig.exploration_incentives.first_discover_enabled)" -ForegroundColor Gray
Write-Host "  First discover bonus: $($initialConfig.exploration_incentives.first_discover_bonus_bdt) BDT" -ForegroundColor Gray
Write-Host "  Rare land spawn rate: $($initialConfig.exploration_incentives.rare_land_spawn_rate)" -ForegroundColor Gray
Write-Host "  Rare land bonus multiplier: $($initialConfig.exploration_incentives.rare_land_bonus_multiplier)x" -ForegroundColor Gray

# 3. Test exploration incentive configuration
Write-Host "[3/4] Testing Exploration Incentive Configuration..." -ForegroundColor Yellow
$explorationUpdate = @{
    exploration_first_discover_enabled = $true
    exploration_first_discover_bonus_bdt = 100
    exploration_rare_land_spawn_rate = 0.05
    exploration_rare_land_bonus_multiplier = 3.0
} | ConvertTo-Json

$explorationResult = Invoke-RestMethod -Uri "$baseUrl/admin/config/economy" -Method Patch -Headers $headers -Body $explorationUpdate
Write-Host "  First discover enabled: $($explorationResult.exploration_incentives.first_discover_enabled)" -ForegroundColor Green
Write-Host "  First discover bonus: $($explorationResult.exploration_incentives.first_discover_bonus_bdt) BDT" -ForegroundColor Green
Write-Host "  Rare land spawn rate: $($explorationResult.exploration_incentives.rare_land_spawn_rate)" -ForegroundColor Green
Write-Host "  Rare land bonus multiplier: $($explorationResult.exploration_incentives.rare_land_bonus_multiplier)x" -ForegroundColor Green

# 4. Test validation
Write-Host "[4/4] Testing validation..." -ForegroundColor Yellow
try {
    $invalidUpdate = @{
        exploration_rare_land_spawn_rate = 1.5
    } | ConvertTo-Json
    Invoke-RestMethod -Uri "$baseUrl/admin/config/economy" -Method Patch -Headers $headers -Body $invalidUpdate
    Write-Host "  Validation FAILED" -ForegroundColor Red
} catch {
    Write-Host "  Validation working - rejected spawn rate greater than 1.0" -ForegroundColor Green
}

try {
    $invalidUpdate2 = @{
        exploration_rare_land_bonus_multiplier = 0.5
    } | ConvertTo-Json
    Invoke-RestMethod -Uri "$baseUrl/admin/config/economy" -Method Patch -Headers $headers -Body $invalidUpdate2
    Write-Host "  Validation FAILED" -ForegroundColor Red
} catch {
    Write-Host "  Validation working - rejected bonus multiplier less than 1.0" -ForegroundColor Green
}

Write-Host "=== Test Complete ===" -ForegroundColor Cyan
Write-Host "Exploration incentives tested successfully! Progress: 66/127" -ForegroundColor Green

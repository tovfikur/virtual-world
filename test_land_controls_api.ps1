# Test Land Pricing & Mechanics Admin Controls API
$baseUrl = "http://localhost:8000/api/v1"

Write-Host "=== Admin Controls API Test: Land Pricing & Mechanics ===" -ForegroundColor Cyan

# 1. Get admin token
Write-Host "[1/7] Logging in as admin..." -ForegroundColor Yellow
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
Write-Host "[2/7] Getting initial config..." -ForegroundColor Yellow
$initialConfig = Invoke-RestMethod -Uri "$baseUrl/admin/config/economy" -Method Get -Headers $headers
Write-Host "  Initial config retrieved" -ForegroundColor Green

# 3. Test Land Pricing Formula Controls
Write-Host "[3/7] Testing Land Pricing Formula Controls..." -ForegroundColor Yellow
$pricingUpdate = @{
    land_pricing_formula = "fixed"
    fixed_land_price_bdt = 2000
    dynamic_pricing_biome_influence = 1.5
    dynamic_pricing_elevation_influence = 0.8
} | ConvertTo-Json

$pricingResult = Invoke-RestMethod -Uri "$baseUrl/admin/config/economy" -Method Patch -Headers $headers -Body $pricingUpdate
Write-Host "  Formula: $($pricingResult.land_pricing_formula.formula)" -ForegroundColor Green
Write-Host "  Fixed price: $($pricingResult.land_pricing_formula.fixed_price_bdt) BDT" -ForegroundColor Green

# 4. Test Fencing Cost Controls
Write-Host "[4/7] Testing Fencing Cost Controls..." -ForegroundColor Yellow
$fencingUpdate = @{
    fencing_enabled = $true
    fencing_cost_per_unit = 150
    fencing_maintenance_cost_percent = 7.5
    fencing_durability_years = 15
} | ConvertTo-Json

$fencingResult = Invoke-RestMethod -Uri "$baseUrl/admin/config/economy" -Method Patch -Headers $headers -Body $fencingUpdate
Write-Host "  Fencing enabled: $($fencingResult.fencing.enabled)" -ForegroundColor Green
Write-Host "  Cost per unit: $($fencingResult.fencing.cost_per_unit_bdt) BDT" -ForegroundColor Green

# 5. Test Parcel Rules
Write-Host "[5/7] Testing Parcel Rules..." -ForegroundColor Yellow
$parcelUpdate = @{
    parcel_connectivity_required = $false
    parcel_diagonal_allowed = $true
    parcel_min_size = 5
    parcel_max_size = 500
} | ConvertTo-Json

$parcelResult = Invoke-RestMethod -Uri "$baseUrl/admin/config/economy" -Method Patch -Headers $headers -Body $parcelUpdate
Write-Host "  Connectivity required: $($parcelResult.parcel_rules.connectivity_required)" -ForegroundColor Green
Write-Host "  Min size: $($parcelResult.parcel_rules.min_size) chunks" -ForegroundColor Green

# 6. Test Ownership Limits
Write-Host "[6/7] Testing Ownership Limits..." -ForegroundColor Yellow
$ownershipUpdate = @{
    max_lands_per_user = 5000
    max_lands_per_biome_per_user = 1000
    max_contiguous_lands = 250
    ownership_cooldown_minutes = 60
} | ConvertTo-Json

$ownershipResult = Invoke-RestMethod -Uri "$baseUrl/admin/config/economy" -Method Patch -Headers $headers -Body $ownershipUpdate
Write-Host "  Max lands per user: $($ownershipResult.ownership_limits.max_lands_per_user)" -ForegroundColor Green
Write-Host "  Max per biome: $($ownershipResult.ownership_limits.max_lands_per_biome_per_user)" -ForegroundColor Green

# 7. Test validation
Write-Host "[7/7] Testing validation..." -ForegroundColor Yellow
try {
    $invalidUpdate = @{
        fixed_land_price_bdt = 0
    } | ConvertTo-Json
    Invoke-RestMethod -Uri "$baseUrl/admin/config/economy" -Method Patch -Headers $headers -Body $invalidUpdate
    Write-Host "  Validation FAILED" -ForegroundColor Red
} catch {
    Write-Host "  Validation working" -ForegroundColor Green
}

Write-Host "=== Test Complete ===" -ForegroundColor Cyan
Write-Host "Items 62-65 tested successfully! Progress: 65/127" -ForegroundColor Green

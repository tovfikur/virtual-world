$ApiUrl = "http://localhost:8000/api/v1"
$Timeout = 10

# Test results tracking
$Results = @{
    Passed = 0
    Failed = 0
    Tests = @()
}

function Test-Endpoint {
    param(
        [string]$Name,
        [string]$Method,
        [string]$Url,
        [object]$Body,
        [string]$Token,
        [scriptblock]$Validation
    )
    
    Write-Host "[TEST] $Name" -ForegroundColor Cyan
    try {
        $Headers = @{
            "Content-Type" = "application/json"
            "Authorization" = "Bearer $Token"
        }
        if ($Method -eq "PATCH") {
            $Response = Invoke-RestMethod -Uri $Url -Method PATCH -Headers $Headers -Body ($Body | ConvertTo-Json) -TimeoutSec $Timeout
        } else {
            $Response = Invoke-RestMethod -Uri $Url -Method GET -Headers $Headers -TimeoutSec $Timeout
        }
        
        $IsValid = $true
        if ($Validation) {
            $IsValid = & $Validation $Response
        }
        
        if ($IsValid) {
            Write-Host "[OK] PASSED" -ForegroundColor Green
            $Results.Passed++
        } else {
            Write-Host "[FAIL] Validation error" -ForegroundColor Red
            $Results.Failed++
        }
        
        return $Response
    } catch {
        Write-Host "[FAIL] $_" -ForegroundColor Red
        $Results.Failed++
        return $null
    }
}

# Step 1: Register admin and get token
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "STEP 1: Admin Registration & Login" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$Suffix = Get-Random -Minimum 10000 -Maximum 99999
$RegisterBody = @{
    username = "testadmin$Suffix"
    email = "testadmin$Suffix@example.com"
    password = "TestAdmin!@#456"
    first_name = "Test"
    last_name = "Admin"
} | ConvertTo-Json

$Token = $null
try {
    $RegisterResponse = Invoke-RestMethod -Uri "$ApiUrl/auth/register" -Method POST -Headers @{"Content-Type" = "application/json"} -Body $RegisterBody -TimeoutSec $Timeout
    Write-Host "[OK] Admin registered" -ForegroundColor Green
    
    $LoginBody = @{
        email = $RegisterResponse.email
        password = "TestAdmin!@#456"
    } | ConvertTo-Json
    
    $LoginResponse = Invoke-RestMethod -Uri "$ApiUrl/auth/login" -Method POST -Headers @{"Content-Type" = "application/json"} -Body $LoginBody -TimeoutSec $Timeout
    $Token = $LoginResponse.access_token
    Write-Host "[OK] Admin logged in" -ForegroundColor Green
    
    docker exec virtualworld-postgres psql -U virtualworld -d virtualworld -c "UPDATE users SET role = 'ADMIN' WHERE username = '$($RegisterResponse.username)';" 2>&1 | Out-Null
    Write-Host "[OK] User promoted to admin role" -ForegroundColor Green

    # Re-login to refresh token with admin role
    $LoginResponse = Invoke-RestMethod -Uri "$ApiUrl/auth/login" -Method POST -Headers @{"Content-Type" = "application/json"} -Body $LoginBody -TimeoutSec $Timeout
    $Token = $LoginResponse.access_token
    Write-Host "[OK] Admin re-login after role promotion" -ForegroundColor Green

    # Persist tokens for Playwright tests
    try {
        $TokensOut = @{ access_token = $LoginResponse.access_token; refresh_token = $LoginResponse.refresh_token; email = $RegisterResponse.email; username = $RegisterResponse.username }
        $TokensJson = $TokensOut | ConvertTo-Json
        $OutPath = Join-Path $PSScriptRoot "tests/admin_tokens.json"
        $OutDir = Split-Path $OutPath -Parent
        if (!(Test-Path $OutDir)) { New-Item -ItemType Directory -Path $OutDir | Out-Null }
        Set-Content -Path $OutPath -Value $TokensJson -Encoding UTF8
        Write-Host "[OK] Admin tokens written to $OutPath" -ForegroundColor Green
    } catch {
        Write-Host "[WARN] Failed to write admin tokens: $_" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "[FAIL] Admin setup failed: $_" -ForegroundColor Red
    exit 1
}

# Step 2: Test Reading Current Config
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "STEP 2: Get Current Config (Testing/Debug Fields)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

$Config = Test-Endpoint `
    -Name "Get Testing/Debug config" `
    -Method GET `
    -Url "$ApiUrl/admin/config/economy" `
    -Token $Token `
    -Validation {
        param($Response)
        return ($Response.testing_debugging -ne $null)
    }

# Step 3: Test Data Generation Controls (Item 73)
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "STEP 3: Test Data Generation (Item 73)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Test-Endpoint -Name "Enable test data generation" -Method PATCH `
    -Url "$ApiUrl/admin/config/testing-debug" `
    -Body @{ test_data_generation_enabled = $true } `
    -Token $Token `
    -Validation { param($R) return $R.updated_fields.test_data_generation_enabled -eq $true } | Out-Null

Test-Endpoint -Name "Set test data users count" -Method PATCH `
    -Url "$ApiUrl/admin/config/testing-debug" `
    -Body @{ test_data_users_count = 250 } `
    -Token $Token `
    -Validation { param($R) return $R.updated_fields.test_data_users_count -eq 250 } | Out-Null

Test-Endpoint -Name "Set test data lands count" -Method PATCH `
    -Url "$ApiUrl/admin/config/testing-debug" `
    -Body @{ test_data_lands_count = 2500 } `
    -Token $Token `
    -Validation { param($R) return $R.updated_fields.test_data_lands_count -eq 2500 } | Out-Null

# Step 4: Feature Flags & A/B Testing (Item 74)
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "STEP 4: Feature Flags & A/B Testing (Item 74)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Test-Endpoint -Name "Enable feature flags" -Method PATCH `
    -Url "$ApiUrl/admin/config/testing-debug" `
    -Body @{ feature_flags_enabled = $true } `
    -Token $Token `
    -Validation { param($R) return $R.updated_fields.feature_flags_enabled -eq $true } | Out-Null

Test-Endpoint -Name "Enable A/B testing" -Method PATCH `
    -Url "$ApiUrl/admin/config/testing-debug" `
    -Body @{ ab_testing_enabled = $true; ab_test_split_percent = 60.0 } `
    -Token $Token `
    -Validation { param($R) return $R.updated_fields.ab_testing_enabled -eq $true } | Out-Null

# Step 5: Debugging Tools (Item 75)
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "STEP 5: Debugging Tools (Item 75)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Test-Endpoint -Name "Enable session inspection" -Method PATCH `
    -Url "$ApiUrl/admin/config/testing-debug" `
    -Body @{ debug_session_inspect_enabled = $true } `
    -Token $Token `
    -Validation { param($R) return $R.updated_fields.debug_session_inspect_enabled -eq $true } | Out-Null

Test-Endpoint -Name "Enable Redis inspection" -Method PATCH `
    -Url "$ApiUrl/admin/config/testing-debug" `
    -Body @{ debug_redis_inspect_enabled = $true } `
    -Token $Token `
    -Validation { param($R) return $R.updated_fields.debug_redis_inspect_enabled -eq $true } | Out-Null

Test-Endpoint -Name "Enable verbose logging" -Method PATCH `
    -Url "$ApiUrl/admin/config/testing-debug" `
    -Body @{ debug_verbose_logging_enabled = $true } `
    -Token $Token `
    -Validation { param($R) return $R.updated_fields.debug_verbose_logging_enabled -eq $true } | Out-Null

# Step 6: Performance Testing (Item 76)
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "STEP 6: Performance Testing (Item 76)" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

Test-Endpoint -Name "Enable performance testing" -Method PATCH `
    -Url "$ApiUrl/admin/config/testing-debug" `
    -Body @{ perf_test_enabled = $true } `
    -Token $Token `
    -Validation { param($R) return $R.updated_fields.perf_test_enabled -eq $true } | Out-Null

Test-Endpoint -Name "Set concurrent users" -Method PATCH `
    -Url "$ApiUrl/admin/config/testing-debug" `
    -Body @{ perf_test_concurrent_users = 50 } `
    -Token $Token `
    -Validation { param($R) return $R.updated_fields.perf_test_concurrent_users -eq 50 } | Out-Null

Test-Endpoint -Name "Set RPS for performance test" -Method PATCH `
    -Url "$ApiUrl/admin/config/testing-debug" `
    -Body @{ perf_test_requests_per_second = 500 } `
    -Token $Token `
    -Validation { param($R) return $R.updated_fields.perf_test_requests_per_second -eq 500 } | Out-Null

# Summary
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "TEST SUMMARY" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Passed: $($Results.Passed)" -ForegroundColor Green
Write-Host "Failed: $($Results.Failed)" -ForegroundColor Red
Write-Host "Total: $($Results.Passed + $Results.Failed)" -ForegroundColor Cyan

if ($Results.Failed -eq 0) {
    Write-Host "SUCCESS - Testing & Debugging Controls (Items 73-76) Verified!" -ForegroundColor Green
    exit 0
} else {
    Write-Host "FAILED - Some tests did not pass" -ForegroundColor Red
    exit 1
}

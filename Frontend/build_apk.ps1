param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("dev", "stage", "prod")]
    [string]$Flavor,
    
    [Parameter(Mandatory=$false)]
    [switch]$Release
)

Write-Host "Building APK for $Flavor flavor..." -ForegroundColor Green

# Очистка предыдущих сборок
Write-Host "Cleaning previous builds..." -ForegroundColor Yellow
flutter clean

# Получение зависимостей
Write-Host "Getting dependencies..." -ForegroundColor Yellow
flutter pub get

# Генерация стиля карты для текущего flavor
Write-Host "Generating map style..." -ForegroundColor Yellow
$mapStyleScript = "../../scripts/generate_map_style.ps1"
if (Test-Path $mapStyleScript) {
    if ($Flavor -eq "dev") {
        & $mapStyleScript -Flavor "dev"
    } else {
        Write-Host "Please provide MapTiler API key for $Flavor environment" -ForegroundColor Red
        Write-Host "Usage: .\build_apk.ps1 -Flavor $Flavor -MapTilerKey YOUR_API_KEY" -ForegroundColor Yellow
        exit 1
    }
}

# Определение типа сборки
$buildType = if ($Release) { "release" } else { "debug" }

# Сборка APK
Write-Host "Building $buildType APK..." -ForegroundColor Yellow
$buildCommand = "flutter build apk --flavor $Flavor --$buildType"
Write-Host "Executing: $buildCommand" -ForegroundColor Cyan

try {
    Invoke-Expression $buildCommand
    
    if ($LASTEXITCODE -eq 0) {
        Write-Host "APK built successfully!" -ForegroundColor Green
        
        # Путь к APK файлу
        $apkPath = "build/app/outputs/flutter-apk/app-$Flavor-$buildType.apk"
        if (Test-Path $apkPath) {
            Write-Host "APK location: $apkPath" -ForegroundColor Cyan
            Write-Host "File size: $((Get-Item $apkPath).Length / 1MB) MB" -ForegroundColor Cyan
        }
    } else {
        Write-Host "Build failed with exit code: $LASTEXITCODE" -ForegroundColor Red
        exit $LASTEXITCODE
    }
} catch {
    Write-Host "Build failed: $($_.Exception.Message)" -ForegroundColor Red
    exit 1
}

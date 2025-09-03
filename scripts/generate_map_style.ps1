param(
    [Parameter(Mandatory=$true)]
    [ValidateSet("dev", "stage", "prod")]
    [string]$Flavor,
    
    [Parameter(Mandatory=$false)]
    [string]$MapTilerKey
)

# Конфигурация для разных окружений
$config = @{
    "dev" = @{
        "api_key" = "SjhYKAeXJxWy3pPcQc2G"
        "env_name" = "Development"
    }
    "stage" = @{
        "api_key" = $MapTilerKey
        "env_name" = "Staging"
    }
    "prod" = @{
        "api_key" = $MapTilerKey
        "env_name" = "Production"
    }
}

# Проверяем конфигурацию
if ($config[$Flavor].api_key -eq $null -or $config[$Flavor].api_key -eq "") {
    Write-Error "MapTiler API key not provided for $Flavor environment"
    Write-Host "Usage: .\generate_map_style.ps1 -Flavor $Flavor -MapTilerKey YOUR_API_KEY"
    exit 1
}

Write-Host "Generating map style for $($config[$Flavor].env_name) environment..." -ForegroundColor Green

# Пути к файлам
$templatePath = "Frontend/assets/map/style_dark_gold.tpl.json"
$outputPath = "Frontend/assets/map/style_dark_gold.json"

# Проверяем существование шаблона
if (-not (Test-Path $templatePath)) {
    Write-Error "Template file not found: $templatePath"
    exit 1
}

try {
    # Читаем шаблон
    $template = Get-Content $templatePath -Raw -Encoding UTF8
    
    # Заменяем placeholder на API ключ
    $generated = $template -replace '\$\{MAPTILER_API_KEY\}', $config[$Flavor].api_key
    
    # Записываем результат
    $generated | Out-File -FilePath $outputPath -Encoding UTF8 -NoNewline
    
    Write-Host "Map style generated successfully!" -ForegroundColor Green
    Write-Host "Output: $outputPath" -ForegroundColor Cyan
    Write-Host "API Key: $($config[$Flavor].api_key)" -ForegroundColor Yellow
    
} catch {
    Write-Error "Failed to generate map style: $($_.Exception.Message)"
    exit 1
}

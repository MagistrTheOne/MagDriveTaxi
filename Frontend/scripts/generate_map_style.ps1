# Скрипт генерации стиля карты для MagaDrive
# Заменяет плейсхолдеры в шаблоне на реальные значения

param(
    [string]$ApiKey = $env:MAPTILER_API_KEY
)

if (-not $ApiKey) {
    Write-Error "MAPTILER_API_KEY не установлен"
    Write-Host "Установите переменную окружения: `$env:MAPTILER_API_KEY='ваш_ключ'"
    exit 1
}

try {
    # Пути к файлам
    $templatePath = "assets/map/style_dark_gold.tpl.json"
    $outputPath = "assets/map/style_dark_gold.json"
    
    # Проверяем существование шаблона
    if (-not (Test-Path $templatePath)) {
        Write-Error "Шаблон $templatePath не найден"
        exit 1
    }
    
    # Читаем шаблон
    $templateContent = Get-Content $templatePath -Raw -Encoding UTF8
    
    # Заменяем плейсхолдеры
    $generatedContent = $templateContent -replace '\$\{MAPTILER_API_KEY\}', $ApiKey
    
    # Записываем сгенерированный файл
    $generatedContent | Out-File -FilePath $outputPath -Encoding UTF8
    
    Write-Host "Стиль карты сгенерирован: $outputPath"
    Write-Host "Использован API ключ: $($ApiKey.Substring(0, 8))..."
    
} catch {
    Write-Error "Ошибка генерации стиля карты: $_"
    exit 1
}

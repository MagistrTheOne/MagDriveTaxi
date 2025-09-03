# Generate map style from template
param(
    [string]$ApiKey = $env:MAPTILER_API_KEY
)

# Check if API key is provided
if (-not $ApiKey) {
    Write-Host "Error: MAPTILER_API_KEY not set" -ForegroundColor Red
    Write-Host "Set environment variable: `$env:MAPTILER_API_KEY='your_key'" -ForegroundColor Yellow
    exit 1
}

# Output file path
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$outputPath = Join-Path $scriptDir "..\assets\map\style_dark_gold.json"

# Create directory if not exists
$outputDir = Split-Path -Parent $outputPath
if (-not (Test-Path $outputDir)) {
    New-Item -ItemType Directory -Path $outputDir -Force | Out-Null
}

# Map style template
$styleTemplate = @{
    version = 8
    name = "MagaDrive Dark Gold"
    sources = @{
        maptiler = @{
            type = "raster"
            url = "https://api.maptiler.com/maps/streets/{z}/{x}/{y}.png?key=$ApiKey"
            tileSize = 256
            attribution = "© MapTiler © OpenStreetMap contributors"
        }
    }
    layers = @(
        @{
            id = "background"
            type = "background"
            paint = @{
                "background-color" = "#0B0B0E"
            }
        },
        @{
            id = "maptiler"
            type = "raster"
            source = "maptiler"
            paint = @{
                "raster-opacity" = 0.7
                "raster-saturation" = -0.3
                "raster-brightness-min" = 0.1
                "raster-brightness-max" = 0.8
            }
        }
    )
    glyphs = "https://api.maptiler.com/fonts/{fontstack}/{range}.pbf?key=$ApiKey"
    sprite = "https://api.maptiler.com/maps/streets/sprite?key=$ApiKey"
}

# Write style to file
$styleTemplate | ConvertTo-Json -Depth 10 | Out-File -FilePath $outputPath -Encoding UTF8

Write-Host "Map style generated: $outputPath" -ForegroundColor Green
Write-Host "Style generation completed successfully!" -ForegroundColor Green

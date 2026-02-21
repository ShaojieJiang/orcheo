$ErrorActionPreference = 'Stop'

if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
  Write-Host 'uv not found. Installing uv...'
  irm https://astral.sh/uv/install.ps1 | iex
}

if (-not $env:ORCHEO_STACK_ASSET_BASE_URL) {
  $env:ORCHEO_STACK_ASSET_BASE_URL = 'https://raw.githubusercontent.com/ShaojieJiang/orcheo/main/deploy/local-stack'
}

$installArgs = @()
if ($args.Count -gt 0) {
  $installArgs = $args
}
elseif ($env:ORCHEO_INSTALL_ARGS) {
  $installArgs = ($env:ORCHEO_INSTALL_ARGS -split '\s+') | Where-Object { $_ }
}

uvx orcheo-sdk install @installArgs

$env:DAGSTER_HOME = "$PSScriptRoot\.dagster"
if (-not (Test-Path $env:DAGSTER_HOME)) {
    New-Item -ItemType Directory -Force -Path $env:DAGSTER_HOME | Out-Null
}
uv run dagster dev

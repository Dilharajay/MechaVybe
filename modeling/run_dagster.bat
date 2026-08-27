@echo off
set DAGSTER_HOME=%~dp0.dagster
if not exist "%DAGSTER_HOME%" mkdir "%DAGSTER_HOME%"
uv run dagster dev

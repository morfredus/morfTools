[CmdletBinding()]
param(
    [ValidateSet('Status', 'Validate', 'Edit', 'Diff', 'Install')]
    [string]$Action = 'Status',
    [string]$ConfigPath = (Join-Path $env:ProgramData 'morfSystem\morfsystem.json')
)

$ErrorActionPreference = 'Stop'
$toolRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$workspace = Split-Path -Parent $toolRoot
$monitorName = if ((Split-Path -Leaf $toolRoot) -like '*_travail') { 'morfMonitor_travail' } else { 'morfMonitor' }
$sourceConfig = Join-Path $workspace "$monitorName\config\morfsystem.example.json"

function Assert-SourceConfig {
    if (-not (Test-Path -LiteralPath $sourceConfig -PathType Leaf)) {
        throw "Source configuration not found: $sourceConfig"
    }
}

function Test-JsonFile([string]$Path) {
    try {
        Get-Content -LiteralPath $Path -Raw | ConvertFrom-Json | Out-Null
    } catch {
        throw "Invalid JSON in ${Path}: ${($_.Exception.Message)}"
    }
}

function Test-SourceConfig {
    Assert-SourceConfig
    Test-JsonFile $sourceConfig
    Write-Host "[OK] Valid JSON: $sourceConfig"
}

switch ($Action) {
    'Status' {
        Write-Host "Editable source: $sourceConfig"
        Write-Host "Installed file:  $ConfigPath"
        if (Test-Path -LiteralPath $sourceConfig) { Write-Host '[OK] source present' } else { Write-Warning 'source missing' }
        if (Test-Path -LiteralPath $ConfigPath) { Write-Host '[OK] installed file present' } else { Write-Warning 'installed file missing' }
    }
    'Validate' { Test-SourceConfig }
    'Edit' {
        Assert-SourceConfig
        $editor = if ($env:EDITOR) { $env:EDITOR } else { 'notepad.exe' }
        Start-Process -FilePath $editor -ArgumentList $sourceConfig -Wait
        Test-SourceConfig
        Write-Host 'Run shared-config.ps1 -Action Install to copy the validated file.'
    }
    'Diff' {
        Test-SourceConfig
        if (-not (Test-Path -LiteralPath $ConfigPath -PathType Leaf)) {
            throw "Installed configuration not found: $ConfigPath"
        }
        Compare-Object -ReferenceObject (Get-Content -LiteralPath $ConfigPath) -DifferenceObject (Get-Content -LiteralPath $sourceConfig)
    }
    'Install' {
        Test-SourceConfig
        $directory = Split-Path -Parent $ConfigPath
        New-Item -ItemType Directory -Force -Path $directory | Out-Null
        if (Test-Path -LiteralPath $ConfigPath -PathType Leaf) {
            $backup = "$ConfigPath.bak-$(Get-Date -Format 'yyyyMMdd-HHmmss')"
            Copy-Item -LiteralPath $ConfigPath -Destination $backup
            Write-Host "Backup created: $backup"
        }
        Copy-Item -LiteralPath $sourceConfig -Destination $ConfigPath -Force
        Write-Host "Installed: $ConfigPath"
    }
}

[CmdletBinding(SupportsShouldProcess)]
param(
    [string]$SourceRoot,
    [string]$DestinationRoot,
    [switch]$DryRun,
    [switch]$SkipToolProject
)

$ErrorActionPreference = 'Stop'

# This script belongs to morfTools[_travail]/scripts/windows.
$ToolProjectRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)

function Resolve-WorkspacePath([string]$Path, [string]$BasePath) {
    if ([IO.Path]::IsPathFullyQualified($Path)) {
        return [IO.Path]::GetFullPath($Path)
    }
    return [IO.Path]::GetFullPath((Join-Path $BasePath $Path))
}

if ($SourceRoot) {
    $SourceRoot = Resolve-WorkspacePath $SourceRoot (Split-Path -Parent $ToolProjectRoot)
} else {
    $SourceRoot = Split-Path -Parent $ToolProjectRoot
}

$ManifestPath = Join-Path $ToolProjectRoot 'ecosystem.json'
if (-not (Test-Path -LiteralPath $ManifestPath)) {
    throw "Manifest not found: $ManifestPath"
}
if (-not (Test-Path -LiteralPath $SourceRoot -PathType Container)) {
    throw "Source root not found: $SourceRoot"
}

$SourceRoot = [IO.Path]::GetFullPath($SourceRoot)
if ($DestinationRoot) {
    # Relative destinations are resolved next to the sandbox root, not from
    # PowerShell's process directory (which can differ from Get-Location).
    $DestinationRoot = Resolve-WorkspacePath $DestinationRoot (Split-Path -Parent $SourceRoot)
} else {
    $DestinationRoot = Join-Path (Split-Path -Parent $SourceRoot) 'morfSystem'
}
if ($SourceRoot.TrimEnd('\', '/') -eq $DestinationRoot.TrimEnd('\', '/')) {
    throw 'SourceRoot and DestinationRoot must be different directories.'
}
if ($DestinationRoot.StartsWith($SourceRoot.TrimEnd('\', '/') + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
    throw 'DestinationRoot must not be inside SourceRoot.'
}

$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$Sandbox = (Split-Path -Leaf $ToolProjectRoot) -like '*_travail'
if (-not $Sandbox) {
    throw 'Run this deployment script from the sandbox project morfTools_travail.'
}

$ExcludeDirs = @('.git', '.pio', 'build', 'build-mingw', 'dist', '.vscode', '.agents', '.claude', '.vs', 'out')
$Projects = @($Manifest.projects | ForEach-Object { [string]$_ })
if (-not $SkipToolProject) {
    # morfTools itself is intentionally not in ecosystem.json: the manifest
    # describes managed components, while this script deploys its own project too.
    $Projects += (Split-Path -Leaf $ToolProjectRoot) -replace '_travail$', ''
}

if ($WhatIfPreference) { $DryRun = $true }
Write-Host "Source:      $SourceRoot"
Write-Host "Destination: $DestinationRoot"
Write-Host "Mode:        $(if ($DryRun) { 'Dry run' } else { 'Execute' })"

foreach ($CanonicalName in $Projects) {
    $SandboxName = "${CanonicalName}_travail"
    if ($CanonicalName -eq ((Split-Path -Leaf $ToolProjectRoot) -replace '_travail$', '')) {
        $SourceProject = $ToolProjectRoot
    } else {
        $SourceProject = Join-Path $SourceRoot $SandboxName
    }
    $DestinationProject = Join-Path $DestinationRoot $CanonicalName

    if (-not (Test-Path -LiteralPath $SourceProject -PathType Container)) {
        Write-Warning "[SKIP] $SandboxName is absent from the sandbox."
        continue
    }

    Write-Host "[$CanonicalName] $SourceProject -> $DestinationProject"
    if ($DryRun) {
        Write-Host '  [DRY RUN] Content would be copied; destination .git would be preserved.'
        continue
    }
    if (-not $PSCmdlet.ShouldProcess($DestinationProject, "Synchronize $CanonicalName")) { continue }

    New-Item -ItemType Directory -Force -Path $DestinationProject | Out-Null
    $RobocopyArgs = @(
        $SourceProject, $DestinationProject,
        '/E', '/FFT', '/MT:16', '/R:2', '/W:1', '/COPY:DAT',
        '/XD'
    ) + $ExcludeDirs + @('/NFL', '/NDL', '/NP')
    & robocopy @RobocopyArgs | Out-Null
    if ($LASTEXITCODE -ge 8) {
        throw "Robocopy failed for $CanonicalName (exit code $LASTEXITCODE). No further projects were processed."
    }
}

Write-Host 'Synchronization completed. Existing destination .git directories were excluded and preserved.'

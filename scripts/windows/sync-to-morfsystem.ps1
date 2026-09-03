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

$ExcludeDirs = @('.git', '.pio', 'build', 'build-mingw', 'build-arm64', 'build-arm64-cross', 'dist', '.vscode', '.agents', '.claude', '.codex', '.vs', 'out')
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

# --- Personal notes tree: .morfredus_travail -> .morfredus -------------------
# Not a project in ecosystem.json, so promoted here explicitly: a personal folder
# (session logs, working notes) that follows the same '_travail' -> prod naming as
# the projects. Same excludes and same dry-run/WhatIf handling; the destination
# .git (if any) is preserved like everywhere else.
$PersonalSource = Join-Path $SourceRoot '.morfredus_travail'
$PersonalDest   = Join-Path $DestinationRoot '.morfredus'
if (Test-Path -LiteralPath $PersonalSource -PathType Container) {
    Write-Host "[.morfredus] $PersonalSource -> $PersonalDest"
    if ($DryRun) {
        Write-Host '  [DRY RUN] Content would be copied; destination .git would be preserved.'
    } elseif ($PSCmdlet.ShouldProcess($PersonalDest, 'Synchronize .morfredus')) {
        New-Item -ItemType Directory -Force -Path $PersonalDest | Out-Null
        $PersonalArgs = @(
            $PersonalSource, $PersonalDest,
            '/E', '/FFT', '/MT:16', '/R:2', '/W:1', '/COPY:DAT',
            '/XD'
        ) + $ExcludeDirs + @('/NFL', '/NDL', '/NP')
        & robocopy @PersonalArgs | Out-Null
        if ($LASTEXITCODE -ge 8) {
            throw ".morfredus robocopy failed (exit code $LASTEXITCODE)."
        }
    }
} else {
    Write-Warning '[SKIP] .morfredus_travail is absent from the sandbox.'
}

Write-Host 'Synchronization completed. Existing destination .git directories were excluded and preserved.'

# --- Restore the executable bit in the promoted trees ------------------------
# robocopy /COPY:DAT copies data, attributes and timestamps -- never the Unix
# executable bit, which Windows does not have. Left alone, every promoted repo
# commits its scripts as 100644, so a fresh clone on the Pi answers 'Permission
# denied' and 'morf doctor' fails on exec-bits. The fix belongs here, at the one
# place the bit is lost.
#
# exec-bits.py STAGES the mode (git update-index --chmod=+x), which is
# fileMode-independent and survives the promotion commit's `git add -A` (verified
# on Windows). It does not commit -- that stays your call, with the rest of the
# promotion. Push is what makes it permanent: without it the remote keeps 100644
# and the next pull strips the bit again.
$ExecBits = Join-Path $ToolProjectRoot 'scripts\exec-bits.py'
if (-not $DryRun -and (Test-Path -LiteralPath $ExecBits)) {
    $py = (Get-Command python3 -ErrorAction SilentlyContinue) ?? (Get-Command python -ErrorAction SilentlyContinue)
    if ($py) {
        Write-Host ''
        Write-Host 'Restoring the executable bit across the promoted repositories...'
        & $py.Source $ExecBits $DestinationRoot
        Write-Host ''
        Write-Host 'The executable bit is STAGED in each promoted repo. It will ride your'
        Write-Host 'promotion commit; make it permanent by pushing -- otherwise the next'
        Write-Host 'pull on Linux strips it again. From the destination morfTools:'
        Write-Host '    python3 morf.py commit -m "chore: promotion"'
        Write-Host '    python3 morf.py push'
    } else {
        Write-Warning 'python3 not found: executable bit NOT restored. Run exec-bits.py by hand in the destination.'
    }
}

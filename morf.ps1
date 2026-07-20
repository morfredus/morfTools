[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('clone', 'fetch', 'pull', 'build', 'install', 'update', 'upgrade', 'doctor', 'clean', 'status', 'commit', 'push')]
    [string]$Command,
    [string]$Message,
    [Alias('Profile')]
    [string]$Preset
)

$ErrorActionPreference = 'Stop'
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$ManifestPath = Join-Path $PSScriptRoot 'ecosystem.json'
if (-not (Test-Path -LiteralPath $ManifestPath)) { throw "Manifest not found: $ManifestPath" }
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$IsSandbox = (Split-Path -Leaf $PSScriptRoot) -like '*_travail'
if ($Preset -and $Command -notin @('build', 'upgrade')) {
    throw '-Preset is only supported by build and upgrade.'
}

function Get-LocalProjectName([string]$Name) {
    if ($IsSandbox) { return "${Name}_travail" }
    return $Name
}

$Failed = [System.Collections.Generic.List[string]]::new()

# cmake/git/pio are native executables: their exit code must be checked
# explicitly, otherwise a failure goes unnoticed and the next step still runs
# (a build launched on a failed configure -> stale directory tree).
function Invoke-Native {
    $Exe = $args[0]
    # $args[1..0] would reverse instead of yielding an empty array: isolated case.
    $Rest = if ($args.Count -gt 1) { $args[1..($args.Count - 1)] } else { @() }
    & $Exe @Rest
    if ($LASTEXITCODE -ne 0) { throw "$Exe $Rest failed (exit code $LASTEXITCODE)" }
}

# Configure presets declared by a project (empty when it has none).
function Get-ProjectPresets([string]$ProjectPath) {
    $File = Join-Path $ProjectPath 'CMakePresets.json'
    if (-not (Test-Path -LiteralPath $File)) { return @() }
    try { $Data = Get-Content -LiteralPath $File -Raw | ConvertFrom-Json }
    catch { return @() }
    return @($Data.configurePresets | Where-Object { $_.name -and -not $_.hidden } | ForEach-Object { $_.name })
}

function Test-Interactive {
    return [Environment]::UserInteractive -and -not [Console]::IsInputRedirected
}

# A required option is never guessed: offer the alternatives instead.
function Select-Preset {
    $Names = [System.Collections.Generic.List[string]]::new()
    $Counts = @{}
    $Total = 0
    foreach ($Project in $Manifest.projects) {
        $ProjectPath = Join-Path $RepositoryRoot (Get-LocalProjectName $Project)
        $Found = Get-ProjectPresets $ProjectPath
        if ($Found.Count -eq 0) { continue }
        $Total++
        foreach ($Name in $Found) {
            if (-not $Counts.ContainsKey($Name)) { $Names.Add($Name); $Counts[$Name] = 0 }
            $Counts[$Name]++
        }
    }
    if ($Names.Count -eq 0) { return '' }   # no CMake project cloned

    Write-Host "No preset given for '$Command'. Available presets:"
    for ($i = 0; $i -lt $Names.Count; $i++) {
        Write-Host ('  {0}) {1,-20} ({2}/{3} projects)' -f ($i + 1), $Names[$i], $Counts[$Names[$i]], $Total)
    }
    if (-not (Test-Interactive)) {
        throw 'Not a terminal: rerun with -Preset <name>.'
    }
    while ($true) {
        $Reply = Read-Host "Choice [1-$($Names.Count)]"
        $Index = 0
        if ([int]::TryParse($Reply, [ref]$Index) -and $Index -ge 1 -and $Index -le $Names.Count) {
            $Chosen = $Names[$Index - 1]
            Write-Host "[INFO] selected preset: $Chosen"
            return $Chosen
        }
        Write-Host 'Invalid answer.'
    }
}

# A preset missing from THIS project (e.g. linux-arm64-cross, declared by 3
# repositories only) is a normal absence, not a build failure.
function Invoke-CMakeBuild([string]$Preset) {
    if (-not $Preset) {
        Invoke-Native cmake -S . -B build
        Invoke-Native cmake --build build
    }
    elseif ((Get-ProjectPresets '.') -contains $Preset) {
        Invoke-Native cmake --preset $Preset
        Invoke-Native cmake --build --preset $Preset
    }
    else {
        Write-Host "[SKIP] preset '$Preset' not defined in this project"
    }
}

function Invoke-ProjectCommand([string]$Name, [scriptblock]$Action) {
    $Path = Join-Path $RepositoryRoot $Name
    if (-not (Test-Path -LiteralPath $Path)) { Write-Host "[SKIP] $Name (not cloned)"; return }
    Write-Host "[$Name]"
    Push-Location -LiteralPath $Path
    # A failing project must not stop the remaining projects.
    try { & $Action }
    catch { Write-Host "[FAIL] $Name : $($_.Exception.Message)"; $script:Failed.Add($Name) }
    finally { Pop-Location }
}

if ($Command -in @('build', 'upgrade') -and -not $Preset) { $Preset = Select-Preset }
if ($Command -eq 'commit' -and -not $Message) {
    if (-not (Test-Interactive)) { throw 'Use -Message to provide the commit message.' }
    while (-not $Message) { $Message = Read-Host 'Commit message' }
}

foreach ($Project in $Manifest.projects) {
    $LocalProject = Get-LocalProjectName $Project
    $Path = Join-Path $RepositoryRoot $LocalProject
    switch ($Command) {
        'clone' {
            if (Test-Path -LiteralPath $Path) { Write-Host "[SKIP] $LocalProject (already present)"; break }
            $Url = $Manifest.cloneUrlTemplate.Replace('{name}', $LocalProject)
            & git clone --branch $Manifest.branch $Url $Path
        }
        'fetch' { Invoke-ProjectCommand $LocalProject { git fetch --prune } }
        'pull' { Invoke-ProjectCommand $LocalProject { git pull --ff-only origin $Manifest.branch } }
        'update' { Invoke-ProjectCommand $LocalProject { git pull --ff-only origin $Manifest.branch } }
        'upgrade' { Invoke-ProjectCommand $LocalProject { Invoke-Native git pull --ff-only origin $Manifest.branch; if (Test-Path 'CMakeLists.txt') { Invoke-CMakeBuild $Preset } } }
        'status' { Invoke-ProjectCommand $LocalProject { git status --short --branch } }
        'push' { Invoke-ProjectCommand $LocalProject { git push origin $Manifest.branch } }
        'commit' {
            Invoke-ProjectCommand $LocalProject { Invoke-Native git add -A; if (git status --porcelain) { Invoke-Native git commit -m $Message } else { Write-Host '[SKIP] no changes' } }
        }
        'build' { Invoke-ProjectCommand $LocalProject { if (Test-Path 'platformio.ini') { if ($Preset) { Write-Host "[INFO] preset ignored for PlatformIO: $Preset" }; Invoke-Native pio run } elseif (Test-Path 'CMakeLists.txt') { Invoke-CMakeBuild $Preset } else { Write-Host '[SKIP] no known build definition' } } }
        'install' { Invoke-ProjectCommand $LocalProject { if (Test-Path 'requirements.txt') { python -m pip install -r requirements.txt } else { Write-Host '[SKIP] no generic install definition' } } }
        'clean' { Invoke-ProjectCommand $LocalProject { foreach ($Dir in @(Get-ChildItem -Directory -Filter 'build*' | Where-Object { $_.Name -eq 'build' -or $_.Name -like 'build-*' })) { Write-Host "[RM] $($Dir.Name)"; Remove-Item -LiteralPath $Dir.FullName -Recurse -Force } } }
        'doctor' {
            if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'git is not available.' }
            if (-not (Test-Path -LiteralPath $Path)) { Write-Host "[WARN] $LocalProject is missing"; break }
            Invoke-ProjectCommand $LocalProject {
                if (-not (Test-Path '.git')) { Write-Host '[WARN] not a Git repository'; return }
                $Remote = git remote get-url origin 2>$null
                # GitHub resolves repository names case-insensitively, so a
                # spelling difference alone is not a wrong origin. -match is
                # already case-insensitive in PowerShell; kept explicit here.
                if ($Remote -imatch [regex]::Escape($LocalProject)) { Write-Host '[OK] remote name matches' } else { Write-Host "[WARN] unexpected origin: $Remote" }
            }
        }
    }
}

if ($Failed.Count -gt 0) {
    Write-Host ''
    Write-Error "$Command failed on: $($Failed -join ', ')"
    exit 1
}

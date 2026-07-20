[CmdletBinding()]
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('clone', 'fetch', 'pull', 'build', 'install', 'update', 'upgrade', 'doctor', 'clean', 'status', 'commit', 'push')]
    [string]$Command,
    [string]$Message,
    [string]$Profile
)

$ErrorActionPreference = 'Stop'
$RepositoryRoot = Split-Path -Parent $PSScriptRoot
$ManifestPath = Join-Path $PSScriptRoot 'ecosystem.json'
if (-not (Test-Path -LiteralPath $ManifestPath)) { throw "Manifest not found: $ManifestPath" }
$Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json
$IsSandbox = (Split-Path -Leaf $PSScriptRoot) -like '*_travail'
if ($Profile -and $Command -notin @('build', 'upgrade')) {
    throw '-Profile is only supported by build and upgrade.'
}

function Get-LocalProjectName([string]$Name) {
    if ($IsSandbox) { return "${Name}_travail" }
    return $Name
}

function Invoke-ProjectCommand([string]$Name, [scriptblock]$Action) {
    $Path = Join-Path $RepositoryRoot $Name
    if (-not (Test-Path -LiteralPath $Path)) { Write-Host "[SKIP] $Name (not cloned)"; return }
    Write-Host "[$Name]"
    Push-Location -LiteralPath $Path
    try { & $Action } finally { Pop-Location }
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
        'upgrade' { Invoke-ProjectCommand $LocalProject { git pull --ff-only origin $Manifest.branch; if (Test-Path 'CMakeLists.txt') { if ($Profile) { cmake --preset $Profile; cmake --build --preset $Profile } else { cmake -S . -B build; cmake --build build } } } }
        'status' { Invoke-ProjectCommand $LocalProject { git status --short --branch } }
        'push' { Invoke-ProjectCommand $LocalProject { git push origin $Manifest.branch } }
        'commit' {
            if (-not $Message) { throw 'Use -Message to provide the commit message.' }
            Invoke-ProjectCommand $LocalProject { git add -A; if (git status --porcelain) { git commit -m $Message } else { Write-Host '[SKIP] no changes' } }
        }
        'build' { Invoke-ProjectCommand $LocalProject { if (Test-Path 'platformio.ini') { if ($Profile) { Write-Host "[INFO] profile ignored for PlatformIO: $Profile" }; pio run } elseif (Test-Path 'CMakeLists.txt') { if ($Profile) { cmake --preset $Profile; cmake --build --preset $Profile } else { cmake -S . -B build; cmake --build build } } else { Write-Host '[SKIP] no known build definition' } } }
        'install' { Invoke-ProjectCommand $LocalProject { if (Test-Path 'requirements.txt') { python -m pip install -r requirements.txt } else { Write-Host '[SKIP] no generic install definition' } } }
        'clean' { Invoke-ProjectCommand $LocalProject { if (Test-Path 'build') { Remove-Item -LiteralPath 'build' -Recurse -Force } } }
        'doctor' {
            if (-not (Get-Command git -ErrorAction SilentlyContinue)) { throw 'git is not available.' }
            if (-not (Test-Path -LiteralPath $Path)) { Write-Host "[WARN] $LocalProject is missing"; break }
            Invoke-ProjectCommand $LocalProject {
                if (-not (Test-Path '.git')) { Write-Host '[WARN] not a Git repository'; return }
                $Remote = git remote get-url origin 2>$null
                if ($Remote -match [regex]::Escape($LocalProject)) { Write-Host '[OK] remote name matches' } else { Write-Host "[WARN] unexpected origin: $Remote" }
            }
        }
    }
}

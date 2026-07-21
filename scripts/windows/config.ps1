<#
.SYNOPSIS
    Point d'entree unique pour le deploiement des configurations du parc.

.DESCRIPTION
    Equivalent Windows de scripts/linux/config.sh.

    Deux natures de configuration, et elles n'appartiennent pas au meme endroit :

      Shared   %ProgramData%\morfSystem\morfsystem.json — decrit CE QUI EST
               SUPERVISE et est lu par morfMonitor *et* RaspberryDashboard.
               Aucun composant ne le possede, donc morfTools s'en charge.

      Deploy   la configuration PROPRE d'un projet (morfmonitor.json,
               morfsensor.json...). Chaque projet possede son fichier, son
               dossier d'installation et le nom de sa tache. Cette commande
               DELEGUE donc au script du projet plutot que de connaitre tout
               cela — comme « morf build » delegue au systeme de build de
               chaque projet au lieu d'apprendre CMake et PlatformIO.

    Consequence a preserver : un projet clone seul deploie sa configuration
    sans morfTools. Rien ici n'est un prerequis.

.EXAMPLE
    .\config.ps1 shared Status
    .\config.ps1 deploy                # liste les projets qui le supportent
    .\config.ps1 deploy morfMonitor
#>
[CmdletBinding()]
param(
    [Parameter(Position = 0)]
    [ValidateSet('shared', 'deploy', 'help')]
    [string]$Command = 'help',

    [Parameter(Position = 1, ValueFromRemainingArguments = $true)]
    [string[]]$Rest = @()
)

$ErrorActionPreference = 'Stop'
$toolRoot  = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
$workspace = Split-Path -Parent $toolRoot
$sandbox   = (Split-Path -Leaf $toolRoot) -like '*_travail'
$manifest  = Join-Path $toolRoot 'ecosystem.json'

function Get-LocalName([string]$Name) {
    if ($sandbox) { return "${Name}_travail" }
    return $Name
}

function Get-DeployScript([string]$Project) {
    $p = Join-Path $workspace (Join-Path (Get-LocalName $Project) 'scripts\windows\deploy-config.ps1')
    if (Test-Path -LiteralPath $p -PathType Leaf) { return $p }
    return $null
}

switch ($Command) {

'shared' {
    & (Join-Path $PSScriptRoot 'shared-config.ps1') @Rest
}

'deploy' {
    $target = if ($Rest.Count -gt 0) { $Rest[0] } else { $null }
    $projects = (Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json).projects

    if (-not $target) {
        Write-Host "Projects providing a configuration deployment script:"
        $found = $false
        foreach ($p in $projects) {
            if (Get-DeployScript $p) { Write-Host "    $p"; $found = $true }
        }
        if (-not $found) { Write-Host "    (none — clone a project first)" }
        Write-Host ""
        # Un nom de projet est exige plutot qu'un defaut « tous » : la commande
        # ecrase des configurations deployees, et le faire pour tout le parc
        # parce qu'un argument manque n'est pas un defaut raisonnable.
        Write-Host "Name one:  .\config.ps1 deploy <project>"
        exit 0
    }

    $script = Get-DeployScript $target
    if (-not $script) {
        Write-Error ("No deployment script for '{0}'.`nExpected: {1}\scripts\windows\deploy-config.ps1`nRun '.\config.ps1 deploy' to list the projects that provide one." -f $target, (Get-LocalName $target))
        exit 1
    }
    Write-Host "[$target] $script"
    $forward = if ($Rest.Count -gt 1) { $Rest[1..($Rest.Count - 1)] } else { @() }
    & $script @forward
}

default {
    Write-Host "Usage: config.ps1 <command>"
    Write-Host ""
    Write-Host "  shared <action>    Manage the shared parc configuration"
    Write-Host "                     (%ProgramData%\morfSystem\morfsystem.json)."
    Write-Host "                     Actions: Status | Validate | Edit | Diff | Install"
    Write-Host ""
    Write-Host "  deploy [project]   Deploy a project's OWN configuration by running its"
    Write-Host "                     deploy-config script. Without a project name, lists"
    Write-Host "                     the projects that provide one."
}

}

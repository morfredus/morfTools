[CmdletBinding()]
param(
    [ValidateSet('Status', 'Validate', 'Edit', 'Diff', 'Install')]
    [string]$Action = 'Status',
    [string]$ConfigPath = (Join-Path $env:ProgramData 'morfSystem\morfsystem.json')
)

& "$PSScriptRoot/scripts/windows/shared-config.ps1" @PSBoundParameters

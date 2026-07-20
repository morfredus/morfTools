[CmdletBinding()]
param(
    [Alias('Profile')]
    [string]$Preset
)

& "$PSScriptRoot/morf.ps1" build -Preset $Preset

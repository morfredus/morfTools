[CmdletBinding()]
param(
    [Alias('Profile')]
    [string]$Preset
)

& "$PSScriptRoot/morf.ps1" upgrade -Preset $Preset

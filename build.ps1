[CmdletBinding()]
param([string]$Profile)

& "$PSScriptRoot/morf.ps1" build -Profile $Profile

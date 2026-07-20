[CmdletBinding()]
param([string]$Profile)

& "$PSScriptRoot/morf.ps1" upgrade -Profile $Profile

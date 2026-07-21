#Requires -Version 7.0
param([Parameter(ValueFromRemainingArguments)] $Args)
$root = (Resolve-Path "$PSScriptRoot/..").Path
python3 "$PSScriptRoot/scripts/exec-bits.py" $root @Args
exit $LASTEXITCODE

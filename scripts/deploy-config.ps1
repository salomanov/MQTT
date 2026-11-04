#Requires -Version 5.1
<#
.SYNOPSIS
    Развертывание конфигурации Mosquitto на роутер KeeneticOS (Xiaomi R3G v1).
#>
param (
    [string]$RouterHost = "192.168.1.1",
    [int]$SshPort = 222,
    [string]$SshUser = "root",
    [string]$Password = "keenetic",
    [switch]$SkipRestart,
    [switch]$StrictHostKey
)

$PSScript = Join-Path $PSScriptRoot "deploy.py"
$ArgList = @("--host", $RouterHost, "--port", $SshPort, "--user", $SshUser, "--password", $Password)

if ($SkipRestart) {
    $ArgList += "--skip-restart"
}
if ($StrictHostKey) {
    $ArgList += "--strict-host-key"
}

python $PSScript @ArgList
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

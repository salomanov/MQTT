#Requires -Version 5.1
<#
.SYNOPSIS
    Создание резервной копии конфигурации Mosquitto с роутера KeeneticOS.
#>
param (
    [string]$RouterHost = "192.168.1.1",
    [int]$SshPort = 222,
    [string]$SshUser = "root",
    [string]$Password = "keenetic",
    [string]$TargetDir = ""
)

$PSScript = Join-Path $PSScriptRoot "backup.py"
$ArgList = @("--host", $RouterHost, "--port", $SshPort, "--user", $SshUser, "--password", $Password)

if ($TargetDir) {
    $ArgList += @("--target-dir", $TargetDir)
}

python $PSScript @ArgList
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

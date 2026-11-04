#Requires -Version 5.1
<#
.SYNOPSIS
    Проверка доступности и работоспособности MQTT-брокера.
#>
param (
    [string]$BrokerHost = "192.168.1.1",
    [int]$Port = 1883,
    [string]$Topic = "router/test/ping",
    [string]$User = "",
    [string]$Password = ""
)

$PSScript = Join-Path $PSScriptRoot "test_broker.py"
$ArgList = @("--host", $BrokerHost, "--port", $Port, "--topic", $Topic)

if ($User) {
    $ArgList += @("--user", $User, "--password", $Password)
}

python $PSScript @ArgList
if ($LASTEXITCODE -ne 0) {
    exit $LASTEXITCODE
}

$ErrorActionPreference = 'Stop'

$scriptPath = Join-Path $PSScriptRoot 'daily_health_report.py'
$pythonPath = (Get-Command python -ErrorAction Stop).Source
$arguments = '"' + $scriptPath + '"'
$action = New-ScheduledTaskAction -Execute $pythonPath -Argument $arguments -WorkingDirectory $PSScriptRoot
$trigger = New-ScheduledTaskTrigger -Daily -At '8:00 AM'
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable

Register-ScheduledTask `
    -TaskName 'Integration Health Daily Report' `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -Description 'Generate a daily report of third-party integration request health.' `
    -Force | Out-Null

Write-Output 'Scheduled Integration Health Daily Report for 8:00 AM.'
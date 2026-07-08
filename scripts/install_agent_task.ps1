# ============================================
# Employee Tracker - Install Agent Task
# ============================================

# Detect project root automatically
$ScriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectPath = Split-Path -Parent $ScriptDirectory

$Python = Join-Path $ProjectPath "venv\Scripts\python.exe"
$Watchdog = Join-Path $ProjectPath "watchdog_service.py"

$TaskName = "EmployeeTrackerAgent"

# Validate files
if (!(Test-Path $Watchdog)) {
    Write-Host "watchdog_service.py not found"
    exit 1
}


$Action = New-ScheduledTaskAction `
    -Execute $Python `
    -Argument "`"$Watchdog`""

$Trigger = New-ScheduledTaskTrigger -AtStartup

$Principal = New-ScheduledTaskPrincipal `
    -UserId "SYSTEM" `
    -RunLevel Highest

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action $Action `
    -Trigger $Trigger `
    -Principal $Principal `
    -Force

Write-Host ""
Write-Host "======================================="
Write-Host "Employee Tracker Agent Installed"
Write-Host "======================================="
Write-Host "Project : $ProjectPath"
Write-Host "Python  : $Python"
Write-Host "Watchdog : $Watchdog"
Write-Host ""
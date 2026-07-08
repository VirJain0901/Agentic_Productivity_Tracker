$TaskName = "EmployeeTrackerAgent"

if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {

    Unregister-ScheduledTask `
        -TaskName $TaskName `
        -Confirm:$false

    Write-Host "Employee Tracker Agent removed."

}
else {

    Write-Host "Task not found."

}
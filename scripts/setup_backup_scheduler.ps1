# GentleΩ Backup Guard Service
# Windows Task Scheduler Configuration

$TaskName = "GentleOmega-BackupGuard"
$TaskDescription = "Hourly backup and storage validation for GentleΩ system"
$ScriptPath = "D:\GentleOmega\scripts\backup_guard.py"
$LogPath = "D:\GentleOmega\logs\backup_guard_scheduler.log"

# Create the task action
$Action = New-ScheduledTaskAction -Execute "python" -Argument $ScriptPath -WorkingDirectory "D:\GentleOmega\scripts"

# Create the trigger (every hour)
$Trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Hours 1) -RepetitionDuration (New-TimeSpan -Days 365)

# Create the principal (run as SYSTEM with highest privileges)
$Principal = New-ScheduledTaskPrincipal -UserId "SYSTEM" -LogonType ServiceAccount -RunLevel Highest

# Create task settings
$Settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable -RunOnlyIfNetworkAvailable

# Register the scheduled task
try {
    Register-ScheduledTask -TaskName $TaskName -Action $Action -Trigger $Trigger -Principal $Principal -Settings $Settings -Description $TaskDescription -Force
    Write-Host "✅ Backup Guard scheduled task created successfully" -ForegroundColor Green
    Write-Host "Task will run every hour to maintain backups and storage policy" -ForegroundColor Cyan
} catch {
    Write-Host "❌ Failed to create scheduled task: $($_.Exception.Message)" -ForegroundColor Red
}

# Start the task immediately for testing
try {
    Start-ScheduledTask -TaskName $TaskName
    Write-Host "✅ Backup Guard task started for initial run" -ForegroundColor Green
} catch {
    Write-Host "⚠️ Failed to start task immediately: $($_.Exception.Message)" -ForegroundColor Yellow
}
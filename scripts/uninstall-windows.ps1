#Requires -RunAsAdministrator

$ServiceName = "AWatch Agent"
$InstallDir = "C:\Program Files\awatch"
$ConfigDir = "C:\ProgramData\awatch"

Write-Host "Stopping service..."
Stop-Service -Name $ServiceName -ErrorAction SilentlyContinue

Write-Host "Removing service..."
$PSVersion = $PSVersionTable.PSVersion.Major
if ($PSVersion -ge 6) {
    Remove-Service -Name $ServiceName -ErrorAction SilentlyContinue
} else {
    sc.exe delete "$ServiceName" | Out-Null
}

Write-Host "Removing installation directory..."
Remove-Item -Path $InstallDir -Recurse -Force -ErrorAction SilentlyContinue

$RemoveConfig = Read-Host "Remove configuration at $ConfigDir? [y/N]"
if ($RemoveConfig -eq "y" -or $RemoveConfig -eq "Y") {
    Remove-Item -Path $ConfigDir -Recurse -Force -ErrorAction SilentlyContinue
    Write-Host "Configuration removed."
}

Write-Host ""
Write-Host "Awatch agent uninstalled."

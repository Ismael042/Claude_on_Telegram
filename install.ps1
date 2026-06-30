# Registra o bot no Agendador de Tarefas para iniciar automaticamente no logon.
# Execute este script UMA vez. Para remover: uninstall.ps1

$ProjectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$PythonW    = Join-Path $ProjectDir ".venv\Scripts\pythonw.exe"
$TrayScript = Join-Path $ProjectDir "tray.py"
$TaskName   = "TelegramClaudeBot"

if (-not (Test-Path $PythonW)) {
    Write-Host "ERRO: $PythonW nao encontrado. Crie o venv primeiro." -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $TrayScript)) {
    Write-Host "ERRO: tray.py nao encontrado em $ProjectDir" -ForegroundColor Red
    exit 1
}

$Action   = New-ScheduledTaskAction -Execute "`"$PythonW`"" `
                                    -Argument "`"$TrayScript`"" `
                                    -WorkingDirectory $ProjectDir
$Trigger  = New-ScheduledTaskTrigger -AtLogon -User $env:USERNAME
$Settings = New-ScheduledTaskSettingsSet `
                -ExecutionTimeLimit 0 `
                -MultipleInstances IgnoreNew `
                -StartWhenAvailable

Register-ScheduledTask `
    -TaskName $TaskName `
    -Action   $Action `
    -Trigger  $Trigger `
    -Settings $Settings `
    -RunLevel Limited `
    -Force | Out-Null

Write-Host ""
Write-Host "Bot registrado como '$TaskName' no Agendador de Tarefas." -ForegroundColor Green
Write-Host "Iniciara automaticamente ao fazer login no Windows." -ForegroundColor Cyan
Write-Host ""
Write-Host "Iniciando agora..." -ForegroundColor Yellow
Start-ScheduledTask -TaskName $TaskName
Start-Sleep -Seconds 2
Write-Host "Pronto. Procure o icone na bandeja do sistema (canto direito da barra de tarefas)." -ForegroundColor Green
Write-Host "Clique duas vezes no icone para ver os logs." -ForegroundColor Cyan

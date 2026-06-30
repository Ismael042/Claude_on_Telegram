# Remove o bot do Agendador de Tarefas.

$TaskName = "TelegramClaudeBot"

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if (-not $task) {
    Write-Host "Tarefa '$TaskName' nao encontrada." -ForegroundColor Yellow
    exit 0
}

Stop-ScheduledTask  -TaskName $TaskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false

Write-Host "Bot removido do Agendador de Tarefas." -ForegroundColor Green

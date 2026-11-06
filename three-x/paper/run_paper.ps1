# AMD paper books: fetch Robinhood prices read-only, replay the five books, notify on buys and sells.
# Paper only. The headless session gets read-only Robinhood tools plus Write, and .claude/settings.json denies every order tool.
# Usage: run_paper.ps1 open | close
param([Parameter(Mandatory = $true)][ValidateSet("open", "close")][string]$Mode)
$ErrorActionPreference = "Continue"
$repo = "E:\stocks-automation"
$box = "$repo\three-x\paper"
$log = "$box\run_log.txt"
$python = "E:\strategy-repos\venvs\vt\Scripts\python.exe"
$claude = "C:\Users\My PC\.local\bin\claude.exe"
function Log($m) { Add-Content -Path $log -Value "$((Get-Date).ToString('yyyy-MM-dd HH:mm:ss')) [$Mode] $m" -Encoding utf8 }
function Notify($text) {
    try {
        [void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
        $xml = [Windows.UI.Notifications.ToastNotificationManager]::GetTemplateContent([Windows.UI.Notifications.ToastTemplateType]::ToastText02)
        $nodes = $xml.GetElementsByTagName("text")
        [void]$nodes.Item(0).AppendChild($xml.CreateTextNode("AMD paper trading"))
        [void]$nodes.Item(1).AppendChild($xml.CreateTextNode($text))
        $app = "{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe"
        [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($xml))
    } catch { Log "toast failed: $_" }
    & msg.exe $env:USERNAME $text 2>$null
    Log "notified: $text"
}

$guard = (& $python "$repo\day-trading\plan\market_calendar.py" 2>&1 | Out-String)
if ($guard -notmatch "TRADING|NO-TRADE" -or $guard -match "ERROR") { Notify "AMD paper: calendar error, no run today. See run_log.txt."; Log "calendar error: $guard"; exit 1 }
if ($guard -notmatch "(?m)^TRADING") { Log "not a trading day"; exit 0 }

Log "start"
Remove-Item "$box\rh_snapshot.json" -ErrorAction SilentlyContinue
Set-Location $repo
$tools = "mcp__robinhood-trading__get_equity_quotes,mcp__robinhood-trading__get_equity_historicals,mcp__robinhood-trading__get_earnings_results,Write"
$prompt = "Read E:\stocks-automation\three-x\paper\fetch_prompt.txt and follow it exactly. It is a read-only price fetch for paper trading."
$claudeArgs = "-p `"$prompt`" --model claude-sonnet-5-5 --permission-mode acceptEdits --allowedTools `"$tools`" --max-turns 12"
$p = Start-Process -FilePath $claude -ArgumentList $claudeArgs -WorkingDirectory $repo -WindowStyle Hidden -PassThru -RedirectStandardOutput "$box\fetch_out.txt" -RedirectStandardError "$box\fetch_err.txt"
if (-not $p.WaitForExit(300000)) { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue; Log "fetch timed out" }
if (-not (Test-Path "$box\rh_snapshot.json")) { Notify "AMD paper: Robinhood fetch failed, using yfinance prices today. See run_log.txt."; Log "no snapshot: $(Get-Content "$box\fetch_err.txt" -Raw)" }

Set-Location "$repo\three-x"
$env:PYTHONIOENCODING = "utf-8"
& $python -W ignore amd_paper.py run $Mode 2>&1 | ForEach-Object { "$_" } | Out-File -FilePath $log -Append -Encoding utf8
if ($LASTEXITCODE -ne 0) { Notify "AMD paper: the $Mode run failed. See run_log.txt."; Log "failed, exit $LASTEXITCODE"; exit 1 }

if (Test-Path "$box\notify_queue.txt") {
    $lines = Get-Content "$box\notify_queue.txt" -Encoding utf8
    Remove-Item "$box\notify_queue.txt"
    foreach ($line in $lines) { if ($line) { Notify $line } }
}

if ($Mode -eq "close") {
    Set-Location $repo
    $paths = @("three-x/paper/ledger.csv", "three-x/paper/equity.csv", "three-x/paper/status.md", "three-x/paper/seen.json", "three-x/paper/bars_AMD.csv", "three-x/paper/bars_QQQ.csv", "three-x/paper/opens.csv", "three-x/paper/reports.json")
    $present = $paths | Where-Object { Test-Path "$repo\$_" }
    & git add -- $present 2>$null
    $staged = & git diff --cached --name-only -- $present
    if ($staged) {
        $day = (Get-Date).ToString("yyyy-MM-dd")
        & git commit -q -m "AMD paper books: $day close" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>" -- $present 2>&1 | Out-Null
        & git push -q origin main 2>&1 | Out-Null
        if ($LASTEXITCODE -ne 0) { Log "git push failed; the commit is local" }
    }
}
Log "done"

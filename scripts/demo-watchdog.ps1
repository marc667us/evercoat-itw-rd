<#
  Keep the demonstration stack reachable, and keep the CURRENT URL somewhere
  findable.

  🔴 WHAT THIS CAN AND CANNOT PROMISE.

  It CAN keep the app running: if the site stops answering it re-runs
  `demo-up.ps1`, which rebuilds the stack and mints a working tunnel.

  It CANNOT promise the same LINK for 24 hours. A Cloudflare *quick* tunnel
  gets a random hostname that is issued fresh every time cloudflared starts,
  so any repair changes the address. That is a property of quick tunnels, not
  a bug in this script, and no amount of watchdogging fixes it.

  The real fix is a NAMED tunnel (`cloudflared tunnel login` once, then
  `demo-up.ps1 -TunnelName evercoat -NamedHostname <host>`), which pins the
  hostname permanently. That needs a Cloudflare account and one interactive
  login, so it is the operator's call rather than something this script does.

  Until then this writes the live URL to TWO places every cycle, so the current
  address is always findable without reading a log:

      Desktop\EVERCOAT-LIVE-URL.txt
      tmp\demo\current_url.txt

  ⚠️ IT IS DELIBERATELY SLOW TO ACT. Three consecutive failures, 5 minutes
  apart, before it touches anything -- because `demo-up.ps1` restarts the whole
  stack, and doing that on one dropped request would be worse than the outage.
  A live test suite run takes ~25 minutes and must not be interrupted by a
  watchdog reacting to a single blip.

  Usage (detached, survives the session):
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\demo-watchdog.ps1
#>

param(
    [string]$RepoRoot = "C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP",
    [int]$IntervalSeconds = 300,
    [int]$FailuresBeforeRepair = 3,
    [int]$HoursToRun = 24
)

$ErrorActionPreference = "Continue"
$logDir = Join-Path $RepoRoot "tmp\demo"
$watchLog = Join-Path $logDir "watchdog.log"
$urlFileRepo = Join-Path $logDir "current_url.txt"
$urlFileDesktop = "C:\Users\USER\Desktop\EVERCOAT-LIVE-URL.txt"

function Write-Line([string]$text) {
    $stamped = "{0}  {1}" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $text
    Add-Content -Path $watchLog -Value $stamped -Encoding utf8
}

function Get-TunnelUrl {
    $log = Join-Path $logDir "cloudflared.err.log"
    if (-not (Test-Path $log)) { return $null }
    $m = Select-String -Path $log -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" -AllMatches
    if (-not $m) { return $null }
    return $m[-1].Matches[-1].Value
}

function Publish-Url([string]$url, [string]$state) {
    $body = @(
        "EvercoatITWRD APP - live demonstration site",
        "",
        "  $url",
        "",
        "Status at $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss') : $state",
        "",
        "Sign in with any of the ten demo users, one per role:",
        "  lead.demo@example.test    (product development lead)",
        "  chem.demo@example.test    (chemist)",
        "  eng.demo@example.test     (engineer)",
        "  dir.demo@example.test     (director)",
        "  qa.demo@example.test      (QA / compliance)",
        "  tech.demo@example.test    (laboratory technician)",
        "  proc.demo@example.test    (procurement)",
        "  prod.demo@example.test    (production engineer)",
        "  exec.demo@example.test    (executive viewer)",
        "  admin.demo@example.test   (administrator)",
        "",
        "Password for all ten:  EvercoatDemo-2026!",
        "",
        "WARNING: this is a Cloudflare QUICK tunnel. If it drops, the watchdog",
        "repairs the stack but the hostname CHANGES -- this file is rewritten",
        "with the new one, so re-read it rather than reusing an old link.",
        "A named tunnel would pin the address permanently and needs one",
        "interactive `cloudflared tunnel login`."
    ) -join "`r`n"
    Set-Content -Path $urlFileRepo -Value $url -Encoding ascii -NoNewline
    Set-Content -Path $urlFileDesktop -Value $body -Encoding utf8
}

$deadline = (Get-Date).AddHours($HoursToRun)
$consecutiveFailures = 0
Write-Line "watchdog started; running until $deadline"

while ((Get-Date) -lt $deadline) {
    $url = Get-TunnelUrl
    $healthy = $false

    if ($url) {
        try {
            $r = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 30 -ErrorAction Stop
            if ($r.StatusCode -eq 200) { $healthy = $true }
        } catch {
            # A DNS blip and a dead origin look different but are handled the
            # same way: one failure is never enough to act on.
            Write-Line "probe failed: $($_.Exception.Message)"
        }
    } else {
        Write-Line "no tunnel hostname in cloudflared.err.log"
    }

    if ($healthy) {
        if ($consecutiveFailures -gt 0) { Write-Line "recovered after $consecutiveFailures failure(s)" }
        $consecutiveFailures = 0
        Publish-Url $url "reachable"
    } else {
        $consecutiveFailures++
        Write-Line "unhealthy ($consecutiveFailures/$FailuresBeforeRepair)"
        if ($url) { Publish-Url $url "NOT REACHABLE - repair pending" }

        if ($consecutiveFailures -ge $FailuresBeforeRepair) {
            Write-Line "repairing: running demo-up.ps1 (the hostname WILL change)"
            & powershell -NoProfile -ExecutionPolicy Bypass `
                -File (Join-Path $RepoRoot "scripts\demo-up.ps1") *>> $watchLog
            Write-Line "repair finished (exit $LASTEXITCODE)"
            $consecutiveFailures = 0
            $newUrl = Get-TunnelUrl
            if ($newUrl) { Publish-Url $newUrl "repaired - NEW hostname" }
        }
    }

    Start-Sleep -Seconds $IntervalSeconds
}

Write-Line "watchdog finished its $HoursToRun-hour window"

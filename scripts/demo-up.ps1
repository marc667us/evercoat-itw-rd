<#
  Bring the demonstration stack up so it OUTLIVES the session that started it.

  🔴 WHY THIS SCRIPT EXISTS.

  The stack has been killed three times by the session's background tasks being
  stopped (twice on 2026-08-23, once on 08-24). The containers always survived
  -- they are not session-owned -- but `cloudflared`, `uvicorn` and `next` did
  not, because they were children of the agent session. `Start-Process`
  detaches them, so they keep running after the session goes away.

  🔴 THE SCRIPT DERIVES THE PUBLIC URL. IT MUST NOT BE TOLD ONE.

  The first version took `-PublicUrl` as a parameter AND restarted cloudflared,
  which mints a NEW random hostname for a quick tunnel. So it configured the
  API and the web bundle against the hostname it had been handed while serving
  traffic on a different one -- every request came back 530, which reads
  exactly like a dead origin when the origin was perfectly healthy.

  A quick tunnel's hostname is not knowable before the tunnel exists, so this
  script starts cloudflared FIRST and reads the hostname back out of its own
  log. Passing a URL in was the bug, not a convenience.

  Usage:
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\demo-up.ps1
    powershell -NoProfile -ExecutionPolicy Bypass -File scripts\demo-up.ps1 -TunnelName evercoat

  With `-TunnelName` (a NAMED tunnel, needs `cloudflared tunnel login` once)
  the hostname is fixed and `-NamedHostname` supplies it. Without it, a quick
  tunnel is created and its hostname discovered.
#>

param(
    [string]$TunnelName = "",
    [string]$NamedHostname = "",
    [string]$RepoRoot = "C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP"
)

# 🔴 NOT "Stop", AND THAT IS DELIBERATE (PowerShell 5.1).
#
# Redirecting a NATIVE executable's stderr inside 5.1 wraps every line in a
# NativeCommandError and sets $? to $false EVEN WHEN THE EXE RETURNED 0. So
# `kcadm.sh` writing its perfectly ordinary "Logging into http://localhost:8080
# as user admin of realm master" to stderr became a TERMINATING error under
# "Stop", and this script died after starting the tunnel but before repointing
# anything -- leaving a live tunnel pointing at an unconfigured stack.
#
# Native failures are checked explicitly via $LASTEXITCODE where it matters.
$ErrorActionPreference = "Continue"
$cloudflared = "C:\Users\USER\cloudflared.exe"
$node        = "C:\Users\USER\nodejs"
$docker      = "C:\Users\USER\AppData\Local\Programs\DockerDesktop\resources\bin\docker.exe"
$logDir      = Join-Path $RepoRoot "tmp\demo"
New-Item -ItemType Directory -Force -Path $logDir | Out-Null

# ---------------------------------------------------------------- containers
# Not session-owned. `unless-stopped` so they also survive a Docker restart.
foreach ($c in @("evercoat-postgres", "evercoat-demo-caddy", "evercoat-demo-keycloak")) {
    try { & $docker start $c | Out-Null } catch { }
    try { & $docker update --restart unless-stopped $c | Out-Null } catch { }
}

# --------------------------------------------------------------------- ports
# 🔴 KILL THE OLD LISTENER FIRST. An API left running from a previous session
# serves STALE CODE -- twice on this project, presenting as 404s for routes
# that plainly exist.
foreach ($port in @(3000, 18000)) {
    $owner = (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
              Select-Object -First 1).OwningProcess
    if ($owner) {
        Write-Host "  stopping stale listener on $port (pid $owner)"
        try { Stop-Process -Id $owner -Force -ErrorAction Stop } catch { }
        Start-Sleep -Seconds 2
    }
}

# -------------------------------------------------------------------- tunnel
Get-Process cloudflared -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Start-Sleep -Seconds 2
$cfOut = Join-Path $logDir "cloudflared.log"
$cfErr = Join-Path $logDir "cloudflared.err.log"
Remove-Item $cfOut, $cfErr -ErrorAction SilentlyContinue

if ($TunnelName) {
    if (-not $NamedHostname) { throw "-TunnelName requires -NamedHostname (the fixed public URL)" }
    $cfArgs = @("tunnel", "--no-autoupdate", "run", "--url", "http://localhost:18081", $TunnelName)
} else {
    $cfArgs = @("tunnel", "--no-autoupdate", "--url", "http://localhost:18081")
}
Start-Process -FilePath $cloudflared -ArgumentList $cfArgs `
    -RedirectStandardOutput $cfOut -RedirectStandardError $cfErr -WindowStyle Hidden

if ($TunnelName) {
    $PublicUrl = $NamedHostname
} else {
    # Read the hostname back out of the tunnel's OWN log. Never assume it.
    $PublicUrl = $null
    foreach ($i in 1..40) {
        Start-Sleep -Seconds 2
        $hit = Select-String -Path @($cfOut, $cfErr) -Pattern "https://[a-z0-9-]+\.trycloudflare\.com" `
                             -ErrorAction SilentlyContinue | Select-Object -First 1
        if ($hit) { $PublicUrl = $hit.Matches[0].Value; break }
    }
    if (-not $PublicUrl) { throw "cloudflared did not report a hostname within 80s" }
}
Write-Host "  tunnel up: $PublicUrl"
# 🔴 `ascii`, NOT `utf8`. PowerShell 5.1's `-Encoding utf8` writes a BOM, and
# this file is read by bash (`$(cat tmp/tunnel_url.txt)`), so the BOM becomes
# part of the URL. Measured: `357 273 277 h t t p s`. It would have been
# compiled into NEXT_PUBLIC_* and into every sign-in redirect, producing a
# bundle whose hostname is invisibly wrong. This machine has been bitten by
# the same BOM before; it is recorded as a hard rule.
Set-Content -Path (Join-Path $RepoRoot "tmp\tunnel_url.txt") -Value $PublicUrl -Encoding ascii -NoNewline

# ------------------------------------------------------------------ keycloak
# 🔴 FOUR THINGS CARRY THE HOSTNAME and all four must move together: the
# client's redirect URIs, KC_HOSTNAME, the API's issuer, and the web bundle.
& $docker exec evercoat-demo-keycloak /opt/keycloak/bin/kcadm.sh config credentials `
    --server http://localhost:8080 --realm master --user admin --password demo-admin-pw | Out-Null
$clientId = (& $docker exec evercoat-demo-keycloak /opt/keycloak/bin/kcadm.sh get clients -r evercoat `
                -q clientId=evercoat-web --fields id --format csv --noquotes) -replace "`r", ""
if (-not $clientId) { throw "could not resolve the evercoat-web client id -- is Keycloak up?" }
# 🔴 THE UPDATE GOES IN AS A JSON FILE, NOT AS `-s` ARGUMENTS.
#
# The `-s "redirectUris=[`"...`"]"` form CANNOT WORK from PowerShell 5.1.
# Passing a string containing embedded double quotes to a NATIVE executable
# goes through a CommandLineToArgvW round-trip that strips them, so kcadm
# received `redirectUris=[https://...,...]` and answered:
#
#     Cannot parse the JSON [unknown_error]
#
# The read-back below caught it -- which is the whole reason the read-back
# exists -- but the call could never have succeeded. Reproduced 2026-08-25
# with a single-element array, so it is the quoting and not the length.
#
# A file has no quoting problem. `ascii` again, never `utf8`: 5.1 writes a
# BOM and a BOM in front of `{` is not JSON either.
$kcBody = [ordered]@{
    redirectUris = @(
        "$PublicUrl/auth/callback/",
        "$PublicUrl/auth/callback",
        "$PublicUrl/*",
        "http://localhost:3000/auth/callback/"
    )
    webOrigins = @("$PublicUrl", "http://localhost:3000")
} | ConvertTo-Json -Compress
$kcFile = Join-Path $RepoRoot "tmp\kc-client-update.json"
Set-Content -Path $kcFile -Value $kcBody -Encoding ascii -NoNewline
if (-not (Test-Path $kcFile)) { throw "could not write $kcFile" }
& $docker cp $kcFile evercoat-demo-keycloak:/tmp/kc-client-update.json | Out-Null
if ($LASTEXITCODE -ne 0) { throw "docker cp of the client body failed ($LASTEXITCODE)" }
& $docker exec evercoat-demo-keycloak /opt/keycloak/bin/kcadm.sh update "clients/$clientId" `
    -r evercoat -f /tmp/kc-client-update.json | Out-Null
$kcUpdateExit = $LASTEXITCODE

# 🔴 READ IT BACK. THE UPDATE IS NOT PROOF THAT THE UPDATE HAPPENED.
#
# `$ErrorActionPreference` is "Continue" here (it has to be -- see the top of
# the file), which means a FAILED kcadm call does not stop the script. That is
# exactly what happened once: the client update silently did nothing, the
# script carried on and reported success, and every browser sign-in died on
# "Invalid parameter: redirect_uri" against a client still holding the
# PREVIOUS tunnel's hostname.
#
# Fixing the stderr trap removed the failure detection with it. So the check
# is explicit now, and it asserts the STORED value rather than the call's
# exit: a check that cannot fail is not a check.
# 🔴 AND IT ASSERTS EVERY VALUE, NOT MERELY THAT THE HOSTNAME APPEARS.
#
# Raised by Codex on 2026-08-25 against the first version of this guard, which
# tested `$stored -notlike "*$PublicUrl*"`. Three ways that is weaker than it
# reads:
#
#   · it never looked at `webOrigins` at all, so a CORS failure would sail
#     through a "verified" line;
#   · it passed if the hostname appeared ANYWHERE, so three of the four
#     redirect URIs could be missing;
#   · with `-TunnelName` the hostname is STABLE, so a completely failed
#     update leaves the previous run's correct-looking value in place and the
#     guard reports success on config it did not write.
#
# 🔴 AND IT PARSES THE JSON RATHER THAN SUBSTRING-MATCHING THE BLOB.
#
# The first attempt at this stronger guard tested `$stored.Contains($value)`
# over the whole response, and it was STILL not a check. Falsified against a
# synthetic config with `webOrigins: []` -- which breaks CORS completely --
# and it PASSED, because every webOrigin is a PREFIX of a redirect URI:
# "http://localhost:3000" is inside "http://localhost:3000/auth/callback/".
# A substring test cannot say WHICH FIELD a value appeared in, so it silently
# graded `webOrigins` against `redirectUris`.
#
# Two guards in a row that read as verification and could not fail. Parse the
# document and assert each field, and note `-contains` is an EXACT element
# match on an array, so a wildcard in the value cannot spread.
$stored = (& $docker exec evercoat-demo-keycloak /opt/keycloak/bin/kcadm.sh get "clients/$clientId" `
              -r evercoat --fields redirectUris,webOrigins) -join ""
$kcClient = $null
try { $kcClient = $stored | ConvertFrom-Json } catch { }
if ($null -eq $kcClient) {
    throw "could not parse the evercoat-web client read-back as JSON. It reads: $stored"
}
$kcWantRedirects = @(
    "$PublicUrl/auth/callback/",
    "$PublicUrl/auth/callback",
    "$PublicUrl/*",
    "http://localhost:3000/auth/callback/"
)
$kcWantOrigins = @("$PublicUrl", "http://localhost:3000")
$kcMissing = @()
$kcMissing += @($kcWantRedirects | Where-Object { $kcClient.redirectUris -notcontains $_ } |
                ForEach-Object { "redirectUris:$_" })
$kcMissing += @($kcWantOrigins   | Where-Object { $kcClient.webOrigins   -notcontains $_ } |
                ForEach-Object { "webOrigins:$_" })
if ($kcUpdateExit -ne 0 -or $kcMissing.Count -gt 0) {
    throw ("the evercoat-web client was NOT repointed (kcadm exit $kcUpdateExit). " +
           "Missing: $($kcMissing -join ', '). It reads: $stored")
}
$kcChecked = $kcWantRedirects.Count + $kcWantOrigins.Count
Write-Host "  keycloak client repointed ($kcChecked/$kcChecked values verified per field by read-back)"

& $docker rm -f evercoat-demo-keycloak | Out-Null
& $docker run -d --restart unless-stopped --name evercoat-demo-keycloak -p 18080:8080 `
    --add-host host.docker.internal:host-gateway `
    -e KC_DB=postgres -e KC_DB_URL="jdbc:postgresql://host.docker.internal:55432/keycloak" `
    -e KC_DB_USERNAME=postgres -e KC_DB_PASSWORD=dev-superuser-pw `
    -e KC_BOOTSTRAP_ADMIN_USERNAME=admin -e KC_BOOTSTRAP_ADMIN_PASSWORD=demo-admin-pw `
    -e KC_HOSTNAME="$PublicUrl/auth" -e KC_HOSTNAME_STRICT=false -e KC_HTTP_ENABLED=true `
    -e KC_PROXY_HEADERS=xforwarded -e KC_HEALTH_ENABLED=true `
    -v "$RepoRoot\services\keycloak\realm:/opt/keycloak/data/import" `
    quay.io/keycloak/keycloak:26.0 start-dev | Out-Null
# 🔴 NEVER memory-cap it. `start-dev` runs a config build first; capped at
# 512 MB it sticks at 497 and never boots. Expect 6-15 min, ONE log line until
# done, memory climbing to ~595 MiB and then DROPPING to ~170 -- that drop is
# the augmentation exiting and the server starting.
Write-Host "  keycloak recreated on $PublicUrl/auth (6-15 min to boot)"

# ----------------------------------------------------------------------- api
$apiCmd = @"
`$env:DATABASE_URL='postgresql+psycopg://evercoat_app:ci-app@localhost:55432/evercoat_itw_rd';
`$env:KEYCLOAK_ISSUER='$PublicUrl/auth/realms/evercoat';
`$env:CORS_ALLOWED_ORIGINS='[\"$PublicUrl\",\"http://localhost:3000\"]';
`$env:APP_ENV='development'; `$env:LOG_FORMAT='console';
Set-Location '$RepoRoot\apps\api';
python -m uvicorn app.main:app --host 0.0.0.0 --port 18000
"@
Start-Process powershell -ArgumentList @("-NoProfile", "-Command", $apiCmd) `
    -RedirectStandardOutput (Join-Path $logDir "api.log") `
    -RedirectStandardError  (Join-Path $logDir "api.err.log") -WindowStyle Hidden
Write-Host "  api started (detached)"

# ----------------------------------------------------------------------- web
# 🔴 BUILD, THEN RUN THE STANDALONE SERVER -- NOT `next start`.
#
# `next.config.mjs` is `output: isExport ? "export" : "standalone"`, so an
# ordinary build produces STANDALONE, and `next start` refuses it:
#
#   ⚠ "next start" does not work with "output: standalone" configuration.
#
# It still printed "Ready in 1204ms" and a "Local: http://localhost:3000"
# line, and bound NOTHING. Port 3000 had zero listeners while the log looked
# like a healthy start -- a success message over a server that does not exist.
# Caught by checking the LISTENER, not the log.
#
# Standalone also does not copy `.next/static` or `public` into itself; the
# server runs but every asset 404s. Both are copied explicitly below.
#
# 🔴 `NEXT_PUBLIC_*` IS INLINED BY THE BUILD, so the hostname is baked in HERE.
# A stale bundle serves a perfect-looking site that cannot sign in.
$webCmd = @"
`$env:PATH='$node;' + `$env:PATH;
`$env:NEXT_PUBLIC_API_BASE_URL='$PublicUrl';
`$env:NEXT_PUBLIC_KEYCLOAK_URL='$PublicUrl/auth';
`$env:NEXT_PUBLIC_KEYCLOAK_REALM='evercoat';
`$env:NEXT_PUBLIC_KEYCLOAK_CLIENT_ID='evercoat-web';
# 🔴 ITS OWN BUILD DIRECTORY. `next build` regenerates `.next/standalone/`,
# which is what this server SERVES -- so a Playwright local run, which builds
# before starting its own web server, silently replaced the demo's bundle with
# one built without NEXT_PUBLIC_*. Twice. The site returned 200 everywhere and
# could not sign in. Separate directories, so neither build can destroy the
# other.
`$env:NEXT_DIST_DIR='.next-demo';
Set-Location '$RepoRoot\apps\web';
npx next build;
Copy-Item -Recurse -Force '.next-demo\static' '.next-demo\standalone\.next-demo\static';
if (Test-Path 'public') { Copy-Item -Recurse -Force 'public' '.next-demo\standalone\public' }
`$env:PORT='3000'; `$env:HOSTNAME='0.0.0.0';
node '.next-demo\standalone\server.js'
"@
Start-Process powershell -ArgumentList @("-NoProfile", "-Command", $webCmd) `
    -RedirectStandardOutput (Join-Path $logDir "web.log") `
    -RedirectStandardError  (Join-Path $logDir "web.err.log") -WindowStyle Hidden
Write-Host "  web building + serving standalone (detached)"

Write-Host ""
Write-Host "PUBLIC URL: $PublicUrl"
Write-Host "All detached -- they outlive this session."
Write-Host "Watch: Get-Content '$logDir\web.log' -Tail 20 -Wait"

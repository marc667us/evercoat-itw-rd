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
#
# 🔴 BUT NAME THE PROCESS BEFORE KILLING IT. THIS BLOCK KILLED explorer.exe.
#
# It used to take `.OwningProcess` from `Get-NetTCPConnection` and hand it
# straight to `Stop-Process -Force`, without ever asking what that process was.
# A PID is not a durable handle: the TCP table can name a process that has
# already exited, and Windows recycles PIDs aggressively. Measured 2026-08-29 --
# this reported "stopping stale listener on 18000 (pid 1744)", and what died
# was the Windows shell. The taskbar and every desktop icon went with it, on a
# machine where nothing about the demo had gone wrong.
#
# `-Force` on an unverified PID is the whole defect. The port is a hint about
# WHICH process to stop, never proof of WHAT it is. So: resolve the PID to a
# real process, check its name against the three things this script is entitled
# to stop, and refuse anything else loudly rather than guessing. A stale
# listener that survives is a visible problem the operator can act on; a
# force-killed shell is not.
$ourProcesses = @("node", "python", "uvicorn", "next-server")
foreach ($port in @(3000, 18000)) {
    $owner = (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue |
              Select-Object -First 1).OwningProcess
    if (-not $owner) { continue }

    # Resolve BEFORE stopping. If the PID no longer exists the table was stale
    # and there is nothing to kill -- which is the case that used to kill
    # whatever had inherited the number.
    $proc = Get-Process -Id $owner -ErrorAction SilentlyContinue
    if (-not $proc) {
        Write-Host "  port $port names pid $owner, which no longer exists (stale entry) -- nothing to stop"
        continue
    }

    if ($ourProcesses -notcontains $proc.ProcessName) {
        Write-Warning (
            "  REFUSING to stop pid $owner on port $port -- it is " +
            "'$($proc.ProcessName)', not one of this stack's own processes " +
            "($($ourProcesses -join ', ')). Stop it yourself if that is really " +
            "what is holding the port. This check exists because an earlier " +
            "version of this line force-killed explorer.exe."
        )
        continue
    }

    Write-Host "  stopping stale listener on $port (pid $owner, $($proc.ProcessName))"
    try { Stop-Process -Id $owner -Force -ErrorAction Stop } catch { }
    Start-Sleep -Seconds 2
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

# 🔴 THE CONTAINER IS CREATED BEFORE ANYTHING IS REPOINTED, AND IT DID NOT USE
#    TO BE. 2026-08-31.
#
# The repointing below talks to Keycloak over `kcadm`, so it needs Keycloak
# RUNNING. This script used to repoint first and recreate second, which works
# only when a Keycloak from a PREVIOUS run happens to be up. On a cold start --
# or after a `docker rm -f` that failed on a zombie PID, which is how it
# happened -- `kcadm get clients` found nothing, the script threw
# "could not resolve the evercoat-web client id", and died BEFORE the
# `docker run` that would have created the very container it was looking for.
#
# The stack was then left with a live tunnel, no identity provider, and a realm
# still naming a hostname two tunnels old. Recreate first, wait, then repoint.
$kcReady = $false
foreach ($attempt in 1..90) {
    try {
        $probe = Invoke-WebRequest -Uri "http://localhost:18080/realms/evercoat/.well-known/openid-configuration" `
                                   -UseBasicParsing -TimeoutSec 5 -ErrorAction Stop
        if ($probe.StatusCode -eq 200) { $kcReady = $true; break }
    } catch { }
    Start-Sleep -Seconds 10
}
if (-not $kcReady) {
    throw ("Keycloak did not answer on http://localhost:18080 within 15 minutes. " +
           "`start-dev` runs a config build first and must NOT be memory-capped; " +
           "check `docker logs evercoat-demo-keycloak`.")
}
Write-Host "  keycloak answering on :18080"

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

# ---------------------------------------------------------- realm frontendUrl
# 🔴 THE CLIENT IS NOT THE ONLY THING THAT HOLDS THE HOSTNAME, AND THE OTHER
#    ONE DECIDES WHAT `iss` SAYS. 2026-08-31.
#
# The realm carries a `frontendUrl` attribute, PERSISTED IN THE DATABASE, and it
# OVERRIDES `KC_HOSTNAME` on the container. This script repointed the client and
# recreated the container with the new `KC_HOSTNAME`, and left that row alone --
# so Keycloak went on minting tokens whose `iss` named a tunnel that had been
# dead for hours, and the API rejected every one of them with "invalid token".
#
# ⚠️ IT LOOKS LIKE A PROXY PROBLEM AND IT IS NOT. The stale issuer is served on
# `http://localhost:18080` too, with Caddy entirely out of the path -- which is
# the measurement that tells the two apart, and is worth making before reaching
# for `X-Forwarded-*`.
#
# ⚠️ AND `kcadm get realms/evercoat --fields attributes` RETURNED `{}` while the
# row was sitting in `realm_attribute`. The admin API did not surface it. So the
# read-back below goes to the DATABASE: asserting through the same interface
# that hid it would prove nothing.
& $docker exec evercoat-demo-keycloak /opt/keycloak/bin/kcadm.sh update realms/evercoat `
    -s "attributes.frontendUrl=$PublicUrl/auth" 2>&1 | Out-Null
$kcFrontend = (& $docker exec -e PGPASSWORD=dev-superuser-pw evercoat-postgres `
    psql -U postgres -d keycloak -tAc "SELECT value FROM realm_attribute WHERE name='frontendUrl'") -join ""
$kcFrontend = $kcFrontend.Trim()
if ($kcFrontend -ne "$PublicUrl/auth") {
    throw ("the realm frontendUrl was NOT repointed. It reads '$kcFrontend' and must read " +
           "'$PublicUrl/auth'. Every token would be issued with that issuer and the API " +
           "would refuse all of them as `"invalid token`".")
}
Write-Host "  keycloak realm frontendUrl repointed (read back from the database)"


# ----------------------------------------------------------- api preflight
# 🔴 THE SIGN-IN ROLE MUST BE ABLE TO LOG IN, AND THIS SCRIPT PROVISIONS
#    NOTHING -- SO IT CHECKS INSTEAD OF ASSUMING.
#
# Migration 053 (I109) revoked EXECUTE on core.principal_for_subject and
# core.memberships_for_subject from evercoat_app and gave them to
# evercoat_auth, which 053 creates NOLOGIN because a migration must not carry
# a password. On a database prepared before 053 that role therefore exists and
# cannot connect -- and the symptom is the API starting cleanly, serving
# /health/live, and refusing EVERY authenticated request.
#
# Raised by Codex: the script hardcodes these credentials and never installs
# them. It still should not install them -- provisioning is the deployment's
# job and this script has no superuser password -- but starting a demo that
# cannot authenticate anybody is worse than refusing, and the refusal can name
# the exact remedy. Same argument live-suite.sh's preflight makes.
$authProbe = docker exec -e PGPASSWORD=ci-auth evercoat-postgres `
    psql -U evercoat_auth -d evercoat_itw_rd -tAc "SELECT 1" 2>&1
if ($LASTEXITCODE -ne 0) {
    throw (
        "the sign-in role cannot connect, so nobody would be able to log in " +
        "to this demo (I109, migration 053). psql said: $authProbe`n`n" +
        "Fix it with:`n" +
        "  docker exec evercoat-postgres psql -U postgres -d evercoat_itw_rd ``n" +
        "    -c ""ALTER ROLE evercoat_auth LOGIN PASSWORD 'ci-auth';""`n`n" +
        "If the role does not exist at all, the database predates migration " +
        "053 -- run ``alembic upgrade head`` first."
    )
}
Write-Host "  sign-in role can connect (I109 preflight)"

# ----------------------------------------------------------------------- api
$apiCmd = @"
`$env:DATABASE_URL='postgresql+psycopg://evercoat_app:ci-app@localhost:55432/evercoat_itw_rd';
# Sign-in only (I109, migration 053). evercoat_app no longer holds EXECUTE on
# core.principal_for_subject or core.memberships_for_subject, so without this
# the demo starts, serves /health/live, and refuses every authenticated
# request. /health/ready reports it rather than leaving that to a user.
`$env:AUTH_DATABASE_URL='postgresql+psycopg://evercoat_auth:ci-auth@localhost:55432/evercoat_itw_rd';
# The anonymous public read connection (migration 059). WITHOUT IT THE DEMO
# COMES UP LOOKING FINE AND EVERY /api/public/* ROUTE ANSWERS 503 -- the
# landing page then renders its "catalogue is unavailable" notice, which is
# the honest failure but is indistinguishable, to a viewer, from the feature
# not existing.
`$env:PUBLIC_DATABASE_URL='postgresql+psycopg://evercoat_public:dev-public-pw@localhost:55432/evercoat_itw_rd';
# The agent tier's curation connection (migration 060). Its inability to
# publish is a property of this role.
`$env:AGENT_DATABASE_URL='postgresql+psycopg://evercoat_agent:dev-agent-pw@localhost:55432/evercoat_itw_rd';
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
# 🔴 ITS OWN BUILD DIRECTORY, AND NO BACKTICKS IN THIS COMMENT -- SEE BELOW.
# 'next build' regenerates '.next/standalone/',
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
# 🔴 KILL THE RUNNING WEB SERVER BEFORE REBUILDING. 2026-08-26.
#
# `node .next-demo\standalone\server.js` holds an open handle on
# `.next-demo`, so a rebuild into that directory does NOT fail loudly -- it
# PRINTS THE NEXT.JS BANNER AND THEN STALLS, indefinitely, at near-zero CPU.
# `Remove-Item -Recurse -Force .next-demo` also silently does nothing
# (`Test-Path` still true afterwards) because `-ErrorAction SilentlyContinue`
# swallows the sharing violation.
#
# Measured today: three consecutive rebuild attempts hung this way and read
# like a slow machine. The tell is `Get-Process node` sitting at single-digit
# CPU seconds while the log holds one line. `Get-CimInstance Win32_Process
# -Filter "Name='node.exe'"` names the holder in its command line.
#
# ⚠️ THIS SCRIPT ALREADY STOPS THE PORT-3000 LISTENER at the top, which is why
# it normally works. It matters when rebuilding BY HAND against a stack that
# is already up -- stop the listener first, or the build will hang and nothing
# will say why.

# 🔴 NO BACKTICKS INSIDE $webCmd, INCLUDING IN ITS COMMENTS. 2026-08-26.
#
# `@"..."@` is a DOUBLE-QUOTED here-string, so PowerShell processes escape
# sequences inside it -- and the backtick is the escape character. The comment
# above used to markdown-quote `next build`, which made PowerShell read the
# backtick-n as a NEWLINE. The comment split in two and its remainder became a
# command:
#
#     ext : The term 'ext' is not recognized ...
#     At line:7 char:1
#     + ext build regenerates .next/standalone/,
#
# The build then ran without `NEXT_DIST_DIR`, wrote to `.next/` instead of
# `.next-demo/`, and `node .next-demo\standalone\server.js` happily served
# YESTERDAY's bundle: every page 200, the two new ones 404, and the previous
# tunnel hostname still inlined in NEXT_PUBLIC_*. A green build serving a
# stale site.
#
# ⚠️ THE IRONY IS THE POINT. The broken comment was the one explaining why the
# build directory must be isolated, and the escape silently disabled exactly
# the protection it described. Keep this block free of backticks, or switch to
# a single-quoted here-string (@'...'@) if interpolation is ever not needed.

Start-Process powershell -ArgumentList @("-NoProfile", "-Command", $webCmd) `
    -RedirectStandardOutput (Join-Path $logDir "web.log") `
    -RedirectStandardError  (Join-Path $logDir "web.err.log") -WindowStyle Hidden
Write-Host "  web building + serving standalone (detached)"

Write-Host ""
Write-Host "PUBLIC URL: $PublicUrl"
Write-Host "All detached -- they outlive this session."
Write-Host "Watch: Get-Content '$logDir\web.log' -Tail 20 -Wait"

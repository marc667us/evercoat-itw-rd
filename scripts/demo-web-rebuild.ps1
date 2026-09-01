# Rebuild the demo web bundle against the CURRENT tunnel hostname.
#
# NEXT_PUBLIC_* is inlined at BUILD time, so when the tunnel rotated the
# client kept calling the dead hostname and the public catalogue rendered
# "The public catalogue is unavailable."  Measured in Chromium:
#   net::ERR_NAME_NOT_RESOLVED https://probably-resident-prague-albert...
#
# Mirrors scripts/demo-up.ps1's own web block exactly, including the separate
# .next-demo dist dir and the two asset copies standalone does not make.

$ErrorActionPreference = "Stop"
$repo = "C:\Users\USER\Documents\evercoat-itw-rd-workspace\EvercoatITWRD APP"
$node = "C:\Users\USER\nodejs"
$logDir = Join-Path $repo "tmp\demo"
$url = (Get-Content (Join-Path $logDir "current_url.txt") -Raw).Trim()

Write-Host "rebuilding web for: $url"

# 🔴 KILL THE LISTENER FIRST. A running node server holds an open handle on
# its own build directory, so `next build` stalls at near-zero CPU forever and
# the removal of the old tree silently fails.
$conn = Get-NetTCPConnection -LocalPort 3000 -State Listen -ErrorAction SilentlyContinue
if ($conn) {
    $pid3000 = $conn[0].OwningProcess
    $proc = Get-CimInstance Win32_Process -Filter "ProcessId=$pid3000"
    if ($proc.CommandLine -match "standalone\\server\.js") {
        Stop-Process -Id $pid3000 -Force
        Write-Host "stopped web server pid $pid3000"
        Start-Sleep -Seconds 3
    } else {
        throw "port 3000 is held by something that is not the demo web server: $($proc.CommandLine)"
    }
}

$env:PATH = "$node;" + $env:PATH
$env:NEXT_PUBLIC_API_BASE_URL = $url
$env:NEXT_PUBLIC_KEYCLOAK_URL = "$url/auth"
$env:NEXT_PUBLIC_KEYCLOAK_REALM = "evercoat"
$env:NEXT_PUBLIC_KEYCLOAK_CLIENT_ID = "evercoat-web"
$env:NEXT_DIST_DIR = ".next-demo"

Set-Location "$repo\apps\web"
npx next build 2>&1 | Tee-Object -FilePath "$logDir\web-rebuild.log"
if ($LASTEXITCODE -ne 0) { throw "next build failed with $LASTEXITCODE" }

Copy-Item -Recurse -Force ".next-demo\static" ".next-demo\standalone\.next-demo\static"
if (Test-Path "public") { Copy-Item -Recurse -Force "public" ".next-demo\standalone\public" }

$env:PORT = "3000"
$env:HOSTNAME = "0.0.0.0"
Start-Process -FilePath "$node\node.exe" -ArgumentList ".next-demo\standalone\server.js" `
    -WorkingDirectory "$repo\apps\web" -WindowStyle Hidden `
    -RedirectStandardOutput "$logDir\web.log" -RedirectStandardError "$logDir\web.err.log"

Write-Host "web restarted; waiting for :3000"
$deadline = (Get-Date).AddSeconds(90)
while ((Get-Date) -lt $deadline) {
    try {
        $r = Invoke-WebRequest -Uri "http://localhost:3000/marketplace" -UseBasicParsing -TimeoutSec 10
        if ($r.StatusCode -eq 200) { Write-Host "web is serving (200)"; break }
    } catch { Start-Sleep -Seconds 3 }
}
Write-Host "done"

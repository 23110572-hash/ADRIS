param(
    [Parameter(Mandatory = $true)]
    [string]$PrimaryUrl,
    [string]$SecondaryUrl = "",
    [int]$TimeoutSeconds = 60
)

$deadline = (Get-Date).AddSeconds($TimeoutSeconds)
$ready = $false

do {
    try {
        $response = Invoke-WebRequest -UseBasicParsing -Uri $PrimaryUrl -TimeoutSec 2
        $ready = $response.StatusCode -lt 500
    }
    catch {
        $ready = $false
    }

    if (-not $ready) {
        Start-Sleep -Milliseconds 400
    }
} while (-not $ready -and (Get-Date) -lt $deadline)

$urls = @($PrimaryUrl)
if ($SecondaryUrl) {
    $urls += $SecondaryUrl
}

$chromeCandidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:LocalAppData\Google\Chrome\Application\chrome.exe"
)
$chrome = $chromeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if ($chrome) {
    Start-Process -FilePath $chrome -ArgumentList $urls
}
else {
    foreach ($url in $urls) {
        Start-Process $url
    }
}

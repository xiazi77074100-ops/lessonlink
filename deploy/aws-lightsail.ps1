[CmdletBinding()]
param(
    [string]$InstanceName = "lessonlink",
    [string]$Region = "ap-northeast-1",
    [string]$AvailabilityZone = "ap-northeast-1a",
    [string]$AwsProfile = "default",
    [string]$BundleId = "",
    [string]$Domain = "",
    [switch]$Yes
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repoRoot = Split-Path -Parent $PSScriptRoot
$deployDir = Join-Path $repoRoot ".deploy"
$backendEnvPath = Join-Path $repoRoot "backend\.env"
$archivePath = Join-Path $deployDir "lessonlink.tar.gz"
$productionEnvPath = Join-Path $deployDir ".env.production"
$awsCommand = (Get-Command "aws" -ErrorAction SilentlyContinue).Source
if (-not $awsCommand) {
    $defaultAwsPath = "C:\Program Files\Amazon\AWSCLIV2\aws.exe"
    if (Test-Path -LiteralPath $defaultAwsPath) { $awsCommand = $defaultAwsPath }
}

function Require-Command([string]$Name, [string]$InstallHint) {
    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "$Name was not found. $InstallHint"
    }
}

function Invoke-AwsJson([string[]]$Arguments) {
    $result = & $script:awsCommand @Arguments --region $Region --profile $AwsProfile --output json
    if ($LASTEXITCODE -ne 0) { throw "AWS CLI command failed: aws $($Arguments -join ' ')" }
    if ([string]::IsNullOrWhiteSpace(($result -join "`n"))) { return $null }
    return (($result -join "`n") | ConvertFrom-Json)
}

function Read-DotEnv([string]$Path) {
    $values = @{}
    foreach ($line in Get-Content -LiteralPath $Path -Encoding UTF8) {
        if ($line -match '^\s*#' -or $line -notmatch '=') { continue }
        $parts = $line -split '=', 2
        $values[$parts[0].Trim()] = $parts[1].Trim().Trim('"').Trim("'")
    }
    return $values
}

function New-RandomHex([int]$Bytes = 32) {
    $buffer = New-Object byte[] $Bytes
    [System.Security.Cryptography.RandomNumberGenerator]::Fill($buffer)
    return [Convert]::ToHexString($buffer).ToLowerInvariant()
}

if (-not $awsCommand) {
    throw "AWS CLI v2 was not found. Install it, then run 'aws configure --profile $AwsProfile': https://docs.aws.amazon.com/cli/latest/userguide/getting-started-install.html"
}
Require-Command "git" "Install Git first."
Require-Command "ssh.exe" "Enable the Windows OpenSSH Client optional feature."
Require-Command "scp.exe" "Enable the Windows OpenSSH Client optional feature."

if (-not (Test-Path -LiteralPath $backendEnvPath)) {
    throw "backend/.env was not found. Configure the LINE credentials first."
}

$sourceEnv = Read-DotEnv $backendEnvPath
$requiredLineKeys = @(
    "LINE_LOGIN_CHANNEL_ID", "LINE_LOGIN_CHANNEL_SECRET", "LINE_MESSAGING_CHANNEL_ID",
    "LINE_MESSAGING_CHANNEL_SECRET", "LINE_MESSAGING_CHANNEL_ACCESS_TOKEN", "LIFF_ID"
)
foreach ($key in $requiredLineKeys) {
    if (-not $sourceEnv.ContainsKey($key) -or [string]::IsNullOrWhiteSpace($sourceEnv[$key])) {
        throw "backend/.env value $key is empty. Configure all LINE credentials first."
    }
}

$identity = Invoke-AwsJson @("sts", "get-caller-identity")
Write-Host "AWS Account: $($identity.Account) / Region: $Region"

$blueprints = Invoke-AwsJson @("lightsail", "get-blueprints")
$blueprint = $blueprints.blueprints |
    Where-Object { $_.isActive -and $_.platform -eq "LINUX_UNIX" -and $_.blueprintId -match '^ubuntu_24_04' } |
    Select-Object -First 1
if (-not $blueprint) { throw "No active Ubuntu 24.04 Lightsail blueprint was found." }

$bundles = Invoke-AwsJson @("lightsail", "get-bundles")
if ($BundleId) {
    $bundle = $bundles.bundles | Where-Object { $_.bundleId -eq $BundleId -and $_.isActive } | Select-Object -First 1
} else {
    $bundle = $bundles.bundles |
        Where-Object {
            $_.isActive -and $_.ramSizeInGb -ge 1 -and
            $_.supportedPlatforms -contains "LINUX_UNIX" -and $_.bundleId -notmatch '_ipv6_'
        } |
        Sort-Object price |
        Select-Object -First 1
}
if (-not $bundle) { throw "No matching Lightsail bundle was found. Specify -BundleId." }

$existing = Invoke-AwsJson @("lightsail", "get-instances")
if ($existing.instances | Where-Object { $_.name -eq $InstanceName }) {
    throw "Lightsail instance '$InstanceName' already exists. Refusing to overwrite it."
}

Write-Host "Will create: $InstanceName / $($blueprint.blueprintId) / $($bundle.bundleId) / $($bundle.ramSizeInGb) GB RAM / USD $($bundle.price) per month"
if (-not $Yes) {
    $confirmation = Read-Host "This creates billable resources. Type CREATE to continue"
    if ($confirmation -ne "CREATE") { throw "Cancelled." }
}

New-Item -ItemType Directory -Force -Path $deployDir | Out-Null
$keyName = "$InstanceName-deploy-$((Get-Date).ToString('yyyyMMddHHmmss'))"
$keyResult = Invoke-AwsJson @("lightsail", "create-key-pair", "--key-pair-name", $keyName)
$keyPath = Join-Path $deployDir "$keyName.pem"
$keyMaterial = [string]$keyResult.privateKeyBase64
if ($keyMaterial -notmatch "BEGIN .*PRIVATE KEY") {
    $keyMaterial = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($keyMaterial))
}
[IO.File]::WriteAllText($keyPath, $keyMaterial, [Text.UTF8Encoding]::new($false))
& icacls $keyPath /inheritance:r /grant:r "$($env:USERNAME):(R)" | Out-Null

Invoke-AwsJson @(
    "lightsail", "create-instances", "--instance-names", $InstanceName,
    "--availability-zone", $AvailabilityZone, "--blueprint-id", $blueprint.blueprintId,
    "--bundle-id", $bundle.bundleId, "--key-pair-name", $keyName,
    "--ip-address-type", "dualstack"
) | Out-Null

Write-Host "Waiting for the instance to start..."
do {
    Start-Sleep -Seconds 8
    $instance = (Invoke-AwsJson @("lightsail", "get-instance", "--instance-name", $InstanceName)).instance
} until ($instance.state.name -eq "running")

$staticIpName = "$InstanceName-static-ip"
Invoke-AwsJson @("lightsail", "allocate-static-ip", "--static-ip-name", $staticIpName) | Out-Null
Invoke-AwsJson @("lightsail", "attach-static-ip", "--static-ip-name", $staticIpName, "--instance-name", $InstanceName) | Out-Null
$staticIp = (Invoke-AwsJson @("lightsail", "get-static-ip", "--static-ip-name", $staticIpName)).staticIp.ipAddress

foreach ($port in 80, 443) {
    Invoke-AwsJson @("lightsail", "open-instance-public-ports", "--instance-name", $InstanceName, "--port-info", "fromPort=$port,toPort=$port,protocol=tcp") | Out-Null
}

if ([string]::IsNullOrWhiteSpace($Domain)) { $Domain = "$($staticIp.Replace('.', '-')).sslip.io" }

$productionLines = @(
    "DOMAIN=$Domain", "POSTGRES_DB=lessonlink", "POSTGRES_USER=lessonlink",
    "POSTGRES_PASSWORD=$(New-RandomHex)", "JWT_SECRET=$(New-RandomHex)",
    "JWT_ALGORITHM=HS256", "JWT_ACCESS_TOKEN_EXPIRE_MINUTES=720"
) + ($requiredLineKeys | ForEach-Object { "$_=$($sourceEnv[$_])" })
[IO.File]::WriteAllLines($productionEnvPath, $productionLines, [Text.UTF8Encoding]::new($false))

& git -C $repoRoot archive --format=tar.gz -o $archivePath HEAD
if ($LASTEXITCODE -ne 0) { throw "git archive failed. Commit changes and retry." }

$sshTarget = "ubuntu@$staticIp"
$sshArgs = @("-i", $keyPath, "-o", "StrictHostKeyChecking=accept-new", "-o", "ConnectTimeout=10")
Write-Host "Waiting for SSH..."
for ($attempt = 1; $attempt -le 30; $attempt++) {
    & ssh.exe @sshArgs $sshTarget "true" 2>$null
    if ($LASTEXITCODE -eq 0) { break }
    if ($attempt -eq 30) { throw "SSH connection failed. Check the Lightsail firewall and instance status." }
    Start-Sleep -Seconds 10
}

& ssh.exe @sshArgs $sshTarget "sudo mkdir -p /opt/lessonlink && sudo chown ubuntu:ubuntu /opt/lessonlink"
if ($LASTEXITCODE -ne 0) { throw "Could not create the remote directory." }
& scp.exe @sshArgs $archivePath "${sshTarget}:/tmp/lessonlink.tar.gz"
& scp.exe @sshArgs $productionEnvPath "${sshTarget}:/tmp/lessonlink.env"
if ($LASTEXITCODE -ne 0) { throw "Could not upload deployment files." }

$remoteCommand = "tar -xzf /tmp/lessonlink.tar.gz -C /opt/lessonlink && mv /tmp/lessonlink.env /opt/lessonlink/.env.production && chmod +x /opt/lessonlink/deploy/remote-bootstrap.sh && /opt/lessonlink/deploy/remote-bootstrap.sh /opt/lessonlink"
& ssh.exe @sshArgs $sshTarget $remoteCommand
if ($LASTEXITCODE -ne 0) { throw "Remote deployment failed. Review the preceding logs." }

Remove-Item -LiteralPath $productionEnvPath -Force
Write-Host "`nDeployment complete"
Write-Host "Admin:         https://$Domain/"
Write-Host "LIFF Endpoint: https://$Domain/parent/"
Write-Host "Health:        https://$Domain/api/v1/health"
Write-Host "Static IP:     $staticIp"
Write-Host "SSH key:       $keyPath"

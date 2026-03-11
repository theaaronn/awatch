#Requires -RunAsAdministrator

$RepoOrg = "YOUR_ORG"
$RepoName = "awatch"

$Arch = "amd64"
if (-not [System.Environment]::Is64BitOperatingSystem) {
    Write-Error "Unsupported architecture. Only 64-bit Windows is supported."
    exit 1
}

function Validate-AgentId {
    param([string]$Id)
    if ($Id -notmatch '^[a-zA-Z0-9_-]{1,64}$') {
        Write-Error "agent_id must be 1-64 characters: letters, numbers, underscore, hyphen"
        return $false
    }
    return $true
}

function Validate-BrokerUrl {
    param([string]$Url)
    if ($Url -notmatch '^[a-zA-Z0-9._-]+:[0-9]+$') {
        Write-Error "broker_url must be in format host:port"
        return $false
    }
    return $true
}

function Validate-NatsUrl {
    param([string]$Url)
    if ($Url -notmatch '^nats://') {
        Write-Error "nats_url must start with nats://"
        return $false
    }
    return $true
}

$AgentId = $env:AWATCH_AGENT_ID
if (-not $AgentId) {
    $AgentId = Read-Host "Enter a unique ID for this server (e.g. prod-web-01)"
}
if (-not (Validate-AgentId $AgentId)) { exit 1 }

$BrokerUrl = $env:AWATCH_BROKER_URL
if (-not $BrokerUrl) {
    $BrokerUrl = Read-Host "Enter broker gRPC address (e.g. 10.0.0.1:50051)"
}
if (-not (Validate-BrokerUrl $BrokerUrl)) { exit 1 }

$NatsUrl = $env:AWATCH_NATS_URL
if (-not $NatsUrl) {
    $NatsUrl = Read-Host "Enter NATS URL (e.g. nats://10.0.0.1:4222)"
}
if (-not (Validate-NatsUrl $NatsUrl)) { exit 1 }

Write-Host "Determining latest version..."
$LatestRelease = Invoke-RestMethod -Uri "https://api.github.com/repos/$RepoOrg/$RepoName/releases/latest"
$Version = $LatestRelease.tag_name

if (-not $Version) {
    Write-Error "Could not determine latest version"
    exit 1
}

Write-Host "Latest version: $Version"

$InstallDir = "C:\Program Files\awatch"
$ConfigDir = "C:\ProgramData\awatch"
$BinaryPath = "$InstallDir\awatch-agent.exe"
$DownloadUrl = "https://github.com/$RepoOrg/$RepoName/releases/download/$Version/awatch-agent-windows-$Arch.exe"

$ServiceName = "AWatch Agent"
$ExistingService = Get-Service -Name $ServiceName -ErrorAction SilentlyContinue
if ($ExistingService) {
    Write-Host "Stopping existing service..."
    Stop-Service -Name $ServiceName -ErrorAction SilentlyContinue
}

Write-Host "Creating directories..."
New-Item -ItemType Directory -Force -Path $InstallDir | Out-Null
New-Item -ItemType Directory -Force -Path $ConfigDir | Out-Null

Write-Host "Downloading awatch-agent..."
Invoke-WebRequest -Uri $DownloadUrl -OutFile $BinaryPath -UseBasicParsing

Write-Host "Writing config file..."
$ConfigContent = @"
agent_id: "$AgentId"
broker_url: "$BrokerUrl"
nats_url: "$NatsUrl"
collection_interval: "1s"
batch_size: 10
log_level: "info"
tls_enabled: false
"@
$ConfigContent | Out-File -FilePath "$ConfigDir\agent.yaml" -Encoding utf8

Write-Host "Creating Windows service..."
if ($ExistingService) {
    Write-Host "Service already exists, starting..."
    Start-Service -Name $ServiceName
} else {
    New-Service -Name $ServiceName `
        -BinaryPathName $BinaryPath `
        -DisplayName "Awatch Monitoring Agent" `
        -Description "Awatch host monitoring agent" `
        -StartupType Automatic | Out-Null
    
    Start-Service -Name $ServiceName
}

Write-Host ""
Write-Host "Awatch agent installed. Check status: Get-Service 'AWatch Agent'"

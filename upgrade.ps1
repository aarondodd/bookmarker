# Bookmarker -- Windows upgrade.
#
# Detects the currently-installed version from the Inno Setup uninstall registry
# entries (both per-user HKCU and system-wide HKLM, so per-user installs upgrade
# cleanly), compares against the latest GitHub release, and prompts before
# downloading + launching the installer. installer.iss uses CloseApplications +
# RestartApplications, so the installer closes the running app via Windows Restart
# Manager and relaunches it after.
#
# Usage:
#
#   iwr -useb https://raw.githubusercontent.com/aarondodd/bookmarker/main/upgrade.ps1 | iex
#
# Or locally:
#
#   .\upgrade.ps1
#
# For a fresh install, download bookmarker-setup-X.Y.Z.exe from the Releases page.

[CmdletBinding()]
param(
    [string]$Owner = "aarondodd",
    [string]$Repo  = "bookmarker",
    # Force the upgrade even when the installed version is already at or ahead of
    # the latest release. Useful for reinstall / repair flows or for testing a
    # freshly-cut tag.
    [switch]$Force,
    [switch]$Yes
)

$ErrorActionPreference = "Stop"

try {
    [Net.ServicePointManager]::SecurityProtocol = `
        [Net.SecurityProtocolType]::Tls12 -bor `
        [Net.ServicePointManager]::SecurityProtocol
} catch {
    # Older PowerShell may not expose Tls12; the default protocol often still works.
}

# Inno Setup's AppId from installer.iss. Inno Setup appends "_is1" to the AppId
# for the uninstall registry key. The AppId is stable across releases, so this
# fast-path lookup is safe long-term. If the canonical key isn't found the
# function falls back to enumerating uninstall keys and matching by DisplayName.
$InnoAppId = "{1F6B8A6C-F768-42C5-9C3A-9E05B1F1B38B}_is1"
$DisplayNameMatch = "Bookmarker"

# Three roots cover every scope an Inno Setup install can land in:
#   HKLM\...\Uninstall                 -- system-wide 64-bit
#   HKLM\...\WOW6432Node\...\Uninstall -- system-wide 32-bit (rare)
#   HKCU\...\Uninstall                 -- per-user (default; installer.iss sets
#                                         PrivilegesRequired=lowest)
$UninstallRoots = @(
    "HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
    "HKLM:\SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall",
    "HKCU:\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"
)

function Read-UninstallKey {
    # Read one uninstall key and return a pscustomobject if it looks like ours.
    # -LiteralPath so the curly braces in the GUID-shaped subkey name aren't
    # interpreted as wildcards by the registry provider.
    param([string]$Root, [string]$Subkey)
    $path = Join-Path -Path $Root -ChildPath $Subkey
    try {
        $key = Get-ItemProperty -LiteralPath $path -ErrorAction Stop
    } catch {
        return $null
    }
    if (-not $key) { return $null }
    if (-not $key.DisplayVersion) { return $null }
    return [pscustomobject]@{
        DisplayVersion = $key.DisplayVersion
        DisplayName = $key.DisplayName
        InstallLocation = $key.InstallLocation
        Publisher = $key.Publisher
        Scope = if ($Root -like "HKCU:*") { "per-user" } else { "system-wide" }
        RegistryPath = $path
    }
}

function Get-InstalledVersion {
    # Fast path: the canonical Inno Setup AppId_is1 key under each uninstall root.
    foreach ($root in $UninstallRoots) {
        $info = Read-UninstallKey -Root $root -Subkey $InnoAppId
        if ($info) { return $info }
    }
    # Fallback: enumerate every uninstall subkey and match by DisplayName.
    foreach ($root in $UninstallRoots) {
        if (-not (Test-Path -LiteralPath $root)) { continue }
        try {
            $children = Get-ChildItem -LiteralPath $root -ErrorAction Stop
        } catch {
            continue
        }
        foreach ($child in $children) {
            try {
                $key = Get-ItemProperty -LiteralPath $child.PSPath -ErrorAction Stop
            } catch {
                continue
            }
            if (-not $key) { continue }
            if ($key.DisplayName -and $key.DisplayName -like "*$DisplayNameMatch*") {
                if ($key.DisplayVersion) {
                    return [pscustomobject]@{
                        DisplayVersion = $key.DisplayVersion
                        DisplayName = $key.DisplayName
                        InstallLocation = $key.InstallLocation
                        Publisher = $key.Publisher
                        Scope = if ($root -like "HKCU:*") { "per-user" } else { "system-wide" }
                        RegistryPath = $child.PSPath
                    }
                }
            }
        }
    }
    return $null
}

function Write-RegistryDiagnostic {
    Write-Host ""
    Write-Host "Registry lookup diagnostic:" -ForegroundColor Yellow
    foreach ($root in $UninstallRoots) {
        $canonical = Join-Path -Path $root -ChildPath $InnoAppId
        $existsCanonical = Test-Path -LiteralPath $canonical
        $rootExists = Test-Path -LiteralPath $root
        $childCount = 0
        if ($rootExists) {
            try {
                $childCount = (Get-ChildItem -LiteralPath $root -ErrorAction Stop).Count
            } catch {
                $childCount = -1
            }
        }
        Write-Host ("  {0}" -f $root)
        Write-Host ("    exists: {0} (child keys: {1})" -f $rootExists, $childCount)
        Write-Host ("    canonical key {0}: {1}" -f $InnoAppId, $existsCanonical)
    }
    Write-Host ("  DisplayName fallback pattern: *{0}*" -f $DisplayNameMatch)
}

function Parse-SemVer {
    # Lenient semver parse: leading "v" allowed, pre-release suffix discarded.
    param([string]$Raw)
    if (-not $Raw) { throw "Empty version string." }
    $trim = $Raw.Trim()
    if ($trim.StartsWith("v") -or $trim.StartsWith("V")) {
        $trim = $trim.Substring(1)
    }
    if ($trim -match '^(\d+(\.\d+){0,3})') {
        return [version]$matches[1]
    }
    throw "Cannot parse version: $Raw"
}

function Get-LatestRelease {
    param([string]$Owner, [string]$Repo)
    $url = "https://api.github.com/repos/$Owner/$Repo/releases/latest"
    Write-Host "Checking latest release on GitHub..." -ForegroundColor Cyan
    try {
        return Invoke-RestMethod -Uri $url -UseBasicParsing -Headers @{
            "User-Agent" = "bookmarker-upgrade-script"
        }
    } catch {
        throw "Could not reach the GitHub releases API ($url). " +
              "Check your network connection. Underlying error: $_"
    }
}

function Find-InstallerAsset {
    param([object]$Release)
    $candidate = $Release.assets | Where-Object {
        $_.name -like "bookmarker-setup-*.exe"
    } | Select-Object -First 1
    if (-not $candidate) {
        throw "Latest release $($Release.tag_name) has no " +
              "bookmarker-setup-*.exe asset attached."
    }
    return $candidate
}

function Format-Size {
    param([long]$Bytes)
    if ($Bytes -ge 1GB) { return "{0:N1} GB" -f ($Bytes / 1GB) }
    if ($Bytes -ge 1MB) { return "{0:N1} MB" -f ($Bytes / 1MB) }
    if ($Bytes -ge 1KB) { return "{0:N1} KB" -f ($Bytes / 1KB) }
    return "$Bytes bytes"
}

function Download-Installer {
    param([string]$Url, [string]$Destination)
    Write-Host ""
    Write-Host "Downloading installer to $Destination ..." -ForegroundColor Cyan
    $prior = $ProgressPreference
    $ProgressPreference = "SilentlyContinue"
    try {
        Invoke-WebRequest -Uri $Url -OutFile $Destination -UseBasicParsing
    } finally {
        $ProgressPreference = $prior
    }
    if (-not (Test-Path -LiteralPath $Destination)) {
        throw "Download finished but $Destination is missing."
    }
    $size = (Get-Item -LiteralPath $Destination).Length
    Write-Host "Downloaded $(Format-Size $size)." -ForegroundColor Green
}

function Confirm-Prompt {
    param([string]$Question, [switch]$Yes)
    if ($Yes) {
        Write-Host "$Question [Y/n] (auto-yes via -Yes flag)" -ForegroundColor Yellow
        return $true
    }
    while ($true) {
        $reply = Read-Host "$Question [Y/n]"
        if ([string]::IsNullOrWhiteSpace($reply)) { return $true }
        switch -Regex ($reply.Trim()) {
            '^[yY]([eE][sS])?$' { return $true }
            '^[nN]([oO])?$'     { return $false }
            default { Write-Host "Please answer Y or N." -ForegroundColor Yellow }
        }
    }
}

# ---- main -----------------------------------------------------------

Write-Host ""
Write-Host "Bookmarker -- Windows upgrade" -ForegroundColor Cyan
Write-Host "============================="

$installed = Get-InstalledVersion
if (-not $installed) {
    Write-Host ""
    Write-Host ("No installed Bookmarker detected. Tried the canonical Inno Setup " +
                "key + a DisplayName fallback across HKLM, HKLM\WOW6432Node, and " +
                "HKCU.") -ForegroundColor Yellow
    Write-RegistryDiagnostic
    Write-Host ""
    Write-Host "For a fresh install, download the latest installer from:"
    Write-Host "  https://github.com/$Owner/$Repo/releases/latest"
    Write-Host "  (bookmarker-setup-X.Y.Z.exe)"
    exit 1
}

Write-Host ""
Write-Host ("Installed: {0} ({1})" -f $installed.DisplayVersion, $installed.Scope) -ForegroundColor Green
if ($installed.InstallLocation) {
    Write-Host ("  Location: {0}" -f $installed.InstallLocation)
}

$release = Get-LatestRelease -Owner $Owner -Repo $Repo
$asset = Find-InstallerAsset -Release $release

# Version comparison. Failures here are non-fatal -- we'd rather still offer the
# upgrade than block the user on a parse glitch from a custom build.
$cmpResult = $null
try {
    $installedVer = Parse-SemVer -Raw $installed.DisplayVersion
    $latestVer    = Parse-SemVer -Raw $release.tag_name
    $cmpResult = $installedVer.CompareTo($latestVer)
} catch {
    Write-Host ("Version compare skipped: {0}" -f $_) -ForegroundColor Yellow
}

Write-Host ""
Write-Host ("Latest release: {0}" -f $release.tag_name) -ForegroundColor Green
Write-Host ("  Asset:        {0}" -f $asset.name)
Write-Host ("  Size:         {0}" -f (Format-Size $asset.size))
Write-Host ("  Published:    {0}" -f $release.published_at)
Write-Host ("  URL:          {0}" -f $release.html_url)
Write-Host ""

if ($cmpResult -eq 0) {
    Write-Host ("You are already on the latest release ($($release.tag_name)).") -ForegroundColor Green
    if (-not $Force) {
        if (-not (Confirm-Prompt -Question "Reinstall anyway?" -Yes:$Yes)) {
            Write-Host "Nothing to do." -ForegroundColor Yellow
            exit 0
        }
    }
} elseif ($cmpResult -gt 0) {
    Write-Host ("Installed version $($installed.DisplayVersion) is AHEAD of the " +
                "latest release ($($release.tag_name)). Looks like a local / dev " +
                "build.") -ForegroundColor Yellow
    if (-not $Force) {
        if (-not (Confirm-Prompt -Question "Downgrade to the latest release?" -Yes:$Yes)) {
            Write-Host "Cancelled." -ForegroundColor Yellow
            exit 0
        }
    }
} else {
    if (-not (Confirm-Prompt -Question "Upgrade from $($installed.DisplayVersion) to $($release.tag_name)?" -Yes:$Yes)) {
        Write-Host "Cancelled by user." -ForegroundColor Yellow
        exit 0
    }
}

$temp = Join-Path -Path $env:TEMP -ChildPath $asset.name
try {
    Download-Installer -Url $asset.browser_download_url -Destination $temp

    Write-Host ""
    Write-Host "Running silent in-place upgrade..." -ForegroundColor Cyan
    Write-Host ("Same flags as the in-app updater: /SILENT /SUPPRESSMSGBOXES " +
                "/NORESTART. Inno Setup's stable AppId means the existing install " +
                "gets replaced in place; Windows Restart Manager closes the running " +
                "app via the installer's CloseApplications hook and relaunches it after.")

    $proc = Start-Process -FilePath $temp `
        -ArgumentList "/SILENT","/SUPPRESSMSGBOXES","/NORESTART" `
        -Wait -PassThru
    if ($proc.ExitCode -eq 0) {
        Write-Host ""
        Write-Host "Upgrade complete." -ForegroundColor Green
    } else {
        Write-Host ""
        Write-Host ("Installer exited with code $($proc.ExitCode). Check the " +
                    "installer's log under %TEMP%\Setup Log*.txt for details.") `
            -ForegroundColor Yellow
    }
} finally {
    if (Test-Path -LiteralPath $temp) {
        try {
            Remove-Item -LiteralPath $temp -Force -ErrorAction Stop
        } catch {
            Write-Host ("Could not remove $temp -- delete it manually when the " +
                        "installer is closed.") -ForegroundColor Yellow
        }
    }
}

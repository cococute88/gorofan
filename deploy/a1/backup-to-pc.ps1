param(
    [Parameter(Mandatory = $true)][string]$SshTarget,
    [Parameter(Mandatory = $true)][string]$IdentityFile,
    [Parameter(Mandatory = $true)][string]$Destination
)
$ErrorActionPreference = 'Stop'
if ($env:OS -ne 'Windows_NT') { throw 'This managed-PC helper requires Windows.' }
if ($SshTarget -notmatch '^[a-zA-Z0-9_][a-zA-Z0-9_.@:-]*$') { throw 'Invalid SSH target.' }
$IdentityFile = (Resolve-Path -LiteralPath $IdentityFile).Path
$Destination = [IO.Path]::GetFullPath($Destination)
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../..'))
if ($Destination.StartsWith($repoRoot.TrimEnd('\') + '\', [StringComparison]::OrdinalIgnoreCase) -or $Destination -eq $repoRoot) {
    throw 'Recovery destination must be outside the repository.'
}
if (Test-Path -LiteralPath $Destination) {
    $item = Get-Item -LiteralPath $Destination
    if (-not $item.PSIsContainer -or ($item.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Destination must be a real directory.' }
    if ((Get-ChildItem -Force -LiteralPath $Destination | Measure-Object).Count -gt 0 -and
        -not (Test-Path -LiteralPath (Join-Path $Destination 'gorofan-recovery-target'))) {
        throw 'Refusing to change permissions of an unrelated nonempty directory.'
    }
} else {
    New-Item -ItemType Directory -Path $Destination | Out-Null
}
$sid = [Security.Principal.WindowsIdentity]::GetCurrent().User
$acl = New-Object Security.AccessControl.DirectorySecurity
$acl.SetOwner($sid)
$acl.SetAccessRuleProtection($true, $false)
$rule = New-Object Security.AccessControl.FileSystemAccessRule($sid, 'FullControl', 'ContainerInherit,ObjectInherit', 'None', 'Allow')
$acl.AddAccessRule($rule)
Set-Acl -LiteralPath $Destination -AclObject $acl
Set-Content -LiteralPath (Join-Path $Destination 'gorofan-recovery-target') -Value 'Private gorofan recovery backup; never upload to Git.'

function Quote-NativeArg([string]$Value) {
    if ($Value.Contains('"') -or $Value.Contains("`n") -or $Value.Contains("`r")) { throw 'Unsafe native argument.' }
    '"' + ([regex]::Replace($Value, '(\\+)$', '$1$1')) + '"'
}
function Receive-Ssh([string]$Command, [string]$OutputFile) {
    $info = New-Object Diagnostics.ProcessStartInfo
    $info.FileName = (Get-Command ssh.exe).Source
    $sshArgs = @('-o', 'BatchMode=yes', '-o', 'IdentitiesOnly=yes', '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=15', '-i', $IdentityFile, $SshTarget, $Command)
    $info.Arguments = ($sshArgs | ForEach-Object { Quote-NativeArg $_ }) -join ' '
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    $process = New-Object Diagnostics.Process
    $process.StartInfo = $info
    $null = $process.Start()
    $errorRead = $process.StandardError.ReadToEndAsync()
    if ($OutputFile) {
        $stream = [IO.File]::Open($OutputFile, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
        try { $process.StandardOutput.BaseStream.CopyTo($stream) } finally { $stream.Dispose() }
        $result = $null
    } else {
        $result = $process.StandardOutput.ReadToEnd()
    }
    $process.WaitForExit()
    $null = $errorRead.GetAwaiter().GetResult() # never expose SSH host/credential diagnostics
    if ($process.ExitCode -ne 0) { throw 'Secure backup transfer failed; inspect SSH access privately.' }
    $process.Dispose()
    return $result
}
$backupResult = Receive-Ssh 'cd /opt/gorofan && sudo -n bash deploy/a1/backup.sh'
$verified = [regex]::Matches($backupResult, '(?m)^Backup verified: /srv/gorofan/backups/(gorofan-[a-zA-Z0-9-]+\.tar\.gz)\r?$')
if ($verified.Count -ne 1) { throw 'Exactly one completed server backup is required.' }
$archive = $verified[0].Groups[1].Value
if ($archive -notmatch '^gorofan-[a-zA-Z0-9-]+\.tar\.gz$') { throw 'Unexpected server archive name.' }
$snapshot = Join-Path $Destination ([IO.Path]::GetFileNameWithoutExtension([IO.Path]::GetFileNameWithoutExtension($archive)))
New-Item -ItemType Directory -Path $snapshot | Out-Null
$archivePath = Join-Path $snapshot $archive
Receive-Ssh "sudo -n cat /srv/gorofan/backups/$archive" $archivePath
$hash = ((Receive-Ssh "sudo -n sha256sum /srv/gorofan/backups/$archive") -split '\s+')[0]
if ($hash -notmatch '^[a-f0-9]{64}$' -or (Get-FileHash -Algorithm SHA256 -LiteralPath $archivePath).Hash.ToLowerInvariant() -ne $hash) { throw 'Archive checksum mismatch.' }
Set-Content -LiteralPath ($archivePath + '.sha256') -Value "$hash  $archive"
$envPath = Join-Path $snapshot 'gorofan.env'
Receive-Ssh 'sudo -n cat /etc/gorofan/gorofan.env' $envPath
$envHash = ((Receive-Ssh 'sudo -n sha256sum /etc/gorofan/gorofan.env') -split '\s+')[0]
if ($envHash -notmatch '^[a-f0-9]{64}$' -or (Get-FileHash -Algorithm SHA256 -LiteralPath $envPath).Hash.ToLowerInvariant() -ne $envHash) { throw 'Environment checksum mismatch.' }
Set-Content -LiteralPath (Join-Path $snapshot 'gorofan.env.sha256') -Value "$envHash  gorofan.env"
$null = Receive-Ssh 'date -u +%FT%TZ | sudo -n tee /srv/gorofan/backups/last-managed-pc-copy >/dev/null'
Write-Output 'Off-instance DB/media archive and separate production env copied; SHA-256 verified. Private current-user ACL applied.'

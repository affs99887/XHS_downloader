param([switch]$NoPause)
$ErrorActionPreference = 'Stop'
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
$env:PYTHONUTF8 = '1'
$env:PYTHONIOENCODING = 'utf-8'
$projectRoot = Split-Path -Parent $PSScriptRoot
$exitCode = 1

function Test-ProjectPython([string]$Candidate) {
    if (-not $Candidate -or -not (Test-Path -LiteralPath $Candidate)) { return $false }
    try {
        $result = & $Candidate -c "import sys,struct; print(int(sys.version_info[:2] == (3,11) and struct.calcsize('P') == 8))" 2>$null
        return ($LASTEXITCODE -eq 0 -and "$result".Trim() -eq '1')
    } catch { return $false }
}

try {
    if (-not [Environment]::Is64BitOperatingSystem -or $env:PROCESSOR_ARCHITECTURE -eq 'ARM64') {
        throw 'This installer supports Windows 10/11 x64. ARM64 requires a separate environment.'
    }
    Set-Location -LiteralPath $projectRoot
    $candidates = @((Join-Path $projectRoot '.runtime\python311\python.exe'))
    $candidates += Join-Path $env:LOCALAPPDATA 'Programs\Python\Python311\python.exe'
    $candidates += Join-Path $env:ProgramFiles 'Python311\python.exe'
    $pythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($pythonCommand -and $pythonCommand.Source -notlike '*\WindowsApps\*') { $candidates += $pythonCommand.Source }
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        try {
            $launched = & $launcher.Source -3.11 -c 'import sys; print(sys.executable)' 2>$null
            if ($LASTEXITCODE -eq 0) { $candidates += "$launched".Trim() }
        } catch { Write-Host 'Python launcher has no usable Python 3.11; checking other locations.' }
    }
    $pythonPath = $null
    foreach ($candidate in $candidates) {
        if (Test-ProjectPython $candidate) { $pythonPath = $candidate; break }
    }
    if (-not $pythonPath) {
        Write-Host 'Installing project-local Python 3.11.9 (no PATH changes)...'
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        $cachePath = Join-Path $projectRoot '.runtime\downloads'
        New-Item -ItemType Directory -Path $cachePath -Force | Out-Null
        $installerPath = Join-Path $cachePath 'python-3.11.9-amd64.exe'
        Invoke-WebRequest -UseBasicParsing -Uri 'https://www.python.org/ftp/python/3.11.9/python-3.11.9-amd64.exe' -OutFile $installerPath
        $signature = Get-AuthenticodeSignature -LiteralPath $installerPath
        if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch 'Python Software Foundation') {
            throw 'Python installer signature verification failed. No installer was executed.'
        }
        $pythonDirectory = Join-Path $projectRoot '.runtime\python311'
        $installerArgs = @('/quiet', 'InstallAllUsers=0', 'PrependPath=0', 'AssociateFiles=0', 'Shortcuts=0', 'Include_launcher=0', 'Include_test=0', 'Include_doc=0', 'Include_tcltk=0', 'Include_pip=1', "TargetDir=`"$pythonDirectory`"")
        $process = Start-Process -FilePath $installerPath -ArgumentList $installerArgs -WindowStyle Hidden -Wait -PassThru
        if ($process.ExitCode -notin @(0, 3010)) { throw "Python installer failed: $($process.ExitCode)" }
        $pythonPath = Join-Path $pythonDirectory 'python.exe'
        if (-not (Test-ProjectPython $pythonPath)) { throw 'Python was not found after installation. Install Python 3.11 x64 from python.org and rerun Setup.bat.' }
    }
    Write-Host "Python: $pythonPath"
    & $pythonPath -B (Join-Path $PSScriptRoot 'setup_windows.py')
    $exitCode = $LASTEXITCODE
} catch {
    Write-Host "Setup failed: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host 'See WINDOWS_SETUP.md. Fix the reported step and rerun Setup.bat.'
} finally {
    if (-not $NoPause) { Read-Host 'Press Enter to close' | Out-Null }
}
exit $exitCode

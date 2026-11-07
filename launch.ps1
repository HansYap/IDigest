param([switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
try {
    $taskAppPath = Join-Path $PSScriptRoot 'app.py'
    $taskDataPath = Join-Path $PSScriptRoot 'data'
    New-Item -ItemType Directory -Path $taskDataPath -Force | Out-Null
    $taskPython = Get-Command python.exe -ErrorAction SilentlyContinue
    $taskPrefix = ''
    if (-not $taskPython) {
        $taskPython = Get-Command py.exe -ErrorAction SilentlyContinue
        $taskPrefix = '-3 '
    }
    if (-not $taskPython) {
        throw 'Morning Signal needs Python 3.10 or newer. Install free Python from python.org, then open this launcher again.'
    }
    $taskVersionArguments = @('-c', 'import sys; print(int(sys.version_info >= (3, 10)))')
    if ($taskPrefix) { $taskVersionArguments = @('-3') + $taskVersionArguments }
    $taskVersionCheck = & $taskPython.Source @taskVersionArguments 2>$null
    if ($LASTEXITCODE -ne 0 -or $taskVersionCheck -ne '1') {
        throw 'Morning Signal needs Python 3.10 or newer. Update Python from python.org and try again.'
    }
    $taskArguments = $taskPrefix + '"' + $taskAppPath + '"'
    if (-not $NoBrowser) { $taskArguments += ' --open' }
    $taskProcess = Start-Process -FilePath $taskPython.Source -ArgumentList $taskArguments -WorkingDirectory $PSScriptRoot -WindowStyle Hidden -PassThru
    Start-Sleep -Milliseconds 1200
    if ($taskProcess.HasExited -and $taskProcess.ExitCode -ne 0) {
        $taskErrorLog = Join-Path $taskDataPath 'app.log'
        if (Test-Path -LiteralPath $taskErrorLog) { Get-Content -LiteralPath $taskErrorLog -Tail 12 | Write-Host }
        throw 'The reader could not start. Details are in the data folder, in app.log.'
    }
    if (-not $NoBrowser) { Write-Host 'Morning Signal is opening in your browser. You can close this window.' }
    else { Write-Host 'Morning Signal is running locally.' }
} catch {
    Write-Host $_.Exception.Message -ForegroundColor Red
    exit 1
}

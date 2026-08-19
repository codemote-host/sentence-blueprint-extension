$ErrorActionPreference = 'Stop'

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$serverPath = Join-Path $projectDir 'local_service\server.py'
$stanzaPython = 'D:\sentence-blueprint-runtime\.venv\Scripts\python.exe'
$bundledPython = 'C:\Users\极客\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

if (Test-Path -LiteralPath $stanzaPython) {
    $pythonExe = $stanzaPython
} elseif (Test-Path -LiteralPath $bundledPython) {
    $pythonExe = $bundledPython
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $pythonExe = (Get-Command python).Source
} elseif (Get-Command py -ErrorAction SilentlyContinue) {
    $pythonExe = (Get-Command py).Source
} else {
    throw '未找到 Python。请安装 Python 3.10+，或修改 start_service.ps1 中的路径。'
}

Write-Host "使用 Python：$pythonExe"
& $pythonExe $serverPath

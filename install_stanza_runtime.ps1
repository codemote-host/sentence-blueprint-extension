param(
    [string]$TargetDir = 'D:\sentence-blueprint-runtime'
)

$ErrorActionPreference = 'Stop'

$projectDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$requirementsPath = Join-Path $projectDir 'local_service\requirements-stanza.txt'
$bundledPython = 'C:\Users\极客\.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe'

if (Test-Path -LiteralPath $bundledPython) {
    $basePython = $bundledPython
} elseif (Get-Command python -ErrorAction SilentlyContinue) {
    $basePython = (Get-Command python).Source
} else {
    throw '未找到可用于创建 Stanza 环境的 Python 3.9+。'
}

$venvDir = Join-Path $TargetDir '.venv'
$pythonExe = Join-Path $venvDir 'Scripts\python.exe'
$modelDir = Join-Path $TargetDir 'stanza_resources'

New-Item -ItemType Directory -Force -Path $TargetDir | Out-Null
if (-not (Test-Path -LiteralPath $pythonExe)) {
    & $basePython -m venv $venvDir
}

& $pythonExe -m pip install --upgrade pip
& $pythonExe -m pip install -r $requirementsPath

$downloadCode = @"
import stanza
stanza.download(
    'en',
    model_dir=r'$modelDir',
    processors='tokenize,pos,lemma,depparse,constituency',
    logging_level='INFO',
)
"@
& $pythonExe -c $downloadCode

Write-Host "Stanza 已安装到：$TargetDir"
Write-Host "模型目录：$modelDir"

#requires -version 5.1
<#
.SYNOPSIS
    LearnWithAI 一键环境引导（克隆完整性一轮新增）：clone 之后跑这一次，环境就到位。

.DESCRIPTION
    做四件事，全部幂等、可重复跑，不硬编码任何本机路径（路径从 $PSScriptRoot 推）：

      1. 前置检查：python / node / npm 是否可用，版本是否够
      2. 建 .venv 并装 requirements.txt + backend/requirements.txt
      3. 前端 npm ci（装 frontend/node_modules）
      4. 一次性准备：python scripts/build_demo_snapshots.py
         （生成学生快照 + 后端答案表 + 证据源码副本，README §0.3 要求先跑一次）

    默认**不**跑验收门禁、**不**构建前端产物 —— 要跑分别加 -Verify / -Build。

    ⚠️ 为什么不直接装进系统 python：本机 `python` 与 `.venv` 恰好都装齐了依赖，
       但别人机器上不一定。装进 .venv 才是"克隆下来就能重现"的做法（见 docs/08 §19.5）。

.PARAMETER SkipFrontend
    跳过前端 npm ci（只想跑后端与 Python 脚本时用）。

.PARAMETER Build
    额外构建前端产物：dist/（正式构建）与 .smoke-dist/（走查 bundle）。

.PARAMETER Verify
    额外跑仓库三道门禁：build_acceptance_report.py / verify_docs.py / verify_sprint0.py。

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File scripts\bootstrap.ps1 -Build -Verify
#>
[CmdletBinding()]
param(
    [switch]$SkipFrontend,
    [switch]$Build,
    [switch]$Verify
)

$ErrorActionPreference = 'Stop'

# ── 路径：全部相对脚本位置，可移植 ────────────────────────────────────────────
$RepoRoot    = Split-Path -Parent $PSScriptRoot
$VenvDir     = Join-Path $RepoRoot '.venv'
$VenvPython  = Join-Path $VenvDir 'Scripts\python.exe'
$FrontendDir = Join-Path $RepoRoot 'frontend'

$script:StepNo = 0
$script:Warned = New-Object System.Collections.ArrayList

function Write-Step {
    param([string]$Text)
    $script:StepNo++
    Write-Host ''
    Write-Host ("[{0}] {1}" -f $script:StepNo, $Text) -ForegroundColor Cyan
    Write-Host ('-' * 68) -ForegroundColor DarkGray
}

function Write-Ok   { param([string]$T) Write-Host ("  [ok]   " + $T) -ForegroundColor Green }
function Write-Warn2{ param([string]$T) Write-Host ("  [warn] " + $T) -ForegroundColor Yellow; [void]$script:Warned.Add($T) }
function Write-Info { param([string]$T) Write-Host ("         " + $T) -ForegroundColor Gray }

# 让失败一定看得见：原生程序的非零退出码不会自己抛异常，必须手动兜住。
function Invoke-Native {
    param(
        [Parameter(Mandatory)][string]$Exe,
        [Parameter(Mandatory)][string[]]$Arguments,
        [string]$WorkDir = $RepoRoot,
        [string]$What = ''
    )
    $display = "$Exe $($Arguments -join ' ')"
    Write-Info $display
    Push-Location $WorkDir
    try {
        & $Exe @Arguments
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
    }
    if ($code -ne 0) {
        $label = if ($What) { $What } else { $display }
        throw ("命令失败（退出码 {0}）：{1}" -f $code, $label)
    }
}

function Find-Python {
    # 1) 已有 .venv 直接用  2) PATH 上的 python  3) py 启动器
    if (Test-Path -LiteralPath $VenvPython) { return $VenvPython }
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }
    $py = Get-Command py -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }
    return $null
}

Write-Host ''
Write-Host 'LearnWithAI · 一键环境引导' -ForegroundColor White
Write-Host ("仓库根目录: " + $RepoRoot)
Write-Host ("PowerShell: " + $PSVersionTable.PSVersion.ToString())

# ── 1. 前置检查 ───────────────────────────────────────────────────────────────
Write-Step '前置检查（python / node / npm）'

$PythonExe = Find-Python
if (-not $PythonExe) {
    throw '找不到 python。请先安装 Python 3.12+（并勾选 Add to PATH），或先手工建好 .venv。'
}

$pyVerText = (& $PythonExe --version 2>&1 | Out-String).Trim()
Write-Ok ("python  : {0}  ({1})" -f $pyVerText, $PythonExe)

# 版本下限：项目文档写明 Python 3.12（docs/00-index.md §一）
$pyVer = [version]([regex]::Match($pyVerText, '\d+\.\d+(\.\d+)?').Value)
if ($pyVer -lt [version]'3.10') {
    Write-Warn2 ("python 版本 {0} 偏低；项目按 3.12 开发（docs/00-index.md §一），可能有语法不兼容" -f $pyVer)
} elseif ($pyVer -lt [version]'3.12') {
    Write-Warn2 ("python 版本 {0} 低于项目使用的 3.12，建议升级" -f $pyVer)
}

$NodeExe = (Get-Command node -ErrorAction SilentlyContinue)
$NpmExe  = (Get-Command npm.cmd -ErrorAction SilentlyContinue)
if (-not $NpmExe) { $NpmExe = (Get-Command npm -ErrorAction SilentlyContinue) }

if ($NodeExe) { Write-Ok ("node    : {0}" -f ((& $NodeExe.Source --version 2>&1 | Out-String).Trim())) }
else          { Write-Warn2 'node 未找到 —— 前端与 jsdom 走查脚本会跑不了（后端与 Python 脚本不受影响）' }

if ($NpmExe)  { Write-Ok ("npm     : {0}" -f $NpmExe.Source) }
else          { Write-Warn2 'npm 未找到 —— 跳过前端依赖安装' }

# ⚠️ npm.ps1 会被 PowerShell 执行策略挡住（docs/06-runbook.md §19.5 实测）；
#    npm.cmd 是同一个东西的 cmd 入口，绕开执行策略，所以优先用它。
$NpmCommand = if ($NpmExe) { $NpmExe.Source } else { $null }
if ($NpmCommand -and $NpmCommand -notlike '*.cmd') {
    Write-Warn2 ("npm 入口不是 npm.cmd（{0}）；若报 npm.ps1 cannot be loaded，请改用 npm.cmd" -f $NpmCommand)
}

# ── 2. Python 依赖 ────────────────────────────────────────────────────────────
Write-Step 'Python 依赖（.venv + requirements.txt）'

if (Test-Path -LiteralPath $VenvPython) {
    Write-Ok ("已有 .venv，直接复用：{0}" -f $VenvDir)
} else {
    Write-Info ("创建虚拟环境：{0}" -f $VenvDir)
    Invoke-Native -Exe $PythonExe -Arguments @('-m', 'venv', $VenvDir) -What '创建 .venv'
    if (-not (Test-Path -LiteralPath $VenvPython)) {
        throw ("venv 建好了但找不到解释器：{0}" -f $VenvPython)
    }
    Write-Ok '虚拟环境已创建'
}

Invoke-Native -Exe $VenvPython -Arguments @('-m', 'pip', 'install', '--upgrade', 'pip') -What '升级 pip'
Invoke-Native -Exe $VenvPython -Arguments @('-m', 'pip', 'install', '-r', (Join-Path $RepoRoot 'requirements.txt')) -What '安装 requirements.txt'
Invoke-Native -Exe $VenvPython -Arguments @('-m', 'pip', 'install', '-r', (Join-Path $RepoRoot 'backend\requirements.txt')) -What '安装 backend/requirements.txt'
Write-Ok 'Python 依赖已装齐（astroid / radon / fastapi / uvicorn / python-multipart）'

# ── 3. 前端依赖 ───────────────────────────────────────────────────────────────
if ($SkipFrontend) {
    Write-Step '前端依赖（已按 -SkipFrontend 跳过）'
    Write-Warn2 '跳过了 npm ci —— 前端 dev/build 与 jsdom 走查脚本暂时跑不了'
} elseif (-not $NpmCommand) {
    Write-Step '前端依赖（无 npm，跳过）'
    Write-Warn2 '没有 npm，跳过了 frontend/node_modules 安装'
} else {
    Write-Step '前端依赖（frontend/ npm ci）'
    if (Test-Path -LiteralPath (Join-Path $FrontendDir 'node_modules')) {
        Write-Ok 'node_modules 已存在，仍执行 npm ci 以保证与 package-lock.json 严格一致'
    }
    if (Test-Path -LiteralPath (Join-Path $FrontendDir 'package-lock.json')) {
        try {
            Invoke-Native -Exe $NpmCommand -Arguments @('ci', '--no-audit', '--no-fund') -WorkDir $FrontendDir -What 'npm ci'
        } catch {
            Write-Warn2 ("npm ci 失败（{0}）；回退到 npm install" -f $_.Exception.Message)
            Invoke-Native -Exe $NpmCommand -Arguments @('install', '--no-audit', '--no-fund') -WorkDir $FrontendDir -What 'npm install'
        }
    } else {
        Write-Warn2 '没有 frontend/package-lock.json，改用 npm install'
        Invoke-Native -Exe $NpmCommand -Arguments @('install', '--no-audit', '--no-fund') -WorkDir $FrontendDir -What 'npm install'
    }
    Write-Ok '前端依赖已装齐'
}

# ── 4. 一次性准备：学生快照 + 答案表 + 证据源码副本 ───────────────────────────
Write-Step '一次性准备（build_demo_snapshots.py）'
Invoke-Native -Exe $VenvPython -Arguments @((Join-Path $RepoRoot 'scripts\build_demo_snapshots.py')) -WorkDir $RepoRoot -What 'build_demo_snapshots.py'
Write-Ok '学生快照 / 后端答案表 / 证据源码副本已生成'

# ── 可选：构建前端产物 ────────────────────────────────────────────────────────
if ($Build) {
    Write-Step '构建前端产物（-Build）'
    if (-not $NpmCommand) { throw '-Build 需要 npm，但没有找到 npm。' }
    $ViteJs = Join-Path $FrontendDir 'node_modules\vite\bin\vite.js'
    if (-not (Test-Path -LiteralPath $ViteJs)) { throw ("找不到 vite 入口：{0}（先确保 npm ci 成功）" -f $ViteJs) }
    # ⚠️ 直接调 node 入口而不是 npm run build：绕开 npm.ps1 执行策略问题（§19.5）
    Invoke-Native -Exe (Get-Command node).Source -Arguments @($ViteJs, 'build') -WorkDir $FrontendDir -What 'vite build（dist/）'
    Invoke-Native -Exe (Get-Command node).Source -Arguments @($ViteJs, 'build', '--config', 'vite.smoke.config.js') -WorkDir $FrontendDir -What 'vite build（.smoke-dist/，走查用）'
    Write-Ok '前端产物已构建：frontend/dist/ 与 frontend/.smoke-dist/'
} else {
    Write-Info '（未构建前端产物；要做前端演示或跑走查，加 -Build，或按 README §0.3 手工跑 vite）'
}

# ── 可选：跑仓库门禁 ──────────────────────────────────────────────────────────
if ($Verify) {
    Write-Step '仓库门禁（-Verify）'
    Invoke-Native -Exe $VenvPython -Arguments @((Join-Path $RepoRoot 'scripts\build_acceptance_report.py')) -WorkDir $RepoRoot -What 'build_acceptance_report.py'
    Invoke-Native -Exe $VenvPython -Arguments @((Join-Path $RepoRoot 'scripts\verify_docs.py')) -WorkDir $RepoRoot -What 'verify_docs.py'
    Invoke-Native -Exe $VenvPython -Arguments @((Join-Path $RepoRoot 'scripts\verify_sprint0.py')) -WorkDir $RepoRoot -What 'verify_sprint0.py'
    Write-Ok '三道门禁全部通过（build_acceptance_report / verify_docs / verify_sprint0）'
} else {
    Write-Info '（未跑门禁；要一次跑完三道，加 -Verify）'
}

# ── 收尾 ──────────────────────────────────────────────────────────────────────
Write-Step '环境就绪 —— 接下来怎么跑'
Write-Host ''
Write-Host '  # 激活虚拟环境（之后 python 就是这个 .venv 里的）' -ForegroundColor Gray
Write-Host ('  .\.venv\Scripts\Activate.ps1') -ForegroundColor White
Write-Host ''
Write-Host '  # 后端（判题 / 源码切片 / 业务图谱 / 教学阶段都要它）' -ForegroundColor Gray
Write-Host '  cd backend; python -m uvicorn app.main:app --host 127.0.0.1 --port 8000' -ForegroundColor White
Write-Host ''
Write-Host '  # 前端（另一个终端）' -ForegroundColor Gray
Write-Host '  cd frontend; npm run dev            # http://127.0.0.1:5173/' -ForegroundColor White
Write-Host ''
Write-Host '  # 门禁与验收（README §0.3 有完整清单）' -ForegroundColor Gray
Write-Host '  python scripts/build_acceptance_report.py' -ForegroundColor White
Write-Host '  python scripts/verify_docs.py' -ForegroundColor White
Write-Host '  python scripts/verify_sprint0.py' -ForegroundColor White
Write-Host ''
Write-Host '  ⚠️ 改了后端代码或 engine/lexicon/*.json 必须重启 uvicorn（启动命令没有 --reload，见 docs/06 §19.5）' -ForegroundColor Yellow

if ($script:Warned.Count -gt 0) {
    Write-Host ''
    Write-Host ("本次有 {0} 条警告：" -f $script:Warned.Count) -ForegroundColor Yellow
    foreach ($w in $script:Warned) { Write-Host ("  - " + $w) -ForegroundColor Yellow }
}

Write-Host ''
Write-Host '[done] bootstrap 完成' -ForegroundColor Green
exit 0

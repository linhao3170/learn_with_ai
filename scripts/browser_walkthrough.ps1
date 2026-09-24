# ============================================================================
# 开发期浏览器走查（P0 walkthrough）
# ============================================================================
#
# 为什么需要它：
#   Sprint 0 之后，前端的验证只到"编译 + 模板绑定 + 模块级逻辑测试"。
#   但 Vue 的交互逻辑只有真的派发 DOM 事件才算验证过 —— 本脚本用**真实的无头
#   Chrome** 打开真实 App（frontend/__smoke.html 会挂载 /src/main.js），
#   用真实 DOM 事件点击选项 / 提交 / 切项目，再把断言结果取回来。
#
# 前置：
#   1. 后端在 127.0.0.1:8000 运行（在线场景）
#   2. 前端 dev server 在 127.0.0.1:5173 运行
#
# 用法（注意：本机执行策略禁用了脚本，需要用 Bypass 启动）：
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\browser_walkthrough.ps1
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\browser_walkthrough.ps1 -Project python_dotenv
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\browser_walkthrough.ps1 -Offline   # 先停掉后端
#   powershell -NoProfile -ExecutionPolicy Bypass -File scripts\browser_walkthrough.ps1 -SkipShots
#
# 产物：_task_scripts/walkthrough/<scenario>-<project>.{html,png}
#
# 兼容性说明：本脚本刻意只使用 Windows PowerShell 5.1 也支持的语法
# （chrome 的参数一律加引号，因为 5.1 会把 `--headless` 当成一元减运算符解析）。
# ============================================================================

param(
  [string]$Project = 'lab_safety_assistant',
  [switch]$Offline,
  [switch]$SkipShots,
  [string]$BaseUrl = 'http://127.0.0.1:5173',
  [int]$WaitMs = 9000
)

$ErrorActionPreference = 'Stop'
$repo = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $repo

# 找浏览器。刻意不用 ${env:ProgramFiles(x86)} 这种写法 ——
# Windows PowerShell 5.1 的解析器对带括号的 ${...} 处理不一致，直接用 API 取更稳。
$pf = [Environment]::GetEnvironmentVariable('ProgramFiles')
$pf86 = [Environment]::GetEnvironmentVariable('ProgramFiles(x86)')
$chromeCandidates = @(
  (Join-Path $pf 'Google\Chrome\Application\chrome.exe'),
  (Join-Path $pf86 'Google\Chrome\Application\chrome.exe'),
  (Join-Path $pf 'Microsoft\Edge\Application\msedge.exe'),
  (Join-Path $pf86 'Microsoft\Edge\Application\msedge.exe')
)
$chrome = $null
foreach ($c in $chromeCandidates) { if ($c -and (Test-Path $c)) { $chrome = $c; break } }
if (-not $chrome) { throw "找不到 Chrome / Edge，无法执行浏览器走查" }

$outDir = Join-Path $repo '_task_scripts\walkthrough'
$profileDir = Join-Path $repo '_task_scripts\chrome-profile'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
New-Item -ItemType Directory -Force -Path $profileDir | Out-Null

$scenario = 'online'
if ($Offline) { $scenario = 'offline' }
$tag = "$scenario-$Project"
$smokeUrl = "$BaseUrl/__smoke.html?scenario=$scenario&project=$Project"

# 公共参数（每个都加引号，避免 5.1 把它们当运算符）
$commonArgs = @(
  '--headless=new',
  '--disable-gpu',
  '--no-sandbox',
  '--hide-scrollbars',
  '--disable-crash-reporter',
  '--disable-breakpad',
  '--no-first-run',
  '--no-default-browser-check',
  '--window-size=1680,1200',
  "--virtual-time-budget=$WaitMs",
  "--user-data-dir=$profileDir"
)

Write-Host "=== 浏览器走查 ===" -ForegroundColor Cyan
Write-Host "browser : $chrome"
Write-Host "scenario: $scenario"
Write-Host "project : $Project"
Write-Host "url     : $smokeUrl"
Write-Host ""

# ---- 1) 断言：打开 __smoke.html，dump-dom 取回报告 ----
$domPath = Join-Path $outDir "$tag.html"
& $chrome @commonArgs '--dump-dom' $smokeUrl > $domPath
if (-not (Test-Path $domPath)) { throw "Chrome 没有输出 DOM。产物：$domPath" }
if ((Get-Item $domPath).Length -eq 0) { throw "Chrome 输出的 DOM 为空（可能被沙箱阻止了子进程）。产物：$domPath" }

$dom = Get-Content $domPath -Raw -Encoding UTF8
$verdict = 'UNKNOWN'
if ($dom -match 'SMOKE_RESULT:\s*(PASS|FAIL)') { $verdict = $Matches[1] }
$total = '?'
if ($dom -match 'SMOKE_TOTAL:\s*(\d+)') { $total = $Matches[1] }
$failed = '?'
if ($dom -match 'SMOKE_FAILED:\s*(\d+)') { $failed = $Matches[1] }

$reportText = ''
if ($dom -match '(?s)<pre id="smoke-report">(.*?)</pre>') {
  $reportText = $Matches[1]
  $reportText = $reportText.Replace('&lt;', '<').Replace('&gt;', '>').Replace('&quot;', '"').Replace('&amp;', '&')
}
Write-Host $reportText
Write-Host ""

# ---- 2) 出图（真实渲染，供人工核对）----
if (-not $SkipShots) {
  $shots = @(
    @{ name = "app-home-$Project";     url = "$BaseUrl/?project=$Project" },
    @{ name = "smoke-$tag";            url = $smokeUrl }
  )
  foreach ($case in $shots) {
    $png = Join-Path $outDir "$($case.name).png"
    & $chrome @commonArgs "--screenshot=$png" $case.url | Out-Null
    if (Test-Path $png) {
      $size = (Get-Item $png).Length
      Write-Host ("截图 {0,-32} {1,9} B" -f $case.name, $size)
    } else {
      Write-Host ("截图 {0,-32} 失败" -f $case.name) -ForegroundColor Yellow
    }
  }
}

Write-Host ""
Write-Host "产物目录: $outDir"
if ($verdict -eq 'PASS') {
  Write-Host "结果: PASS（$total 项，0 失败）" -ForegroundColor Green
  exit 0
}
Write-Host "结果: $verdict（$total 项，$failed 失败）" -ForegroundColor Red
exit 1

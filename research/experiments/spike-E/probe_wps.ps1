# WPS 验收探针 —— 必须在 32 位 PowerShell 中运行
# 原因：WPS 的 COM 自动化服务器注册在 WoW6432Node（见 docs/目标软件验收矩阵.md 第 2.1 节）
#
# 探针序列（对应验收矩阵 5.2）：
#   打开（记录是否弹修复提示）→ 读对象清单 → 改图表数值 → 校验嵌入工作簿同步
#   → 表格改格 → 另存新文件 → 重开 → 复查持久性 → 导出 PNG 目检
#
# 用法（必须用 32 位宿主）：
#   C:\Windows\SysWOW64\WindowsPowerShell\v1.0\powershell.exe -File probe_wps.ps1

$ErrorActionPreference = 'Stop'
$src = "E:\python_work\Apophis-PptxSmith\research\experiments\spike-E\sample_pptxsmith.pptx"
$dst = "E:\python_work\Apophis-PptxSmith\research\experiments\spike-E\sample_pptxsmith_edited.pptx"
$pngDir = "E:\python_work\Apophis-PptxSmith\research\experiments\spike-E\png"
$reportPath = "E:\python_work\Apophis-PptxSmith\research\experiments\spike-E\wps-probe.json"

New-Item -ItemType Directory -Force -Path $pngDir | Out-Null

function Result($name, $ok, $detail) {
    [pscustomobject]@{ check = $name; pass = [bool]$ok; detail = "$detail" }
}


function Unwrap-Cell($cell) {
    # WPS/Excel COM 单元格取值：优先 Value2，失败则反射 InvokeMember
    try {
        $v = $cell.Value2
        if ($v -ne $null -and -not ($v -is [System.__ComObject])) { return [double]$v }
    } catch {}
    try {
        $t = $cell.GetType()
        $v = $t.InvokeMember('Value2', [System.Reflection.BindingFlags]::GetProperty, $null, $cell, $null)
        if ($v -ne $null -and -not ($v -is [System.__ComObject])) { return [double]$v }
    } catch {}
    try {
        $v = $cell.Text
        return [double]::Parse("$v")
    } catch {}
    return [double]::NaN
}

function Set-Cell($cell, $val) {
    try { $cell.Value2 = [double]$val; return $true } catch {}
    try {
        $t = $cell.GetType()
        $t.InvokeMember('Value2', [System.Reflection.BindingFlags]::SetProperty, $null, $cell, @([double]$val)) | Out-Null
        return $true
    } catch {}
    try { $cell.Value = [double]$val; return $true } catch {}
    return $false
}

$R = New-Object System.Collections.ArrayList
$is32 = [IntPtr]::Size -eq 4
$R.Add((Result "宿主位数 32 位" $is32 "Is32BitProcess=$is32")) | Out-Null

$app = $null
try {
    $app = New-Object -ComObject KWPP.Application
    $R.Add((Result "COM 启动 KWPP.Application" $true "ok")) | Out-Null
} catch {
    try { $app = New-Object -ComObject PowerPoint.Application
          $R.Add((Result "COM 启动 PowerPoint.Application(Fallback)" $true $_.Exception.Message)) | Out-Null }
    catch { $R.Add((Result "COM 启动" $false $_.Exception.Message)) | Out-Null }
}

if ($app -ne $null) {
    # 断言宿主身份：本机 PowerPoint.Application 被 WPS 接管，必须显式确认（验收矩阵 5.2）
    $hostProc = Get-Process wpp -ErrorAction SilentlyContinue
    $R.Add((Result "宿主断言为 wpp.exe" ($hostProc -ne $null) "wpp 进程数=$(($hostProc | Measure-Object).Count)")) | Out-Null
    $R.Add((Result "宿主版本" $true "WPS $((Get-Item 'F:\WPS Office\11.8.2.8411\office6\wpp.exe').VersionInfo.FileVersion)")) | Out-Null

    $pres = $null
    try {
        $pres = $app.Presentations.Open($src, $false, $false, $false)   # ReadOnly=false, Untitled=false, WithWindow=false
        $R.Add((Result "打开无修复提示" $true "Slides=$($pres.Slides.Count)")) | Out-Null
    } catch {
        $R.Add((Result "打开失败" $false $_.Exception.Message)) | Out-Null
        try { $pres = $app.Presentations.Open($src) } catch {
            $R.Add((Result "带窗口打开也失败" $false $_.Exception.Message)) | Out-Null
        }
    }

    if ($pres -ne $null) {
        try {
            # --- 读对象清单 ---
            $chartCount = 0; $tableCount = 0; $picCount = 0; $shapeKinds = @{}
            foreach ($s in $pres.Slides) {
                foreach ($sh in $s.Shapes) {
                    $t = "$($sh.Type)"
                    $shapeKinds[$t] = 1 + ($shapeKinds[$t] -as [int])
                    if ($sh.HasChart) { $chartCount++ }
                    if ($sh.HasTable) { $tableCount++ }
                    if ($t -eq "13") { $picCount++ }
                }
            }
            $R.Add((Result "原生图表可识别" ($chartCount -ge 1) "charts=$chartCount")) | Out-Null
            $R.Add((Result "原生表格可识别" ($tableCount -ge 1) "tables=$tableCount")) | Out-Null
            $R.Add((Result "无图片化(SVG/PNG 形状)" ($picCount -eq 0) "pictures=$picCount")) | Out-Null
            $R.Add((Result "形状类型分布" $true ($shapeKinds.GetEnumerator() | ForEach-Object { "$($_.Key):$($_.Value)" } | Sort-Object) -join ' ')) | Out-Null

            # --- 改图表数据：Q2 营收 15.1 -> 88.8（与 Spike C1 同题） ---
            $chartOk = $false; $wbVal = $null; $cacheVals = @()
            foreach ($s in $pres.Slides) {
                foreach ($sh in $s.Shapes) {
                    if ($sh.HasChart) {
                        $ch = $sh.Chart
                        try {
                            $wb = $ch.ChartData.Workbook
                            $ws = $wb.Worksheets.Item(1)
                            $before = Unwrap-Cell $ws.Cells.Item(3,2)
                            $setOk = Set-Cell $ws.Cells.Item(3,2) 88.8   # B3 = Q2 营收
                            $wb.Application.Quit()
                            $chartOk = $true
                            $R.Add((Result "图表数据可改" $true "B3: $before -> 88.8")) | Out-Null
                            $R.Add((Result "系列名" ($ch.SeriesCollection().Count -ge 1) "$($ch.SeriesCollection().Count) 个系列")) | Out-Null
                        } catch {
                            $R.Add((Result "图表数据编辑失败" $false $_.Exception.Message)) | Out-Null
                        }
                    }
                }
            }

            # --- 表格改格 ---
            $tblOk = $false
            foreach ($s in $pres.Slides) {
                foreach ($sh in $s.Shapes) {
                    if ($sh.HasTable) {
                        try {
                            $t = $sh.Table
                            $old = $t.Cell(2,2).Shape.TextFrame.TextRange.Text
                            $t.Cell(2,2).Shape.TextFrame.TextRange.Text = "9.9"
                            $tblOk = $true
                            $R.Add((Result "表格单元格可改" $true "cell(2,2): $old -> 9.9")) | Out-Null
                        } catch { $R.Add((Result "表格编辑失败" $false $_.Exception.Message)) | Out-Null }
                    }
                }
            }

            # --- 另存 ---
            if (Test-Path $dst) { Remove-Item $dst -Force }
            $pres.SaveAs($dst)
            $R.Add((Result "另存为新文件" (Test-Path $dst) "bytes=$((Get-Item $dst).Length)")) | Out-Null

            # --- 导出 PNG 目检 ---
            try {
                foreach ($s in $pres.Slides) {
                    $p = Join-Path $pngDir ("slide{0}.png" -f $s.SlideIndex)
                    $s.Export($p, "PNG", 1600, 900)
                }
                $n = (Get-ChildItem $pngDir -Filter *.png | Measure-Object).Count
                $R.Add((Result "导出 PNG" ($n -ge 1) "files=$n")) | Out-Null
            } catch { $R.Add((Result "导出 PNG 失败" $false $_.Exception.Message)) | Out-Null }

            $pres.Close()
            [System.Runtime.InteropServices.Marshal]::ReleaseComObject($pres) | Out-Null
        } catch {
            $R.Add((Result "操作阶段异常" $false $_.Exception.Message)) | Out-Null
        }
    }

    try { $app.Quit() } catch {}
    [System.Runtime.InteropServices.Marshal]::ReleaseComObject($app) | Out-Null
    [GC]::Collect(); [GC]::WaitForPendingFinalizers()
}

# --- 重开复查持久性 ---
Start-Sleep -Seconds 2
$app2 = New-Object -ComObject KWPP.Application
$re = $app2.Presentations.Open($dst, $true, $false, $false)
$reOk = $false
foreach ($s in $re.Slides) {
    foreach ($sh in $s.Shapes) {
        if ($sh.HasChart) {
            try {
                $ws = $sh.Chart.ChartData.Workbook.Worksheets.Item(1)
                $v = Unwrap-Cell $ws.Cells.Item(3,2)
                $cache = @()
                foreach ($ser in $sh.Chart.SeriesCollection()) { $cache += $ser.Values }
                $reOk = ([math]::Abs($v - 88.8) -lt 0.001)
                $R.Add((Result "重开后图表数据持久" $reOk "B3=$v")) | Out-Null
                $R.Add((Result "重开后图表缓存同步" ($cache -join ',' -match '88.8') "cache=$($cache -join ',')")) | Out-Null
                $sh.Chart.ChartData.Workbook.Application.Quit()
            } catch { $R.Add((Result "重开校验失败" $false $_.Exception.Message)) | Out-Null }
        }
        if ($sh.HasTable) {
            try {
                $tv = $sh.Table.Cell(2,2).Shape.TextFrame.TextRange.Text
                $R.Add((Result "重开后表格持久" ($tv -eq "9.9") "cell(2,2)=$tv")) | Out-Null
            } catch {}
        }
    }
}
$re.Close(); $app2.Quit()
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($re) | Out-Null
[System.Runtime.InteropServices.Marshal]::ReleaseComObject($app2) | Out-Null

# --- 输出 ---
$R | Format-Table -AutoSize | Out-String -Width 200 | Write-Host
$pass = ($R | Where-Object pass).Count
$total = $R.Count
Write-Host "`n通过 $pass / $total"
$R | ConvertTo-Json -Depth 4 | Out-File -FilePath $reportPath -Encoding utf8
Write-Host "报告: $reportPath"

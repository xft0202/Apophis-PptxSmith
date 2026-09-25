$ErrorActionPreference = 'Continue'
$src = "E:\python_work\Apophis-PptxSmith\research\experiments\sandun-live\downloads\sandun_generated.pptx"
$app = New-Object -ComObject KWPP.Application
$p = $app.Presentations.Open($src, $false, $false, $false)
Write-Host "Slides: $($p.Slides.Count)"
$charts=0; $tables=0; $pics=0; $textboxes=0; $shapes=0
foreach ($s in $p.Slides) {
  foreach ($sh in $s.Shapes) {
    $shapes++
    if ($sh.HasChart) { $charts++ }
    if ($sh.HasTable) { $tables++ }
    $t = "$($sh.Type)"
    if ($t -eq "13") { $pics++ }
    if ($t -eq "17") { $textboxes++ }
  }
}
Write-Host "Shapes=$shapes Charts=$charts Tables=$tables Pictures=$pics TextBoxes=$textboxes"
Write-Host "--- 检查能否编辑图表数据 ---"
foreach ($s in $p.Slides) {
  foreach ($sh in $s.Shapes) {
    if ($sh.HasChart) {
      try {
        $wb = $sh.Chart.ChartData.Workbook
        Write-Host "  ChartData.Workbook OK -> 可改数据"
        $wb.Application.Quit()
      } catch { Write-Host "  ChartData 不可用: $($_.Exception.Message)" }
    }
  }
}
Write-Host "--- 检查文字是否可读（散文完整性）---"
$i=0
foreach ($s in $p.Slides) {
  $i++
  if ($i -le 2) {
    foreach ($sh in $s.Shapes) {
      if ($sh.HasTextFrame -and $sh.TextFrame.HasText) {
        $t = $sh.TextFrame.TextRange.Text
        if ($t.Length -gt 8) { Write-Host "  P${i}: $($t.Substring(0,[Math]::Min(60,$t.Length)))" }
      }
    }
  }
}
$p.Close()
$app.Quit()

# ============================================
# 寰俊娑堟伅鐩戞帶涓庤嚜鍔ㄥ洖澶嶆満鍣ㄤ汉
# 浣跨敤 UIAutomation 鎶€鏈紝閫傞厤鎵€鏈?Windows 鐢佃剳
# ============================================

param(
    [string]$ConfigPath = ".\wechat_config.json"
)

# 瀵煎叆蹇呰鐨勭▼搴忛泦
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes

# ==================== 閰嶇疆鍖哄煙 ====================

# 榛樿閰嶇疆锛堝鏋滈厤缃枃浠朵笉瀛樺湪鍒欎娇鐢ㄦ閰嶇疆锛?$DefaultConfig = @{
    # 鐩戞帶鐨勫井淇¤仈绯讳汉锛堝悕绉版垨澶囨敞鍚嶏級
    MonitoredContacts = @(
        "寮犱笁",
        "鏉庡洓"
        # 鍦ㄨ繖閲屾坊鍔犳洿澶氳仈绯讳汉...
    )

    # 娑堟伅瑙勫垯锛氬叧閿瘝 -> 鍥炲鍐呭
    MessageRules = @(
        @{
            Keywords = @("浣犲ソ", "鍦ㄥ悧", "鍦ㄤ笉鍦?)
            Reply = "浣犲ソ锛佹垜鐜板湪涓嶅湪鐢佃剳鏃侊紝绋嶅悗鍥炲浣爚"
        },
        @{
            Keywords = @("浠锋牸", "澶氬皯閽?, "鎶ヤ环")
            Reply = "璇风◢绛夛紝鎴戞煡涓€涓嬩环鏍煎悗鍥炲鎮ㄣ€?
        },
        @{
            Keywords = @("鍙戣揣", "蹇€?, "鐗╂祦")
            Reply = "鎮ㄥソ锛屽彂璐т俊鎭凡璁板綍锛屾垜浠細灏藉揩澶勭悊銆?
        }
        # 鍦ㄨ繖閲屾坊鍔犳洿澶氳鍒?..
    )

    # 榛樿鍥炲锛堝綋娌℃湁鍖归厤瑙勫垯鏃讹級
    DefaultReply = "鏀跺埌鎮ㄧ殑娑堟伅锛屾垜浼氬敖蹇洖澶嶃€?

    # 鎵弿闂撮殧锛堢锛?    ScanInterval = 3

    # 鏄惁鍚敤榛樿鍥炲锛堟病鏈夊尮閰嶅叧閿瘝鏃舵槸鍚﹀洖澶嶏級
    EnableDefaultReply = $false
}

# ==================== 鏍稿績鍔熻兘 ====================

class WeChatBot {
    [System.Windows.Automation.AutomationElement]$MainWindow
    [hashtable]$ProcessedMessages
    [hashtable]$Config

    WeChatBot([hashtable]$config) {
        $this.Config = $config
        $this.ProcessedMessages = @{}
    }

    # 鏌ユ壘寰俊涓荤獥鍙?    [bool]FindWeChatWindow() {
        try {
            $rootElement = [System.Windows.Automation.AutomationElement]::RootElement
            $condition = New-Object System.Windows.Automation.PropertyCondition(
                [System.Windows.Automation.AutomationElement]::ClassNameProperty,
                "WeChatMainWndForPC"
            )
            $this.MainWindow = $rootElement.FindFirst(
                [System.Windows.Automation.TreeScope]::Children,
                $condition
            )

            if ($null -eq $this.MainWindow) {
                # 灏濊瘯閫氳繃绐楀彛鏍囬鏌ユ壘
                $nameCondition = New-Object System.Windows.Automation.PropertyCondition(
                    [System.Windows.Automation.AutomationElement]::NameProperty,
                    "寰俊"
                )
                $this.MainWindow = $rootElement.FindFirst(
                    [System.Windows.Automation.TreeScope]::Children,
                    $nameCondition
                )
            }

            return $null -ne $this.MainWindow
        }
        catch {
            Write-Warning "鏌ユ壘寰俊绐楀彛澶辫触: $_"
            return $false
        }
    }

    # 鑾峰彇娑堟伅鍒楄〃
    [array]GetMessages() {
        $messages = @()

        try {
            if ($null -eq $this.MainWindow) {
                return $messages
            }

            # 鏌ユ壘娑堟伅鍒楄〃鎺т欢
            $listCondition = New-Object System.Windows.Automation.PropertyCondition(
                [System.Windows.Automation.AutomationElement]::ControlTypeProperty,
                [System.Windows.Automation.ControlType]::List
            )

            $messageList = $this.MainWindow.FindAll(
                [System.Windows.Automation.TreeScope]::Descendants,
                $listCondition
            )

            foreach ($item in $messageList) {
                try {
                    $messageText = $item.Current.Name
                    if ([string]::IsNullOrEmpty($messageText)) {
                        # 灏濊瘯鑾峰彇瀛愬厓绱犵殑鏂囨湰
                        $textPattern = $item.GetCurrentPattern([System.Windows.Automation.TextPattern]::Pattern)
                        if ($null -ne $textPattern) {
                            $messageText = $textPattern.DocumentRange.GetText(-1)
                        }
                    }

                    if (-not [string]::IsNullOrEmpty($messageText)) {
                        $messages += @{
                            Element = $item
                            Text = $messageText
                            Timestamp = Get-Date -Format "HH:mm:ss"
                        }
                    }
                }
                catch {
                    # 蹇界暐鍗曚釜娑堟伅鐨勮В鏋愰敊璇?                }
            }
        }
        catch {
            Write-Warning "鑾峰彇娑堟伅澶辫触: $_"
        }

        return $messages
    }

    # 婵€娲诲井淇＄獥鍙?    [void]ActivateWindow() {
        try {
            if ($null -ne $this.MainWindow) {
                $windowPattern = $this.MainWindow.GetCurrentPattern([System.Windows.Automation.WindowPattern]::Pattern)
                if ($null -ne $windowPattern) {
                    $windowPattern.SetWindowVisualState([System.Windows.Automation.WindowVisualState]::Normal)
                }
                $this.MainWindow.SetFocus()
            }
        }
        catch {
            Write-Warning "婵€娲荤獥鍙ｅけ璐? $_"
        }
    }

    # 鍙戦€佹秷鎭?    [void]SendMessage([string]$message) {
        try {
            $this.ActivateWindow()
            Start-Sleep -Milliseconds 500

            # 鍙戦€佸埌鍓创鏉?            [System.Windows.Forms.Clipboard]::SetText($message)

            # 妯℃嫙 Ctrl+V 绮樿创
            $wshell = New-Object -ComObject WScript.Shell
            $wshell.SendKeys("^v")
            Start-Sleep -Milliseconds 300

            # 妯℃嫙 Enter 鍙戦€?            $wshell.SendKeys("{ENTER}")

            Write-Host "鉁?娑堟伅宸插彂閫? $message" -ForegroundColor Green
        }
        catch {
            Write-Warning "鍙戦€佹秷鎭け璐? $_"
        }
    }

    # 鍖归厤瑙勫垯
    [string]MatchRule([string]$message, [string]$contactName) {
        # 妫€鏌ヨ仈绯讳汉鏄惁鍦ㄧ洃鎺у垪琛?        $isMonitored = $false
        foreach ($contact in $this.Config.MonitoredContacts) {
            if ($message -like "*$contact*" -or $contactName -like "*$contact*") {
                $isMonitored = $true
                break
            }
        }

        if (-not $isMonitored -and $this.Config.MonitoredContacts.Count -gt 0) {
            return $null
        }

        # 鍖归厤鍏抽敭璇嶈鍒?        foreach ($rule in $this.Config.MessageRules) {
            foreach ($keyword in $rule.Keywords) {
                if ($message -like "*$keyword*") {
                    return $rule.Reply
                }
            }
        }

        # 杩斿洖榛樿鍥炲
        if ($this.Config.EnableDefaultReply) {
            return $this.Config.DefaultReply
        }

        return $null
    }
}

# ==================== 涓荤▼搴?====================

function Load-Config([string]$path) {
    if (Test-Path $path) {
        try {
            $json = Get-Content $path -Raw -Encoding UTF8
            $config = $json | ConvertFrom-Json
            Write-Host "鉁?閰嶇疆鏂囦欢鍔犺浇鎴愬姛: $path" -ForegroundColor Green
            return $config
        }
        catch {
            Write-Warning "閰嶇疆鏂囦欢瑙ｆ瀽澶辫触锛屼娇鐢ㄩ粯璁ら厤缃? $_"
            return $DefaultConfig
        }
    }
    else {
        # 鍒涘缓榛樿閰嶇疆鏂囦欢
        $DefaultConfig | ConvertTo-Json -Depth 10 | Out-File $path -Encoding UTF8
        Write-Host "馃摑 宸插垱寤洪粯璁ら厤缃枃浠? $path" -ForegroundColor Yellow
        return $DefaultConfig
    }
}

function Main {
    Write-Host @"
========================================
   寰俊娑堟伅鐩戞帶涓庤嚜鍔ㄥ洖澶嶆満鍣ㄤ汉
   鐗堟湰: 1.0
   浣滆€? QClaw Assistant
========================================
"@ -ForegroundColor Cyan

    # 鍔犺浇閰嶇疆
    $config = Load-Config $ConfigPath

    Write-Host "`n馃搵 鐩戞帶鑱旂郴浜? $($config.MonitoredContacts -join ', ')" -ForegroundColor Yellow
    Write-Host "馃摑 宸查厤缃鍒? $($config.MessageRules.Count) 鏉? -ForegroundColor Yellow
    Write-Host "鈴?鎵弿闂撮殧: $($config.ScanInterval) 绉抈n" -ForegroundColor Yellow

    # 鍒涘缓鏈哄櫒浜哄疄渚?    $bot = [WeChatBot]::new($config)

    # 妫€鏌ュ井淇℃槸鍚﹁繍琛?    Write-Host "馃攳 姝ｅ湪鏌ユ壘寰俊绐楀彛..." -ForegroundColor Cyan
    if (-not $bot.FindWeChatWindow()) {
        Write-Host "鉂?鏈壘鍒板井淇＄獥鍙ｏ紝璇风‘淇濆井淇″凡鐧诲綍骞朵繚鎸佺獥鍙ｆ墦寮€" -ForegroundColor Red
        Write-Host "鎻愮ず: 鑴氭湰灏嗗湪鍚庡彴鎸佺画灏濊瘯杩炴帴..." -ForegroundColor Yellow
    }
    else {
        Write-Host "鉁?宸茶繛鎺ュ埌寰俊绐楀彛" -ForegroundColor Green
    }

    # 涓诲惊鐜?    Write-Host "`n馃殌 鏈哄櫒浜哄凡鍚姩锛屾寜 Ctrl+C 鍋滄`n" -ForegroundColor Green

    while ($true) {
        try {
            # 閲嶆柊鏌ユ壘绐楀彛锛堥槻姝㈠井淇￠噸鍚級
            if ($null -eq $bot.MainWindow) {
                $bot.FindWeChatWindow()
            }

            if ($null -ne $bot.MainWindow) {
                # 鑾峰彇鏈€鏂版秷鎭?                $messages = $bot.GetMessages()

                foreach ($msg in $messages) {
                    $msgKey = "$($msg.Timestamp)-$($msg.Text.Substring(0, [Math]::Min(50, $msg.Text.Length)))"

                    # 妫€鏌ユ槸鍚﹀凡澶勭悊
                    if (-not $bot.ProcessedMessages.ContainsKey($msgKey)) {
                        $bot.ProcessedMessages[$msgKey] = $true

                        # 鎵撳嵃娑堟伅
                        Write-Host "[$(Get-Date -Format 'HH:mm:ss')] 馃摡 鏂版秷鎭? $($msg.Text)" -ForegroundColor White

                        # 鍖归厤瑙勫垯骞跺洖澶?                        $reply = $bot.MatchRule($msg.Text, "")
                        if (-not [string]::IsNullOrEmpty($reply)) {
                            Write-Host "   鈫╋笍 鑷姩鍥炲: $reply" -ForegroundColor Cyan
                            $bot.SendMessage($reply)
                        }
                    }
                }

                # 娓呯悊鏃ф秷鎭褰曪紙淇濈暀鏈€杩?00鏉★級
                if ($bot.ProcessedMessages.Count -gt 100) {
                    $bot.ProcessedMessages.Clear()
                }
            }

            Start-Sleep -Seconds $config.ScanInterval
        }
        catch {
            Write-Warning "杩愯鍑洪敊: $_"
            Start-Sleep -Seconds 5
        }
    }
}

# 鍚姩涓荤▼搴?Main

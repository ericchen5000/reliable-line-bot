# 定承資訊 AI 客服管理系統

這是一套提供 LINE 與官網 WEB 使用的 AI 客服系統，並附有後台管理介面。系統可以優先用 FAQ、公司資料、KB 知識庫、網站索引回答問題，最後才交給 AI 生成回覆。

## 主要功能

### LINE 客服

- 使用者可透過 LINE 官方帳號提問。
- 系統會依照資料來源優先順序自動回答。
- 支援 LINE 使用者資訊記錄，例如暱稱、User ID、語言、頭像等。
- 支援圖片訊息辨識，若圖片含文字可嘗試 OCR 或 Vision API。

### WEB 官網客服

- 可嵌入定承資訊官網作為右下角對話小工具。
- 支援文字提問。
- 支援 WEB 訪客 session、瀏覽器、裝置與 User Agent 記錄。
- 支援圖片上傳辨識。
- 可記錄聯絡表單資訊，方便後台追蹤商機。

### 後台管理

後台主要頁面：

- `Dashboard`：營運總覽、健康檢查、網站索引狀態、圖表與建議。
- `LOGS`：查看 LINE / WEB 對話紀錄、來源、延遲、IP、商機意圖與品質標記。
- `知識管理`：管理 FAQ、網站索引網址、KB 文件。
- `測試`：直接在後台測試 AI 客服回答流程。
- `帳號管理`：管理後台帳號、權限、登入紀錄、操作紀錄與後台更新紀錄。

## 回答來源優先順序

目前回答問題大致依照以下順序：

1. FAQ
2. 公司資料或固定規則
3. KB 知識庫文件
4. 網站索引
5. AI 客服生成回答

這樣設計的原因是：越前面的資料越可控、越準確；越後面的資料越彈性，但也越需要檢查。

## 重要資料夾與檔案

```text
app.py                      主程式與 LINE / WEB API
dashboard.py                Dashboard 後台首頁
logs.py                     LOGS 管理頁與匯出
faq.py                      知識管理頁
admin_tools.py              後台登入、權限、操作紀錄
admin_ui.py                 共用後台導覽與 Admin Bar
deepseek.py                 AI API 呼叫
site_index.py               網站索引管理頁
services/search_index.py    網站索引建立
services/retriever.py       知識檢索
data/faq.json               FAQ 資料
data/urls.json              指定搜尋網站
data/site_index.json        已建立的網站索引
data/admin_changelog.json   後台最近更新紀錄
knowledge/txt/              KB 文字知識庫
logs/chat_logs.json         對話紀錄
static/admin-logo.png       後台 Logo
```

## 環境變數

請在 `.env` 設定必要資訊。

```env
LINE_CHANNEL_ACCESS_TOKEN=
LINE_CHANNEL_SECRET=
DEEPSEEK_API_KEY=
DEEPSEEK_API_URL=https://api.deepseek.com/v1/chat/completions
ADMIN_AUTH_SECRET=
WEB_CHAT_ALLOWED_ORIGINS=https://www.reliable.com.tw,https://reliable.com.tw
SITE_INDEX_INTERVAL_HOURS=24
VISION_API_URL=
VISION_API_KEY=
VISION_MODEL=gpt-4o-mini
```

說明：

- `LINE_CHANNEL_ACCESS_TOKEN`：LINE Bot 存取權杖。
- `LINE_CHANNEL_SECRET`：LINE Bot Channel Secret。
- `DEEPSEEK_API_KEY`：DeepSeek API Key。
- `ADMIN_AUTH_SECRET`：後台登入 cookie 簽章用，建議放一串很長的隨機字串。
- `WEB_CHAT_ALLOWED_ORIGINS`：允許呼叫 WEB 客服 API 的網站來源。
- `SITE_INDEX_INTERVAL_HOURS`：網站索引自動重建間隔。
- `VISION_API_URL` / `VISION_API_KEY`：圖片辨識 API，未設定時仍可嘗試本機 OCR。

## 本機啟動

建立虛擬環境：

```bash
python3 -m venv venv
source venv/bin/activate
```

安裝套件：

```bash
pip install fastapi uvicorn python-dotenv requests beautifulsoup4 line-bot-sdk python-multipart
```

啟動服務：

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8000
```

後台網址：

```text
http://127.0.0.1:8000/
```

第一次進後台時，如果尚未建立管理者帳號，系統會要求先建立第一位管理員。

## VPS 更新流程

目前使用 GitHub 作為 Mac 與 VPS 的同步中繼。

一般流程：

1. Mac 本機修改檔案。
2. Commit 並 push 到 GitHub。
3. 到 VPS 執行 `git pull`。
4. 重新啟動 `uvicorn` 或 systemd service。

範例：

```bash
git pull
systemctl restart line-bot
```

如果 VPS 有本機資料檔修改，可能會遇到 git 衝突。常見資料檔如：

```text
data/faq.json
data/urls.json
logs/chat_logs.json
```

這些檔案是「線上資料」，更新前要特別注意，不要直接覆蓋掉正式資料。

## 新增指定網站

到後台：

```text
知識管理 -> 網站索引管理 -> 新增網站索引
```

新增後，再到 Dashboard 按：

```text
立即建立索引
```

如果直接編輯檔案，主要是改：

```text
data/urls.json
```

建議放主要入口頁，例如：

```text
https://www.reliable.com.tw/
https://www.reliable.com.tw/category/pr/
https://www.reliable.com.tw/array-networks/
https://www.reliable.com.tw/category/kb/
```

系統會從這些入口嘗試抓取可索引內容。

## 新增 KB 文件

到後台：

```text
知識管理 -> 知識庫文件管理 -> 新增 / 上傳 KB
```

目前建議使用：

- TXT
- PDF
- DOCX

不建議使用 PPTX，因為投影片轉文字容易出現亂碼或段落錯亂。

## LOGS 使用方式

LOGS 可以查看每一筆客服對話，包含：

- 時間
- 平台：LINE / WEB
- 問題
- 回覆
- 回答來源
- 延遲
- IP
- 商機意圖
- 品質標記

常用操作：

- `點擊查看`：展開完整對話詳情。
- `轉 FAQ`：將常見問題一鍵加入 FAQ。
- `良好 / 待修 / 錯誤`：標記回答品質。
- `待追蹤 / 已處理`：管理商機或人工接手狀態。
- `排除 IP`：排除內部測試紀錄，例如公司 WiFi 或手機 5G。

多個 IP 可以用逗號或空白分隔：

```text
211.20.45.252, 147.92.149.170
```

## 帳號權限

目前後台有兩種角色：

- `管理者`：可查看與編輯，可新增帳號、調整權限、管理 FAQ / KB / 網站索引。
- `唯讀`：只能查看，不能新增、編輯、刪除或匯入資料。

系統會避免以下狀況：

- 把最後一位管理者改成唯讀。
- 刪除最後一位管理者。
- 所有帳號都變成唯讀而無法管理。

## GitHub 建議用法

目前 GitHub 主要用來同步 Mac 與 VPS 程式碼。後續可以再加強：

- README：本文件，用來交接與維護。
- Issue：記錄待辦與功能需求。
- Release：標記穩定版本，例如 `v1.0`。
- GitHub Actions：自動檢查 Python 語法，未來也可做自動部署。

## 常見問題

### git pull 時遇到資料檔衝突

通常是 VPS 上的資料檔有變動，例如 FAQ 被後台更新過。先備份線上資料，再處理 pull。

建議先備份：

```bash
cp data/faq.json data/faq.backup.json
```

再視情況處理 Git 衝突。

### LINE 或 WEB 回答來源不準

優先檢查：

1. FAQ 是否有錯誤資料。
2. KB 文件內容是否正確。
3. `data/urls.json` 是否放了正確網站入口。
4. Dashboard 是否已按「立即建立索引」。
5. LOGS 的來源欄位顯示命中哪一種資料。

### 圖片辨識沒有結果

可能原因：

- 圖中文字太小或太模糊。
- 本機 OCR 沒有裝完整。
- Vision API 尚未設定。

VPS 可安裝：

```bash
sudo apt install tesseract-ocr tesseract-ocr-chi-tra tesseract-ocr-eng
```

## 維護提醒

- 程式碼可以放 GitHub。
- `.env` 不要放 GitHub。
- 後台帳號資料不要放 GitHub。
- 線上 LOG 與使用者資料要注意備份與隱私。
- 修改後台功能時，記得同步更新 `data/admin_changelog.json`。

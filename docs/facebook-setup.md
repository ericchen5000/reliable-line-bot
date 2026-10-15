# Facebook Messenger 設定與更新

本版支援粉專文字問答、既有知識庫、多輪對話、商機分類與 FB LOGS。
圖片與其他附件會提示使用文字；按鈕 postback、人工接手切換、人工回覆後暫停 AI 尚未實作。
若粉專有人工作業，先以測試帳號驗證並協調回覆方式，避免同時回答。

## VPS 設定

保持 ngrok 的既有回呼網址，路徑為 `/webhook`。程式須監聽 ngrok 轉送的 8000 埠。
參考 `facebook.env.example` 將設定加入 VPS 專案 `.env`，不要把真正的權杖提交到 GitHub 或貼進聊天。

- FB_PAGE_ID：定承資訊粉專 ID。
- FB_PAGE_ACCESS_TOKEN：此應用程式為該粉專產生的存取權杖。
- FB_APP_SECRET：Meta「應用程式設定／基本資料」中的應用程式密鑰。
- FB_VERIFY_TOKEN：自行設定的驗證字串，須與 Meta Webhooks 欄位完全一致。
- FB_GRAPH_VERSION：Meta 後台顯示仍受支援的 API 版本，格式 `v數字.數字`。
- FB_AUTO_REPLY：先 false；準備好測試時改 true 並重啟。

設定由既有 config.py 的 load_dotenv 載入。若改成系統服務，確認工作目錄和環境設定正確。

## 每次更新

1. 本機測試通過，檢查差異後提交並推送 GitHub。原有尚未完成的頁面推薦修改保留在本機，不包含在此次 FB 發布。
2. VPS 另開 SSH 視窗，進入 `~/line-bot`，先 `git status -sb` 確認有無本機修改。
3. 備份 `.env`、`data/`、`knowledge/`、`logs/` 到專案外安全位置。
4. 沒有衝突時執行 `git pull --ff-only`；若失敗先處理原因，不使用強制覆蓋。
5. 在原客服視窗 Ctrl+C 停止，於專案目錄、既有 venv 中啟動：

   `uvicorn app:app --host 0.0.0.0 --port 8000`

6. 保持客服與 ngrok 視窗運作。Meta 回呼網址與驗證權杖儲存驗證應成功。
7. 由具應用程式測試資格的帳號私訊粉專，確認一次回覆、正確來源及 FB LOGS；再測 LINE 與 WEB。
8. 正式公開使用仍需完成 Meta 後台要求的檢閱與發佈；開發模式測試成功不代表所有客人可用。

## 訊息與錯誤處理

已驗證的事件先存入 `logs/facebook_queue.sqlite3` 再回覆 Meta，背景逐筆處理。資料庫含私人對話，已加入 Git 忽略清單。
重複 mid 不重送，忽略 echo、讀取及投遞事件；只接受設定粉專的事件。
佇列超過 23 小時的事件停止發送，避免逾越一般回覆時間視窗。

發送失敗標記 failed；連線結果不確定標記 uncertain；程序在發送途中中斷可能保留 processing。
這些狀態不會自動重送，以免重複打擾使用者。需檢查終端錯誤及粉專實際對話再決定如何處理。
若發送成功但 LOGS 寫入失敗，終端會提示，佇列保留 sent，避免再次發送。

暫停 AI：設 FB_AUTO_REPLY=false 並重啟。停用期間事件會略過，不會在下次啟用時補發。
本版沒有針對個別對話的人工接手開關。

初次部署建議單一 uvicorn worker，與目前啟動方式一致。原有 JSON LOGS 仍有多程序同時寫入限制。

# LawExplore 技術參考

分工和交付先看[團隊手冊](TEAM.md)。這一頁用來查 CSV 怎麼填、程式怎麼接，以及有哪些指令可用。

## 先分清楚兩種檔案

`data/processed/official/corpus.jsonl` 是網站搜尋的資料。一行是一條法條或一點契約規範，包含全文、官方來源和文件 ID。網站直接讀這份檔案，由 `python manage.py build` 重建。

`data/annotations/A.csv` 到 `E.csv` 是工作表，放原文核對、詞組、口語對照、搜尋題和相關性標註。用 `doc_id` 找回引用的原文，用 `corpus_id` 確認一起使用的是同一版資料。修改 CSV 的標註或狀態後，網站的原文和搜尋排序不會跟著更新。若要接入口語對照，由 C 在搜尋模組實作。

## CSV 怎麼填

用 CSV UTF-8 存檔。保留下面 12 欄與原順序，ID 欄在 Excel 設為文字。每筆 `id` 加上自己的角色前綴，例如 `B_P_01`。可以直接複製 A.csv 的格式。

```csv
kind,id,corpus_id,doc_id,query_id,text,target,label,evidence,source_url,author,status
```

| kind | 要填的內容 | label 怎麼選 |
|---|---|---|
| `audit` | `doc_id`、完整原文放 `text`、來源放 `source_url`，查核日期和方法放 `evidence` | `snapshot_only` 是快照資料，`text_matches_web` 是已核對網頁文字 |
| `phrase` | `doc_id`、原文可逐字找到的詞組放 `text`，判斷理由放 `evidence` | `valid` 可用、`incomplete` 不完整、`generic` 太通用、`uncertain` 不確定 |
| `mapping` | `doc_id`、口語放 `text`、原文法律詞放 `target`，適用情境放 `evidence` | `synonym` 同義、`near_synonym` 近義、`contextual` 情境相關 |
| `query` | 問題放 `text`，本列 `id` 就是問題 ID，`doc_id` 可留空 | `development` 開發、`demo` 展示、`user_study` 使用者研究 |
| `qrel` | `query_id` 填問題 ID，`doc_id` 填對應文件，`evidence` 寫判分理由 | `2` 直接相關、`1` 背景、`0` 不相關 |

`status` 可填 `draft`、`needs_review`、`approved` 或 `disputed`。各自確認自己的列再改為 `approved`，先確認題目再確認該題的相關性列。正式評估與口語對照採用已確認的資料。`python manage.py check` 會核對格式、引用與原文，相關性和適用情境由負責人判斷。

## 後端怎麼接

| 路徑 | 要傳什麼 | 會拿到什麼 |
|---|---|---|
| GET `/health`、`/meta`、`/team` | 無 | 狀態、版本或角色資料 |
| GET `/search` | `query`、`corpus_id`，可選 `top_k`、`domain` | `results` 搜尋結果和 `suggestions` 推薦 |
| GET `/suggest` | `query`、`corpus_id` | 推薦詞、理由和來源文件 ID |
| GET `/phrases/{term}` | 詞組放在路徑，另傳 `corpus_id` | 總次數、命中文本數、位置、上下文和共現詞組 |
| GET `/documents/{id}` | 文件 ID 放在路徑，另傳 `corpus_id` | 原文和官方來源 |

`query` 和 `term` 長度是 1～200 字。`top_k` 預設 5，範圍是 1～20。輸入不合法回 400，找不到指定語料或文件回 404，搜尋無命中回 200 和空結果。錯誤訊息在 `error.message`。

- **B** 參照 `reference.py` 的 `lookup(phrase)`。輸出 `frequency` 總次數、`df` 命中文本數，以及 `documents` 內每份文件的 `doc_id`、`tf` 和 `positions`。位置從 0 開始，用 Unicode code point 計算，`end` 指命中後的第一個位置。可重疊，單次命中不能跨文件。前端用 `Array.from` 轉換字元位置。
- **C** 維持 `search(query, top_k, domain)`，交回按排名排好的 `doc_id` 與 `score`。現有 BM25 用單字元和雙字元組合，`k1=1.5`、`b=0.75`，同分以文件 ID 排序。推薦包含 `phrase`、`reason` 和 `source_doc_ids`。
- **D** 的共現分數是「兩詞都出現的文件數 ÷ 至少出現其中一詞的文件數」。目前 `related_terms` 已有詞組、分數和 `cooccurrence_df`，要讓前端查看共現證據時，再約定共同文件 ID 與上下文的格式。
- **A** 從 API 拿排名、全文和上下文。共用服務在 `src/services.py` 組裝這些模組，B、C 或 D 改回傳格式前先和 A 對一下。

## 怎麼做評估

E 的 `evaluate(runs, qrels)` 需要兩份資料。`runs` 是「問題 ID → 依名次排列的文件 ID」，`qrels` 是「問題 ID → 文件 ID 與相關性分數」。排名裡的文件 ID 不能重複，每題至少有一筆相關性大於 0。用同一批問題、語料和標註比較版本。

- `MRR@10` 看前 10 名的第一筆相關文本排多前面。
- `Recall@5` 看前 5 名找回多少已標相關的文本。
- `nDCG@10` 同時考慮前 10 名的順序和 0～2 的相關程度。

目前的評估程式把缺少排名的題目計為 0，未標文件視為 0。報告時記下這項限制、使用的語料版本、方法和參數。目前的 25 題供開發及演練。正式評估先確認原始資料欄位與 ID，另存自己使用的語料與結果。預定的外部資料來源是 [LawFactsQA-TW](https://github.com/NCHU-NLP-Lab/LawFactsQA-TW)，目前尚未匯入。

研究用的 A/B 介面仍待實作，`POST /events` 預設關閉。E 設計任務與事件，A 串接。事件必填 `event`、`session_id`、`task_id`、`variant`、`corpus_id`、`index_id`，姓名和查詢全文不放入事件。啟用後寫到 `results/local/events.jsonl`。

## 常用指令

| 指令 | 用途 |
|---|---|
| `python -X utf8 manage.py example B` | 看角色的輸出範例，替換最後的代號 |
| `python manage.py check` | 檢查語料和 CSV |
| `python manage.py build` | 用附帶的來源離線重建語料 |
| `python manage.py export` | 將詞頻、詞組位置和 A 的範例排名輸出到 `results/local/`。每次執行前先另存要保留的輸出 |
| `python -m unittest discover -s tests -v` | 跑程式與本機 API 測試 |
| `python manage.py package` | 更新分享用 ZIP |

找不到 Python 可試 `py -3 run.py --open`，埠號被占用可跑 `python run.py --port 8766 --open`。改 Python 後重啟服務，改前端後重新整理瀏覽器。

## 語料來源和更新

目前 467 筆，包括 434 條法條和 33 項住宅租賃契約規範。法條分布是租賃 67、勞動 98、消費 77、個資 65、交通 127。租賃法條是民法租賃整節及《租賃住宅市場發展及管理條例》第 1～16 條。法規 XML 快照於 2026-11-14 臺灣時間擷取。 [全國法規資料庫開放資料](https://data.gov.tw/dataset/18289)

契約規範使用內政部 114 年 4 月 18 日公告版，擷取 PDF 第 1～7 頁正文並整理排版空白。來源、版本及檔案雜湊記在 `data/seed/source_manifest.json`。 [開放資料集](https://data.gov.tw/dataset/178758) · [公告全文](https://www.ey.gov.tw/File/43BC094940995CFC?A=C)

平常直接用附帶的來源檔重建。要更新完整法規快照時，用 `python manage.py download --output data/raw/official/new.xml` 先保存新檔。若要重新擷取法規子集，`build --extract-full` 會從 `data/raw/official/laws.xml` 與同名 manifest，依 `config/scope.json` 挑出條文。更換語料前要同步檢查版本和標註引用。

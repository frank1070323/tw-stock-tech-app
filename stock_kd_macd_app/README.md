# 台股技術分析 App

這是一個用 Flask 製作的台股單股分析工具，現在已經整理成可以本機執行，也可以部署到雲端主機。

目前功能包含：

- KD / MACD
- 均線 5 / 10 / 20 / 60 / 120
- 成交量 VMA5 / VMA20
- 成本價分析
- 市場熱度 / 新聞情緒
- 技術圖

## 本機執行

```powershell
pip install -r requirements.txt
python app.py
```

預設網址：

```text
http://127.0.0.1:5050
```

## API

```text
GET /api/analyze?symbol=6442
GET /api/chart?symbol=6442
```

## 雲端部署

專案已補好這些部署檔案：

- [render.yaml](./render.yaml)
- [Procfile](./Procfile)
- [.python-version](./.python-version)

### Render

官方文件：

- <https://render.com/docs/deploy-flask>
- <https://render.com/docs/web-services>
- <https://render.com/docs/free>

建立方式：

1. 把專案放到 GitHub
2. 登入 Render
3. 建立 `Web Service`
4. Build Command：`pip install -r requirements.txt`
5. Start Command：`gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120`

### Railway

如果之後想改用 Railway，現在也可以直接沿用 [Procfile](./Procfile)。

## 測試

```powershell
python -m unittest discover -s tests -v
```

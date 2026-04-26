from flask import Flask, Response, jsonify, render_template, request

from .analysis import StockAnalyzer
from .data_source import OfficialStockDataSource, StockDataError
from .enrichment import StockEnrichmentService


def create_app(test_config=None):
    app = Flask(__name__, template_folder="../templates", static_folder="../static")
    app.config.from_mapping(JSON_AS_ASCII=False)

    if test_config:
        app.config.update(test_config)

    if "ANALYZER" not in app.config:
        data_source = OfficialStockDataSource()
        analyzer = StockAnalyzer(
            data_source,
            StockEnrichmentService(data_source, network_enabled=not app.config.get("TESTING", False)),
        )
        app.config["ANALYZER"] = analyzer

    @app.get("/")
    def index():
        return render_template("index.html")

    @app.get("/api/analyze")
    def analyze():
        symbol = (request.args.get("symbol") or "").strip()
        if not symbol:
            return jsonify({"error": "請輸入股票代號或公司名稱。"}), 400

        target_price = _parse_optional_float(request.args.get("target_price"))
        stop_price = _parse_optional_float(request.args.get("stop_price"))

        try:
            result = app.config["ANALYZER"].analyze(symbol, target_price=target_price, stop_price=stop_price)
        except StockDataError as exc:
            return jsonify({"error": str(exc)}), 400
        except Exception:
            return jsonify({"error": "分析服務暫時失敗，請稍後再試。"}), 502

        return jsonify(result)

    @app.get("/api/chart")
    def chart():
        symbol = (request.args.get("symbol") or "").strip()
        if not symbol:
            return Response("請輸入股票代號或公司名稱。", status=400, content_type="text/plain; charset=utf-8")

        try:
            image_bytes = app.config["ANALYZER"].render_chart(symbol)
        except StockDataError as exc:
            return Response(str(exc), status=400, content_type="text/plain; charset=utf-8")
        except Exception:
            return Response("圖表產生失敗，請稍後再試。", status=502, content_type="text/plain; charset=utf-8")

        return Response(image_bytes, mimetype="image/png")

    return app


def _parse_optional_float(raw_value):
    if raw_value in {None, ""}:
        return None
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return None

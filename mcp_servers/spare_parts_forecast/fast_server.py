"""FastMCP based server for spare parts forecasting.

Run (package mode):
    python -m mcp_servers.spare_parts_forecast.fast_server
"""
from __future__ import annotations

import contextlib
import logging
from typing import Any

from fastmcp import FastMCP

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

app = FastMCP(name="spare-parts-forecast-fast", version="1.0.0")
with contextlib.suppress(Exception):  # pragma: no cover
    app.description = "Spare parts demand forecasting tools (FastMCP)"  # type: ignore[attr-defined]

def create_fast_server() -> FastMCP:
    """Factory returning FastMCP app (for embedding)."""
    return app

__all__ = [
    "algorithm_categories",
    "algorithms",
    "arima_forecast",
    "bp_forecast",
    "create_fast_server",
    "croston_forecast",
    "ema_forecast",
    "forest_forecast",
    "ping",
    "sma_forecast",
    "xgb_forecast",
]

# Try import algorithms
try:
    from .forecasting import (
        arimaforecast_try,
        croston_forecast_try,
        ema_forecast_try,
        forest_try,
        get_available_algorithms,
        list_algorithms,
        sma_forecast_try,
        xgboost_forecast,
        zero_and_bp_predict,
    )
except Exception:  # pragma: no cover
    logger.exception("Failed to import forecasting algorithms")
    arimaforecast_try = croston_forecast_try = ema_forecast_try = forest_try = None  # type: ignore
    sma_forecast_try = xgboost_forecast = zero_and_bp_predict = None  # type: ignore

    def list_algorithms() -> list[str]:  # type: ignore
        return []

    def get_available_algorithms() -> dict[str, list[str]]:  # type: ignore
        return {}


@app.tool()
def ping() -> str:
    """连接测试"""
    return "pong"


@app.tool()
def algorithms() -> list[str]:
    """列出所有算法名称"""
    return list_algorithms()


@app.tool()
def algorithm_categories() -> dict[str, list[str]]:
    """按类别列出可用算法"""
    return get_available_algorithms()


@app.tool()
def sma_forecast(n: int = 4) -> Any:
    """SMA 简单移动平均预测"""
    if sma_forecast_try is None:
        return {"error": "SMA unavailable"}
    return sma_forecast_try(n)


@app.tool()
def ema_forecast(n: int = 4) -> Any:
    """EMA 指数平滑预测"""
    if ema_forecast_try is None:
        return {"error": "EMA unavailable"}
    return ema_forecast_try(n)


@app.tool()
def croston_forecast(n: int = 4) -> Any:
    """Croston 间歇需求预测"""
    if croston_forecast_try is None:
        return {"error": "Croston unavailable"}
    return croston_forecast_try(n)


@app.tool()
def arima_forecast(n: int = 4) -> Any:
    """ARIMA 预测"""
    if arimaforecast_try is None:
        return {"error": "ARIMA unavailable"}
    return arimaforecast_try(n)


@app.tool()
def forest_forecast(n: int = 4) -> Any:
    """随机森林预测"""
    if forest_try is None:
        return {"error": "Forest unavailable"}
    return forest_try(n)


@app.tool()
def xgb_forecast(column_index: int = 16) -> Any:
    """XGBoost 预测"""
    if xgboost_forecast is None:
        return {"error": "XGBoost unavailable"}
    return xgboost_forecast(column_index=column_index)


@app.tool()
def bp_forecast(column_index: int = 16) -> Any:
    """BP 神经网络预测 (需要 TensorFlow)"""
    if zero_and_bp_predict is None:
        return {"error": "BP unavailable"}
    try:
        return zero_and_bp_predict(column_index)
    except Exception as e:  # pragma: no cover
        return {"error": str(e)}


if __name__ == "__main__":  # pragma: no cover
    # FastMCP 提供 uvicorn/stdio 等多种运行方式；默认使用 stdio
    app.run()

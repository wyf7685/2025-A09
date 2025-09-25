"""FastMCP based server for spare parts forecasting.

Run (package mode):
    python -m mcp_servers.spare_parts_forecast.fast_server
"""

from __future__ import annotations

import logging
from typing import Any

from mcp.server import FastMCP

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

instructions = """\
此服务器提供多种备件需求预测算法:

可用算法分类和功能:
- 统计类: SMA(简单移动平均), EMA(指数平滑), Croston(间歇需求), ARIMA
- 机器学习: 随机森林, XGBoost
- 深度学习: BP神经网络

主要工具:
- algorithms: 列出所有可用算法
- algorithm_categories: 按类别显示算法列表
- sma_forecast: 简单移动平均预测
- ema_forecast: 指数平滑预测
- croston_forecast: 间歇需求预测
- arima_forecast: ARIMA预测
- forest_forecast: 随机森林预测
- xgb_forecast: XGBoost预测
- bp_forecast: BP神经网络预测

对于大多数算法,可通过参数n指定预测步数。机器学习算法可通过column_index指定预测列。
"""

app = FastMCP(
    name="spare-parts-forecast-fast",
    instructions=instructions,
)


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
    "sma_forecast",
    "xgb_forecast",
]

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
    app.run("sse")

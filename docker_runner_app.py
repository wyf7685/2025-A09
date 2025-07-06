# ruff: noqa

import base64
import io
from typing import Any, Literal

import pandas as pd
import uvicorn
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.executor import ExecuteResult, execute_code as execute_code_in_docker

app = FastAPI(
    title="代码执行调试接口",
    description="用于测试在Docker环境中执行数据分析代码",
    version="0.1.0",
)

# 添加CORS中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


async def process_uploaded_csv(file: UploadFile) -> pd.DataFrame:
    """处理上传的CSV文件"""
    if not file.filename or not file.filename.endswith(".csv"):
        raise HTTPException(status_code=400, detail="只接受CSV文件")

    try:
        # 读取上传的文件内容
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
        return df
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"CSV文件解析错误: {str(e)}")


class TableResult(BaseModel):
    """表格数据结果"""

    type: Literal["table"] = Field(default="table", description="数据类型")
    data: dict[str, Any] = Field(description="表格数据，包含columns、index和data")


class ArrayResult(BaseModel):
    """数组数据结果"""

    type: Literal["array"] = Field(default="array", description="数据类型")
    data: list[Any] = Field(description="数组数据")


class OtherResult(BaseModel):
    """其他类型结果"""

    type: Literal["other"] = Field(default="other", description="数据类型")
    data: str = Field(description="字符串形式的数据")


class Figure(BaseModel):
    """图表数据"""

    type: str = Field(default="image/png", description="图片类型")
    data: str = Field(description="Base64编码的图片数据")


class ExecutionResponse(BaseModel):
    """代码执行结果响应"""

    success: bool = Field(description="是否执行成功")
    output: str = Field(default="", description="标准输出内容")
    error: str = Field(default="", description="错误信息")
    result: TableResult | ArrayResult | OtherResult | None = Field(default=None, description="执行结果")
    figure: Figure | None = Field(default=None, description="生成的图表")


def process_result(execution_result: ExecuteResult) -> ExecutionResponse:
    """处理执行结果，使用Pydantic模型规范化输出"""
    processed_result = {
        "success": execution_result["success"],
        "output": execution_result["output"],
        "error": execution_result["error"],
        "result": None,
        "figure": None,
    }

    # 处理结果数据
    result = execution_result["result"]
    if result is not None:
        if isinstance(result, pd.Series):
            result = result.to_frame()
        if isinstance(result, pd.DataFrame):
            processed_result["result"] = TableResult(data=result.to_dict(orient="split"))
        elif hasattr(result, "__array__"):  # numpy数组
            processed_result["result"] = ArrayResult(data=result.tolist())
        else:
            processed_result["result"] = OtherResult(data=str(result))

    # 处理图表
    if execution_result["figure"] is not None:
        image_base64 = base64.b64encode(execution_result["figure"]).decode()
        processed_result["figure"] = Figure(data=image_base64)

    return ExecutionResponse(**processed_result)


@app.post("/execute", response_model=ExecutionResponse)
async def execute_code(
    code: str = Form(),
    data_file: UploadFile = File(),
) -> ExecutionResponse:
    """
    执行Python数据分析代码

    参数:
    - code: Python代码字符串
    - data_file: CSV格式的数据文件

    返回:
    - ExecutionResponse: 包含执行结果的响应对象
    """
    try:
        df = await process_uploaded_csv(data_file)
        execution_result = execute_code_in_docker(code, df)
        return process_result(execution_result)

    except Exception as e:
        return ExecutionResponse(
            success=False,
            error=f"服务器错误: {str(e)}",
            output="",
        )


def main():
    """启动调试服务器"""
    uvicorn.run(app, host="0.0.0.0", port=8000)


if __name__ == "__main__":
    main()

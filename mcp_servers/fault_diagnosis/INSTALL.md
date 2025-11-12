# 机器故障诊断 MCP - 安装和使用指南

## 📦 安装步骤

### 1. 激活项目虚拟环境并安装

```bash
# 进入项目根目录
cd e:\服务外包\2025-A09

# 激活虚拟环境
.\.venv\Scripts\activate

# 进入MCP目录
cd mcp_servers\fault_diagnosis

# 安装MCP服务器
pip install -e .
```

### 2. 测试工具功能

```bash
# 在 mcp_servers/fault_diagnosis 目录下
python test_tools.py
```

### 3. 启动MCP服务器 ✅

**推荐方式: 使用启动脚本（最简单）**
```bash
# 在项目根目录，激活虚拟环境后
cd e:\服务外包\2025-A09
.\.venv\Scripts\activate
python .\mcp_servers\fault_diagnosis\run_server.py sse --port 8001
```

启动成功后会看到：
```
🚀 启动故障诊断MCP服务器...
   服务器名称: fault-diagnosis
   可用工具: fault_vs_normal, health_score, fault_rules, fault_patterns

正在启动...
INFO:     Started server process [xxxxx]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8001
```

**其他启动方式**
```bash
# stdio 模式
python .\mcp_servers\fault_diagnosis\run_server.py stdio

# 或直接运行模块
python -m mcp_servers.fault_diagnosis.app sse --port 8001
```

## 🔧 配置到项目

### 在 `data/mcp_servers.json` 中添加：

```json
{
  "你的UUID": {
    "id": "你的UUID",
    "connection": {
      "transport": "sse",
      "url": "http://127.0.0.1:8001/sse",
      "timeout": 30.0,
      "sse_read_timeout": 300.0
    },
    "name": "机器故障诊断",
    "description": "提供故障特征分析、健康度评分、规则挖掘、模式聚类等工具"
  }
}
```

### 或使用前端界面添加：

1. 访问项目前端
2. 进入 MCP 管理页面
3. 添加新的 MCP 连接：
   - **名称**: 机器故障诊断
   - **传输方式**: SSE
   - **URL**: `http://127.0.0.1:8001/sse`
   - **描述**: 提供故障诊断工具

## 🎯 使用示例

### 在Agent对话中使用：

```
用户: "分析这台机器的故障情况"

Agent会自动：
1. 调用 fault_vs_normal 识别故障特征
2. 调用 fault_patterns 分类故障类型  
3. 调用 fault_rules 提取诊断规则
4. 调用 health_score 评估当前健康状况
5. 综合生成诊断报告
```

### 4个工具说明：

| 工具 | 命令 | 用途 |
|-----|------|------|
| fault_vs_normal | 故障对比分析 | 识别哪些特征与故障相关 |
| health_score | 健康度评分 | 评估设备当前健康状况 |
| fault_rules | 规则挖掘 | 提取故障判断规则 |
| fault_patterns | 模式聚类 | 识别不同故障类型 |

## 🧪 测试数据

项目中的 `local/data.csv` 是机器故障数据集，包含：
- 10个特征列（footfall, tempMode, AQ, USS, CS, VOC, RP, IP, Temperature）
- 1个标签列（fail: 0=正常, 1=故障）
- 944条记录，故障率约41.6%

非常适合演示MCP的故障诊断功能！

## 🐛 故障排查

### 问题1: 找不到数据源

确保数据文件在以下位置之一：
- `data/datasources/{source_id}.csv`
- `uploads/{source_id}.csv`
- `external/{source_id}.csv`

### 问题2: MCP服务器无法启动

**检查端口是否被占用：**
```bash
netstat -ano | findstr :8001
```

**更换端口：**
```bash
python .\mcp_servers\fault_diagnosis\run_server.py sse --port 8002
```

**检查是否在正确的虚拟环境：**
```bash
# 应该显示项目的 .venv 路径
python -c "import sys; print(sys.prefix)"
```

### 问题3: Agent无法调用MCP工具

1. 确认MCP服务器正在运行
2. 检查会话是否已连接MCP
3. 查看MCP连接状态

## 📝 演示脚本

```
用户问题: "这台机器现在的状态如何？会不会故障？"

预期Agent流程:
1. [内置] inspect_dataframe - 查看数据结构
2. [MCP] fault_vs_normal - 识别VOC、AQ、footfall是关键特征
3. [MCP] fault_patterns - 发现3种故障模式
4. [MCP] health_score - 当前健康度71.7分（中等风险）
5. [MCP] fault_rules - 提取判断规则
6. Agent综合输出诊断报告

完美展示MCP与内置工具的协同！
```

## 📚 更多信息

详见 [README.md](README.md)

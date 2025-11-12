#!/usr/bin/env python3
"""
故障诊断MCP服务器启动脚本

提供简单的命令行接口来启动MCP服务器。
"""
# ruff: noqa T201
import sys
import os
from pathlib import Path
import logging

# 配置详细日志
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加项目根目录到Python路径，以便能够导入app模块
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

logger.debug(f"当前工作目录: {os.getcwd()}")
logger.debug(f"Python路径: {sys.path}")

def main():
    """主函数，启动MCP服务器"""
    logger.info("🚀 启动故障诊断MCP服务器...")
    
    try:
        # 导入app对象和必要的依赖
        logger.debug("导入app对象...")
        from mcp_servers.fault_diagnosis.app.__main__ import app
        import anyio
        
        # 检查命令行参数
        args = sys.argv[1:]
        logger.debug(f"命令行参数: {args}")
        
        # 确保我们使用SSE模式启动
        if 'sse' in args:
            logger.info("以SSE模式启动服务器...")
            # 直接调用run_sse_async方法
            anyio.run(app.run_sse_async)
        else:
            logger.info("使用默认模式启动服务器...")
            # 回退到app.run()
            app.run()
            
    except ImportError as e:
        logger.error(f"导入模块失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
    except Exception as e:
        logger.error(f"服务器启动失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    logger.info("启动脚本被直接执行")
    main()
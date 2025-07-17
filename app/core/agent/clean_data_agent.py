"""
基于LangChain和LangGraph的智能数据清洗Agent
支持用户自定义清洗要求，LLM猜测数据源字段名并保存
"""

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, TypedDict

import pandas as pd
from langchain.prompts import PromptTemplate
from langchain_core.language_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.runnables import RunnableLambda, ensure_config
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, StateGraph
from pydantic import BaseModel, Field

from app.core.chain.llm import LLM, get_chat_model, get_llm
from app.log import logger


class CleaningState(TypedDict):
    """数据清洗状态"""
    file_path: str
    df_data: Optional[Dict[str, Any]]  # 存储DataFrame的序列化数据而不是DataFrame本身
    user_requirements: Optional[str]
    quality_issues: List[Dict[str, Any]]
    field_mappings: Dict[str, str]
    cleaning_suggestions: List[Dict[str, Any]]
    cleaned_df_data: Optional[Dict[str, Any]]  # 存储清洗后DataFrame的序列化数据
    cleaning_summary: str
    error_message: Optional[str]


class FieldMapping(BaseModel):
    """字段映射模型"""
    original_name: str = Field(description="原始字段名")
    suggested_name: str = Field(description="建议的标准字段名")
    confidence: float = Field(description="置信度", ge=0.0, le=1.0)
    field_type: str = Field(description="字段类型")
    description: str = Field(description="字段描述")


class CleaningSuggestion(BaseModel):
    """清洗建议模型"""
    column: str = Field(description="列名")
    issue_type: str = Field(description="问题类型")
    description: str = Field(description="问题描述")
    suggested_action: str = Field(description="建议的清洗动作")
    priority: str = Field(description="优先级: high/medium/low")
    parameters: Dict[str, Any] = Field(default_factory=dict, description="清洗参数")


class DataQualityReport(BaseModel):
    """数据质量报告模型"""
    overall_score: float = Field(description="总体质量分数", ge=0.0, le=100.0)
    total_rows: int = Field(description="总行数")
    total_columns: int = Field(description="总列数")
    missing_values_count: int = Field(description="缺失值总数")
    duplicate_rows_count: int = Field(description="重复行数")
    issues: List[Dict[str, Any]] = Field(description="质量问题列表")
    recommendations: List[str] = Field(description="建议列表")


class SmartCleanDataAgent:
    """基于LangChain和LangGraph的智能数据清洗Agent"""

    def __init__(self, model_name: Optional[str] = None):
        self.llm = get_llm()
        self.chat_model = get_chat_model(model_name)
        self.graph = self._create_graph()
        self.config = ensure_config({"configurable": {"thread_id": "clean_data_agent"}})
        
        # 常见的数据类型模式
        self.patterns = {
            "email": re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"),
            "phone": re.compile(r"^[\+]?[1-9]?\d{1,14}$"),
            "date": re.compile(r"^\d{4}-\d{2}-\d{2}$"),
            "time": re.compile(r"^\d{2}:\d{2}:\d{2}$"),
            "url": re.compile(r"^https?://[^\s/$.?#].[^\s]*$"),
            "numeric": re.compile(r"^-?\d+\.?\d*$"),
        }

    def _create_graph(self) -> Any:
        """创建数据清洗工作流图"""
        graph = StateGraph(CleaningState)
        
        # 添加节点
        graph.add_node("load_data", self._load_data)
        graph.add_node("analyze_quality", self._analyze_quality)
        graph.add_node("guess_field_names", self._guess_field_names)
        graph.add_node("generate_suggestions", self._generate_suggestions)
        graph.add_node("apply_cleaning", self._apply_cleaning)
        graph.add_node("generate_summary", self._generate_summary)
        
        # 设置起始节点
        graph.set_entry_point("load_data")
        
        # 添加边
        graph.add_edge("load_data", "analyze_quality")
        graph.add_edge("analyze_quality", "guess_field_names")
        graph.add_edge("guess_field_names", "generate_suggestions")
        graph.add_edge("generate_suggestions", "apply_cleaning")
        graph.add_edge("apply_cleaning", "generate_summary")
        graph.add_edge("generate_summary", END)
        
        return graph.compile(checkpointer=InMemorySaver())

    def _load_data(self, state: CleaningState) -> CleaningState:
        """加载数据文件"""
        try:
            file_path = Path(state["file_path"])
            logger.info(f"加载数据文件: {file_path}")
            
            if not file_path.exists():
                raise FileNotFoundError(f"文件不存在: {file_path}")
            
            # 根据文件扩展名读取数据
            if file_path.suffix.lower() == '.csv':
                df = pd.read_csv(file_path)
            elif file_path.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(file_path)
            else:
                raise ValueError(f"不支持的文件格式: {file_path.suffix}")
            
            if df.empty:
                raise ValueError("数据文件为空")
            
            state["df_data"] = df.to_dict() # 序列化DataFrame
            logger.info(f"成功加载数据: {len(df)} 行, {len(df.columns)} 列")
            return state
            
        except Exception as e:
            logger.error(f"加载数据失败: {e}")
            state["error_message"] = str(e)
            return state

    def _analyze_quality(self, state: CleaningState) -> CleaningState:
        """分析数据质量"""
        try:
            df_data = state["df_data"]
            if df_data is None:
                raise ValueError("数据未加载")
            
            df = pd.DataFrame(df_data) # 反序列化DataFrame
            
            logger.info("开始分析数据质量")
            
            # 基本统计信息
            total_rows = len(df)
            total_columns = len(df.columns)
            missing_values_count = int(df.isna().sum().sum())
            duplicate_rows_count = int(df.duplicated().sum())
            
            # 分析各种质量问题
            issues = []
            
            # 1. 检查列名问题
            column_issues = self._check_column_names(df)
            issues.extend(column_issues)
            
            # 2. 检查缺失值
            missing_issues = self._check_missing_values(df)
            issues.extend(missing_issues)
            
            # 3. 检查重复行
            if duplicate_rows_count > 0:
                issues.append({
                    "type": "duplicate_rows",
                    "severity": "medium",
                    "description": f"发现 {duplicate_rows_count} 行重复数据",
                    "count": duplicate_rows_count
                })
            
            # 4. 检查数据类型
            type_issues = self._check_data_types(df)
            issues.extend(type_issues)
            
            # 5. 检查异常值
            outlier_issues = self._check_outliers(df)
            issues.extend(outlier_issues)
            
            # 计算质量分数
            quality_score = self._calculate_quality_score(issues, total_rows, total_columns)
            
            state["quality_issues"] = issues
            logger.info(f"数据质量分析完成，质量分数: {quality_score:.2f}")
            return state
            
        except Exception as e:
            logger.error(f"数据质量分析失败: {e}")
            state["error_message"] = str(e)
            return state

    def _guess_field_names(self, state: CleaningState) -> CleaningState:
        """使用LLM猜测数据源字段名"""
        try:
            df_data = state["df_data"]
            if df_data is None:
                raise ValueError("数据未加载")
            
            df = pd.DataFrame(df_data) # 反序列化DataFrame
            
            logger.info("开始猜测字段名")
            
            # 准备数据样本和列信息
            sample_data = df.head(5).to_dict('records')
            columns_info = []
            
            for col in df.columns:
                col_info = {
                    "original_name": col,
                    "dtype": str(df[col].dtype),
                    "null_count": int(df[col].isnull().sum()),
                    "unique_count": int(df[col].nunique()),
                    "sample_values": df[col].dropna().head(3).tolist()
                }
                columns_info.append(col_info)
            
            # 构建提示词
            prompt = self._create_field_mapping_prompt(columns_info, sample_data, state.get("user_requirements"))
            
            # 调用LLM
            messages = [
                SystemMessage(content="你是一位专业的数据分析师，擅长理解数据结构和字段含义。"),
                HumanMessage(content=prompt)
            ]
            
            response = self.chat_model.invoke(messages)
            
            # 解析LLM响应
            field_mappings = self._parse_field_mappings(str(response.content))
            
            state["field_mappings"] = field_mappings
            logger.info(f"字段名猜测完成，处理了 {len(field_mappings)} 个字段")
            return state
            
        except Exception as e:
            logger.error(f"字段名猜测失败: {e}")
            state["error_message"] = str(e)
            return state

    def _generate_suggestions(self, state: CleaningState) -> CleaningState:
        """生成清洗建议"""
        try:
            df_data = state["df_data"]
            issues = state["quality_issues"]
            user_requirements = state.get("user_requirements", "")
            
            if df_data is None:
                raise ValueError("数据未加载")
            
            df = pd.DataFrame(df_data) # 反序列化DataFrame
            
            logger.info("开始生成清洗建议")
            
            # 基于质量问题生成建议
            suggestions = []
            
            for issue in issues:
                suggestion = self._create_cleaning_suggestion(issue, df)
                if suggestion:
                    suggestions.append(suggestion)
            
            # 如果有用户自定义要求，使用LLM生成额外建议
            if user_requirements:
                custom_suggestions = self._generate_custom_suggestions(df, user_requirements)
                suggestions.extend(custom_suggestions)
            
            state["cleaning_suggestions"] = suggestions
            logger.info(f"生成了 {len(suggestions)} 个清洗建议")
            return state
            
        except Exception as e:
            logger.error(f"生成清洗建议失败: {e}")
            state["error_message"] = str(e)
            return state

    def _apply_cleaning(self, state: CleaningState) -> CleaningState:
        """应用清洗操作"""
        try:
            df_data = state["df_data"]
            suggestions = state["cleaning_suggestions"]
            
            if df_data is None:
                raise ValueError("数据未加载")
            
            df = pd.DataFrame(df_data) # 反序列化DataFrame
            
            logger.info("开始应用清洗操作")
            
            # 创建数据副本用于清洗
            cleaned_df = df.copy()
            
            # 应用清洗建议
            for suggestion in suggestions:
                if suggestion.get("auto_apply", False):
                    cleaned_df = self._apply_single_cleaning(cleaned_df, suggestion)
            
            state["cleaned_df_data"] = cleaned_df.to_dict() # 序列化清洗后DataFrame
            logger.info(f"清洗操作完成，处理了 {len(suggestions)} 个建议")
            return state
            
        except Exception as e:
            logger.error(f"应用清洗操作失败: {e}")
            state["error_message"] = str(e)
            return state

    def _generate_summary(self, state: CleaningState) -> CleaningState:
        """生成清洗总结"""
        try:
            df_data = state["df_data"]
            cleaned_df_data = state["cleaned_df_data"]
            suggestions = state["cleaning_suggestions"]
            field_mappings = state["field_mappings"]
            
            logger.info("开始生成清洗总结")
            
            # 构建总结信息
            summary_parts = []
            
            # 基本信息对比
            if df_data is not None and cleaned_df_data is not None:
                df = pd.DataFrame(df_data) # 反序列化DataFrame
                cleaned_df = pd.DataFrame(cleaned_df_data) # 反序列化DataFrame
                summary_parts.append(f"原始数据: {len(df)} 行, {len(df.columns)} 列")
                summary_parts.append(f"清洗后数据: {len(cleaned_df)} 行, {len(cleaned_df.columns)} 列")
            
            # 字段映射信息
            if field_mappings:
                summary_parts.append(f"字段映射: 识别了 {len(field_mappings)} 个字段的含义")
            
            # 清洗建议信息
            if suggestions:
                summary_parts.append(f"清洗建议: 生成了 {len(suggestions)} 个建议")
            
            summary = "\n".join(summary_parts)
            state["cleaning_summary"] = summary
            
            logger.info("清洗总结生成完成")
            return state
            
        except Exception as e:
            logger.error(f"生成清洗总结失败: {e}")
            state["error_message"] = str(e)
            return state

    def _create_field_mapping_prompt(self, columns_info: List[Dict], sample_data: List[Dict], user_requirements: Optional[str]) -> str:
        """创建字段映射提示词"""
        prompt = f"""
请分析以下数据集的字段，并为每个字段提供标准化的名称和描述。

字段信息:
{json.dumps(columns_info, ensure_ascii=False, indent=2)}

数据样本:
{json.dumps(sample_data, ensure_ascii=False, indent=2)}

用户要求:
{user_requirements or "无特殊要求"}

请为每个字段提供以下信息，以JSON格式返回:
{{
  "field_mappings": [
    {{
      "original_name": "原始字段名",
      "suggested_name": "建议的标准字段名",
      "confidence": 0.95,
      "field_type": "字段类型(如: 数值型、文本型、日期型等)",
      "description": "字段含义的详细描述"
    }}
  ]
}}

要求:
1. 建议的字段名应该简洁、清晰、符合命名规范
2. 置信度应该基于数据样本的清晰程度
3. 字段类型要准确反映数据的实际类型
4. 描述要详细说明字段的业务含义
"""
        return prompt

    def _parse_field_mappings(self, response: str) -> Dict[str, str]:
        """解析LLM返回的字段映射"""
        try:
            # 尝试提取JSON部分
            json_match = re.search(r'\{.*\}', response, re.DOTALL)
            if json_match:
                json_str = json_match.group(0)
                parsed = json.loads(json_str)
                
                field_mappings = {}
                for mapping in parsed.get("field_mappings", []):
                    original = mapping.get("original_name")
                    suggested = mapping.get("suggested_name")
                    if original and suggested:
                        field_mappings[original] = suggested
                
                return field_mappings
            else:
                logger.warning("无法从LLM响应中提取JSON格式的字段映射")
                return {}
                
        except Exception as e:
            logger.error(f"解析字段映射失败: {e}")
            return {}

    def _generate_custom_suggestions(self, df: pd.DataFrame, user_requirements: str) -> List[Dict[str, Any]]:
        """基于用户要求生成自定义清洗建议"""
        try:
            # 构建数据概览
            data_overview = {
                "shape": df.shape,
                "columns": df.columns.tolist(),
                "dtypes": {col: str(dtype) for col, dtype in df.dtypes.items()},
                "missing_values": {col: int(df[col].isnull().sum()) for col in df.columns},
                "sample": df.head(3).to_dict('records')
            }
            
            prompt = f"""
基于用户的清洗要求，为以下数据集生成具体的清洗建议。

数据概览:
{json.dumps(data_overview, ensure_ascii=False, indent=2)}

用户要求:
{user_requirements}

请生成清洗建议，以JSON格式返回:
{{
  "suggestions": [
    {{
      "column": "列名",
      "issue_type": "问题类型",
      "description": "问题描述",
      "suggested_action": "建议的清洗动作",
      "priority": "优先级(high/medium/low)",
      "parameters": {{"参数名": "参数值"}},
      "auto_apply": false
    }}
  ]
}}

要求:
1. 建议要具体、可执行
2. 优先级要合理
3. 参数要完整
4. 只有安全的操作才设置auto_apply为true
"""
            
            messages = [
                SystemMessage(content="你是一位专业的数据清洗专家。"),
                HumanMessage(content=prompt)
            ]
            
            response = self.chat_model.invoke(messages)
            
            # 解析响应
            try:
                response_content = str(response.content)
                json_match = re.search(r'\{.*\}', response_content, re.DOTALL)
                if json_match:
                    json_str = json_match.group(0)
                    parsed = json.loads(json_str)
                    return parsed.get("suggestions", [])
            except Exception as e:
                logger.error(f"解析自定义建议失败: {e}")
                
            return []
            
        except Exception as e:
            logger.error(f"生成自定义建议失败: {e}")
            return []

    def _check_column_names(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """检查列名规范性"""
        issues = []
        
        for col in df.columns:
            col_issues = []
            
            # 检查空格
            if ' ' in col:
                col_issues.append("包含空格")
            
            # 检查特殊字符
            if re.search(r'[^\w\u4e00-\u9fff]', col):
                col_issues.append("包含特殊字符")
            
            # 检查长度
            if len(col) > 50:
                col_issues.append("名称过长")
            
            if col_issues:
                issues.append({
                    "type": "column_name",
                    "column": col,
                    "severity": "low",
                    "description": f"列名 '{col}' 存在问题: {', '.join(col_issues)}",
                    "issues": col_issues
                })
        
        return issues

    def _check_missing_values(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """检查缺失值"""
        issues = []
        
        for col in df.columns:
            missing_count = df[col].isnull().sum()
            if missing_count > 0:
                missing_rate = missing_count / len(df)
                severity = "high" if missing_rate > 0.5 else "medium" if missing_rate > 0.1 else "low"
                
                issues.append({
                    "type": "missing_values",
                    "column": col,
                    "severity": severity,
                    "description": f"列 '{col}' 有 {missing_count} 个缺失值 ({missing_rate:.2%})",
                    "count": int(missing_count),
                    "rate": float(missing_rate)
                })
        
        return issues

    def _check_data_types(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """检查数据类型一致性"""
        issues = []
        
        for col in df.columns:
            if df[col].dtype == 'object':
                # 检查是否应该是数值型
                non_null_values = df[col].dropna()
                if len(non_null_values) > 0:
                    numeric_count = sum(1 for val in non_null_values if self.patterns["numeric"].match(str(val)))
                    if numeric_count / len(non_null_values) > 0.8:
                        issues.append({
                            "type": "data_type",
                            "column": col,
                            "severity": "medium",
                            "description": f"列 '{col}' 可能应该是数值型",
                            "suggested_type": "numeric"
                        })
        
        return issues

    def _check_outliers(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        """检查异常值"""
        issues = []
        
        numeric_columns = df.select_dtypes(include=['number']).columns
        
        for col in numeric_columns:
            Q1 = df[col].quantile(0.25)
            Q3 = df[col].quantile(0.75)
            IQR = Q3 - Q1
            lower_bound = Q1 - 1.5 * IQR
            upper_bound = Q3 + 1.5 * IQR
            
            outliers = df[(df[col] < lower_bound) | (df[col] > upper_bound)]
            if len(outliers) > 0:
                issues.append({
                    "type": "outliers",
                    "column": col,
                    "severity": "low",
                    "description": f"列 '{col}' 有 {len(outliers)} 个异常值",
                    "count": len(outliers),
                    "bounds": {"lower": float(lower_bound), "upper": float(upper_bound)}
                })
        
        return issues

    def _calculate_quality_score(self, issues: List[Dict[str, Any]], total_rows: int, total_columns: int) -> float:
        """计算数据质量分数"""
        if not issues:
            return 100.0
        
        penalty = 0
        for issue in issues:
            severity = issue.get("severity", "low")
            if severity == "high":
                penalty += 20
            elif severity == "medium":
                penalty += 10
            else:
                penalty += 5
        
        score = max(0, 100 - penalty)
        return score

    def _create_cleaning_suggestion(self, issue: Dict[str, Any], df: pd.DataFrame) -> Optional[Dict[str, Any]]:
        """基于问题创建清洗建议"""
        issue_type = issue.get("type")
        column = issue.get("column")
        
        if issue_type == "missing_values":
            return {
                "column": column,
                "issue_type": issue_type,
                "description": issue["description"],
                "suggested_action": "填充缺失值或删除含缺失值的行",
                "priority": issue["severity"],
                "parameters": {
                    "method": "mean" if df[column].dtype in ['int64', 'float64'] else "mode",
                    "threshold": 0.5
                },
                "auto_apply": False
            }
        
        elif issue_type == "duplicate_rows":
            return {
                "column": "all",
                "issue_type": issue_type,
                "description": issue["description"],
                "suggested_action": "删除重复行",
                "priority": "medium",
                "parameters": {"keep": "first"},
                "auto_apply": True
            }
        
        elif issue_type == "column_name":
            return {
                "column": column,
                "issue_type": issue_type,
                "description": issue["description"],
                "suggested_action": "规范化列名",
                "priority": "low",
                "parameters": {"method": "normalize"},
                "auto_apply": True
            }
        
        elif issue_type == "data_type":
            return {
                "column": column,
                "issue_type": issue_type,
                "description": issue["description"],
                "suggested_action": f"转换为{issue['suggested_type']}类型",
                "priority": "medium",
                "parameters": {"target_type": issue["suggested_type"]},
                "auto_apply": False
            }
        
        return None

    def _apply_single_cleaning(self, df: pd.DataFrame, suggestion: Dict[str, Any]) -> pd.DataFrame:
        """应用单个清洗操作"""
        try:
            column = suggestion["column"]
            issue_type = suggestion["issue_type"]
            parameters = suggestion.get("parameters", {})
            
            if issue_type == "duplicate_rows":
                return df.drop_duplicates(keep=parameters.get("keep", "first"))
            
            elif issue_type == "column_name" and column in df.columns:
                # 规范化列名
                new_name = column.strip().replace(" ", "_")
                return df.rename(columns={column: new_name})
            
            elif issue_type == "missing_values" and column in df.columns:
                method = parameters.get("method", "mean")
                if method == "mean" and df[column].dtype in ['int64', 'float64']:
                    df[column] = df[column].fillna(df[column].mean())
                elif method == "mode":
                    df[column] = df[column].fillna(df[column].mode().iloc[0])
                elif method == "drop":
                    df = df.dropna(subset=[column])
                
                return df
            
            elif issue_type == "data_type" and column in df.columns:
                target_type = parameters.get("target_type")
                if target_type == "numeric":
                    df[column] = pd.to_numeric(df[column], errors='coerce')
                
                return df
            
            return df
            
        except Exception as e:
            logger.error(f"应用清洗操作失败: {e}")
            return df

    def process_file(self, file_path: str, user_requirements: Optional[str] = None) -> Dict[str, Any]:
        """处理数据文件的主要入口"""
        try:
            # 初始化状态
            initial_state = CleaningState(
                file_path=file_path,
                df_data=None,
                user_requirements=user_requirements,
                quality_issues=[],
                field_mappings={},
                cleaning_suggestions=[],
                cleaned_df_data=None,
                cleaning_summary="",
                error_message=None
            )
            
            # 执行工作流
            result = self.graph.invoke(initial_state, self.config)
            
            # 构建返回结果
            if result.get("error_message"):
                return {
                    "success": False,
                    "error": result["error_message"],
                    "quality_report": None,
                    "field_mappings": {},
                    "cleaning_suggestions": [],
                    "summary": ""
                }
            
            # 构建质量报告
            df_data = result.get("df_data")
            quality_report = None
            if df_data is not None:
                df = pd.DataFrame(df_data) # 反序列化DataFrame
                quality_report = DataQualityReport(
                    overall_score=self._calculate_quality_score(result["quality_issues"], len(df), len(df.columns)),
                    total_rows=len(df),
                    total_columns=len(df.columns),
                    missing_values_count=int(df.isna().sum().sum()),
                    duplicate_rows_count=int(df.duplicated().sum()),
                    issues=result["quality_issues"],
                    recommendations=[s.get("suggested_action", "") for s in result["cleaning_suggestions"]]
                ).model_dump()
            
            return {
                "success": True,
                "quality_report": quality_report,
                "field_mappings": result["field_mappings"],
                "cleaning_suggestions": result["cleaning_suggestions"],
                "summary": result["cleaning_summary"]
            }
            
        except Exception as e:
            logger.error(f"处理文件失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "quality_report": None,
                "field_mappings": {},
                "cleaning_suggestions": [],
                "summary": ""
            }

    def apply_cleaning_actions(self, file_path: str, actions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """应用指定的清洗动作"""
        try:
            # 加载数据
            path = Path(file_path)
            if path.suffix.lower() == '.csv':
                df = pd.read_csv(path)
            elif path.suffix.lower() in ['.xlsx', '.xls']:
                df = pd.read_excel(path)
            else:
                raise ValueError(f"不支持的文件格式: {path.suffix}")
            
            # 应用清洗动作
            results = []
            for action in actions:
                try:
                    df = self._apply_single_cleaning(df, action)
                    results.append({
                        "action": action,
                        "status": "success",
                        "message": "清洗动作应用成功"
                    })
                except Exception as e:
                    results.append({
                        "action": action,
                        "status": "error",
                        "message": str(e)
                    })
            
            return {
                "success": True,
                "results": results,
                "cleaned_rows": len(df),
                "cleaned_columns": len(df.columns)
            }
            
        except Exception as e:
            logger.error(f"应用清洗动作失败: {e}")
            return {
                "success": False,
                "error": str(e),
                "results": []
            }


# 创建全局实例
smart_clean_agent = SmartCleanDataAgent()


# 保持向后兼容的类名
class CleanDataAgent(SmartCleanDataAgent):
    """向后兼容的类名"""
    pass

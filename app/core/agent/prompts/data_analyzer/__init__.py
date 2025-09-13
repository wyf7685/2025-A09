from .._prompts import make_loader


@make_loader(__file__)
class PROMPTS:
    create_title: str
    default_report_template: str
    summary: str
    system: str
    tool_intro: str
    external_ml_model: str
    mcp_server: str
    mcp_tools_instruction: str

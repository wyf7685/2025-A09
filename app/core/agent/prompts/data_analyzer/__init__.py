from .._prompts import PromptLoader as _PromptLoader


class _Loader(_PromptLoader):
    create_title: str
    default_report_template: str
    summary: str
    system: str
    tool_intro: str


PROMPTS = _Loader(__file__)

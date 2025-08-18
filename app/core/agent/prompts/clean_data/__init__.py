from .._prompts import make_loader


@make_loader(__file__)
class PROMPTS:
    field_mapping: str
    generate_clean_code: str
    clean_suggestion: str

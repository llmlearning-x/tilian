"""
题库整理 Agent 工厂。
"""
from deepagents import create_deep_agent

from .config import get_kimi_model
from .prompts import BANK_IMPORT_AGENT_PROMPT
from .tools import execute_python, try_parse_json, validate_bank_json


def get_bank_import_agent(temperature: float = 0.2):
    """
    创建并返回一个基于 deepagents 的题库整理 Agent。

    该 Agent 使用 Kimi / Moonshot 模型，能把非标准文档内容整理成
    符合 TILIAN 题炼平台导入要求的标准 JSON 题库。
    """
    model = get_kimi_model(temperature=temperature)
    return create_deep_agent(
        model=model,
        tools=[try_parse_json, validate_bank_json, execute_python],
        system_prompt=BANK_IMPORT_AGENT_PROMPT,
    )

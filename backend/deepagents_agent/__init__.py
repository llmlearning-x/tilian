"""
DeepAgents 题库整理 Agent
用于把非标准文档（PDF/Word/TXT/Markdown/不规范 JSON）整理成
符合 TILIAN 题炼平台导入要求的标准 JSON 题库。
"""

from .agent import get_bank_import_agent

__all__ = ["get_bank_import_agent"]

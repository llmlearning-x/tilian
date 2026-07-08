"""
题库整理 Agent 的自定义工具。
"""
import json
import os
import subprocess
import tempfile
from typing import Union

from pydantic import ValidationError

from schemas import BankImportPayload


def try_parse_json(text: str) -> Union[dict, str]:
    """
    尝试把文本解析为 JSON 对象。

    Args:
        text: JSON 字符串，可能包含 markdown 代码块

    Returns:
        解析成功返回 dict，失败返回错误信息字符串。
    """
    cleaned = text.strip()
    # 去掉 markdown 代码块标记
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as exc:
        return f"错误：JSON 解析失败 - {exc}"


def validate_bank_json(data: dict) -> str:
    """
    验证字典是否符合平台题库导入格式。

    Args:
        data: 待验证的字典

    Returns:
        验证通过返回 "验证通过"，否则返回具体错误信息。
    """
    try:
        BankImportPayload.model_validate(data)
        return "验证通过"
    except ValidationError as exc:
        errors = []
        for error in exc.errors():
            location = ".".join(str(part) for part in error["loc"])
            errors.append(f"{location}: {error['msg']}")
        return "验证失败：\n" + "\n".join(errors)


def execute_python(code: str, input_text: str = "") -> str:
    """
    执行 Python 代码处理复杂文档内容，返回标准输出。

    当文档格式混乱、包含表格、需要正则提取、需要批量转换时，
    你可以调用本工具编写 Python 脚本完成预处理。

    Args:
        code: 要执行的 Python 代码。可通过变量 `input_text` 读取输入文本，
              使用 `print(...)` 输出结果。
        input_text: 输入的文档内容字符串

    Returns:
        代码执行的标准输出和错误输出。
    """
    # 构造完整脚本，把 input_text 注入为字符串变量
    script = f"""# -*- coding: utf-8 -*-
import json, re, sys
input_text = {json.dumps(input_text, ensure_ascii=False)}

{code}
"""
    fd, path = tempfile.mkstemp(suffix=".py", prefix="bank_agent_")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(script)

        result = subprocess.run(
            ["python", path],
            capture_output=True,
            text=True,
            timeout=30,
        )
        output = result.stdout
        if result.stderr:
            output += "\n[stderr]\n" + result.stderr
        return output
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass

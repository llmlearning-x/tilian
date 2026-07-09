"""
命令行入口：整理非标准文档为标准题库 JSON。

用法示例：
    cd backend
    python -m deepagents_agent.cli ../uploads/某文档.pdf -o ./output.json
"""
import argparse
import asyncio
import json
from pathlib import Path

from .agent import organize_bank
from .tools import validate_bank_json


def read_document(path: str) -> str:
    """
    读取 PDF/DOCX/TXT/MD/JSON 文档内容并返回文本。
    """
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from document_parser import extract_text

    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"文件不存在：{path}")
    if not p.is_file():
        raise ValueError(f"{path} 不是文件")

    suffix = p.suffix.lower().lstrip(".")
    if suffix == "json":
        return p.read_text(encoding="utf-8")
    return extract_text(p, suffix)


def extract_json_from_text(text: str) -> dict:
    """
    从 Agent 回复中提取 JSON 对象。
    """
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = "\n".join(cleaned.split("\n")[1:])
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3].strip()
    return json.loads(cleaned)


async def main():
    parser = argparse.ArgumentParser(
        description="使用 DeepAgents + Kimi 把非标准文档整理成标准题库 JSON"
    )
    parser.add_argument("input", help="输入文件路径（PDF/DOCX/TXT/MD/JSON）")
    parser.add_argument(
        "-o", "--output", default="./bank_import.json", help="输出 JSON 路径"
    )
    parser.add_argument(
        "-t", "--temperature", type=float, default=0.2, help="模型温度（默认 0.2）"
    )
    args = parser.parse_args()

    input_path = Path(args.input).resolve()
    output_path = Path(args.output).resolve()

    try:
        raw_text = read_document(str(input_path))
    except Exception as exc:
        print(f"读取文件失败：{exc}")
        return 1

    result = await organize_bank(raw_text)
    if not result["valid"]:
        print(f"Agent 整理失败：{result['validation']}")
        return 1

    bank_data = result["data"]
    validation = validate_bank_json(bank_data)
    if validation != "验证通过":
        print(f"Agent 输出未通过校验：\n{validation}")
        return 1

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(bank_data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    question_count = len(bank_data.get("questions", []))
    print(
        f"整理完成：题库《{bank_data.get('name')}》共 {question_count} 题，"
        f"已保存到 {output_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

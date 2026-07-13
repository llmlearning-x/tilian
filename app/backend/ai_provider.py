import json
import re

import httpx

from config import get_settings
from schemas import QuestionPayload


class AIConfigurationError(RuntimeError):
    pass


class AIOutputError(RuntimeError):
    pass


class AIProvider:
    async def generate_questions(
        self,
        document_text: str,
        single_count: int,
        multiple_count: int,
        difficulty: str,
    ) -> list[dict]:
        settings = get_settings()
        if not settings.LLM_API_URL or not settings.LLM_API_KEY or not settings.LLM_MODEL:
            raise AIConfigurationError("AI 服务未配置，请设置 LLM_API_URL、LLM_API_KEY 和 LLM_MODEL")

        prompt = self._build_prompt(document_text, single_count, multiple_count, difficulty)
        payload = {
            "model": settings.LLM_MODEL,
            "messages": [
                {"role": "system", "content": "你是严谨的教师，只能依据用户提供的材料出题。"},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.2,
        }
        headers = {"Authorization": f"Bearer {settings.LLM_API_KEY}", "Content-Type": "application/json"}
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(settings.LLM_API_URL, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.TimeoutException as exc:
            raise TimeoutError("AI 请求超时") from exc
        except httpx.HTTPError as exc:
            raise RuntimeError("AI 服务调用失败") from exc

        content = response.json().get("choices", [{}])[0].get("message", {}).get("content", "")
        raw = self._parse_json(content)
        expected = single_count + multiple_count
        if not isinstance(raw, list) or len(raw) != expected:
            raise AIOutputError(f"AI 返回题量不正确，应为 {expected} 题")
        normalized = [self._normalize_question(item) for item in raw]
        try:
            validated = [QuestionPayload.model_validate(item).model_dump() for item in normalized]
        except Exception as exc:
            raise AIOutputError("AI 返回的题目结构不合法") from exc
        if sum(item["type"] == "single" for item in validated) != single_count:
            raise AIOutputError("AI 返回的单选题数量不正确")
        if sum(item["type"] == "multiple" for item in validated) != multiple_count:
            raise AIOutputError("AI 返回的多选题数量不正确")
        return validated

    @staticmethod
    def _parse_json(content: str):
        cleaned = re.sub(r"^```(?:json)?\s*|\s*```$", "", content.strip(), flags=re.IGNORECASE)
        try:
            return json.loads(cleaned)
        except json.JSONDecodeError as exc:
            raise AIOutputError("AI 未返回有效 JSON") from exc

    @staticmethod
    def _normalize_question(item: dict) -> dict:
        """兼容不同模型对 options / answer 的返回格式。"""
        normalized = dict(item)

        # options 兼容：字符串数组 -> {label, content} 对象数组
        options = normalized.get("options", [])
        if options and isinstance(options[0], str):
            labels = ["A", "B", "C", "D", "E", "F"]
            normalized["options"] = [
                {"label": labels[i], "content": opt} for i, opt in enumerate(options[: len(labels)])
            ]

        # answer 兼容：字符串 -> 数组
        answer = normalized.get("answer", [])
        if isinstance(answer, str):
            normalized["answer"] = [answer]

        # 若 answer 是内容字符串，映射回选项 label
        label_map = {opt["content"]: opt["label"] for opt in normalized["options"]}
        normalized["answer"] = [label_map.get(a, a) for a in normalized["answer"]]

        return normalized

    @staticmethod
    def _build_prompt(text: str, single: int, multiple: int, difficulty: str) -> str:
        return f"""仅依据以下学习材料生成题目，不得补充材料之外的事实。
难度：{difficulty}
题量：单选题 {single} 道，多选题 {multiple} 道。
每题必须包含四个不重复选项、答案和解析。单选题答案一个，多选题答案至少两个。
只返回 JSON 数组。字段：type, stem, options, answer, explanation, difficulty。
- type: "single" 或 "multiple"
- options: 四个 {{"label": "A", "content": "选项内容"}} 对象
- answer: 选项 label 数组，例如 ["A"] 或 ["A", "B"]
- difficulty: 整数，easy=1, medium=2, hard=3

学习材料：
{text[:50000]}
"""


ai_provider = AIProvider()

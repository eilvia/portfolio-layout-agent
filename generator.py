import json
import os
from datetime import datetime, timezone
from itertools import count
from typing import Any

from openai import OpenAI

from server import get_components, validate_layout


JOB_LABELS = {
    "developer": "개발자",
    "designer": "디자이너",
    "cv": "대학원 진학용 CV",
}

CAREER_LABELS = {
    "entry": "신입",
    "three_plus": "3년 이상",
    "five_plus": "5년 이상",
    "ten_plus": "10년 이상",
}

DEFAULT_PLANS = {
    "developer": [
        "hero", "profile", "skills", "project", "troubleshooting",
        "architecture", "project", "metric", "contact",
    ],
    "designer": [
        "hero", "profile", "skills", "project", "gallery",
        "process", "project", "gallery", "metric", "contact",
    ],
    "cv": [
        "hero", "profile", "text", "experience", "paper",
        "paper", "project", "skills", "contact",
    ],
}

NON_REPEATABLE = {"hero", "profile", "contact", "section"}


class PortfolioGenerationError(RuntimeError):
    pass


def _call_json(client: OpenAI, model: str, system: str, user: str) -> dict[str, Any]:
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        text={"format": {"type": "json_object"}},
    )

    try:
        return json.loads(response.output_text)
    except (TypeError, json.JSONDecodeError) as exc:
        raise PortfolioGenerationError("AI가 올바른 JSON을 반환하지 않았습니다.") from exc


def _normalize_plan(raw_plan: Any, job_type: str, valid_types: set[str]) -> list[str]:
    if not isinstance(raw_plan, list):
        return DEFAULT_PLANS[job_type]

    result: list[str] = []
    seen_non_repeatable: set[str] = set()

    for item in raw_plan:
        block_type = item if isinstance(item, str) else item.get("type") if isinstance(item, dict) else None
        if block_type not in valid_types:
            continue
        if block_type in NON_REPEATABLE:
            if block_type in seen_non_repeatable:
                continue
            seen_non_repeatable.add(block_type)
        result.append(block_type)

    if "hero" not in result:
        result.insert(0, "hero")
    if "profile" not in result:
        result.insert(1, "profile")
    if "contact" not in result:
        result.append("contact")

    return result[:12] if len(result) >= 5 else DEFAULT_PLANS[job_type]


def _chunked(items: list[str], size: int = 3) -> list[list[str]]:
    return [items[index:index + size] for index in range(0, len(items), size)]


def _default_props(block_type: str, job_type: str) -> dict[str, Any]:
    preset = "research" if job_type == "cv" else job_type

    if block_type == "gallery":
        return {"layout": "carousel"}
    if block_type == "project":
        return {
            "display": "list" if job_type == "designer" else "card",
            "showThumbnail": True,
            "preset": preset,
        }
    if block_type == "skills":
        return {"display": "tag", "preset": preset}
    return {}


def _normalize_chunk(
    expected_types: list[str],
    raw_items: Any,
    job_type: str,
    order_start: int,
    type_counts: dict[str, count],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    items = raw_items if isinstance(raw_items, list) else []
    blocks: list[dict[str, Any]] = []
    values: list[dict[str, Any]] = []

    for offset, block_type in enumerate(expected_types):
        item = items[offset] if offset < len(items) and isinstance(items[offset], dict) else {}
        number = next(type_counts.setdefault(block_type, count(1)))
        block_id = f"{block_type}-{number:02d}"
        value = item.get("value") if isinstance(item.get("value"), dict) else {}
        props = item.get("props") if isinstance(item.get("props"), dict) else {}

        blocks.append({
            "id": block_id,
            "type": block_type,
            "category": "layout" if block_type in {"section", "columns", "spacer", "divider"} else "template",
            "label": str(item.get("label") or block_type.replace("_", " ").title()),
            "description": str(item.get("description") or ""),
            "layout": {
                "span": 12,
                "order": order_start + offset,
                "padding": 32 if block_type == "hero" else 24,
                "align": item.get("align") if item.get("align") in {"left", "center", "right"} else "left",
            },
            "style": {
                "variant": item.get("variant") if item.get("variant") in {"default", "highlight", "minimal", "ghost"} else "default",
                "emphasis": item.get("emphasis") if item.get("emphasis") in {"high", "medium", "low"} else "medium",
            },
            "repeatable": block_type not in NON_REPEATABLE,
            "props": {**_default_props(block_type, job_type), **props},
        })

        if block_type not in {"section", "columns", "spacer", "divider"}:
            values.append({"blockId": block_id, "type": block_type, "value": value})

    return blocks, values


def generate_portfolio(job_type: str, career_level: str, request: str) -> dict[str, Any]:
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise PortfolioGenerationError("OPENAI_API_KEY가 설정되지 않았습니다.")

    model = os.getenv("OPENAI_MODEL", "gpt-5.4-mini")
    client = OpenAI(api_key=api_key)
    component_spec = json.loads(get_components(job_type))
    valid_types = {component["id"] for component in component_spec}
    job_label = JOB_LABELS[job_type]
    career_label = CAREER_LABELS[career_level]

    system = """당신은 취업 및 대학원 포트폴리오 정보 설계자입니다.
사용자가 직접 내용을 채울 수 있는 편집 가능한 레이아웃 초안을 만드세요.
사용자가 제공하지 않은 회사명, 성과 수치, 프로젝트 사실은 꾸며내지 마세요.
모든 출력은 JSON 객체여야 합니다."""

    plan_payload = _call_json(
        client,
        model,
        system,
        f"""직무: {job_label}
경력 수준: {career_label}
추가 요청: {request}

사용 가능한 컴포넌트 명세:
{json.dumps(component_spec, ensure_ascii=False)}

5~12개의 블록 순서를 설계하세요. Hero, Profile, Contact는 각각 한 번만 사용하세요.
디자이너는 Gallery와 Process, 개발자는 Troubleshooting과 Architecture,
대학원 CV는 Paper와 Experience를 우선 고려하세요.
반드시 다음 형식으로만 응답하세요: {{"blockTypes": ["hero", "profile", "..."]}}""",
    )
    plan = _normalize_plan(plan_payload.get("blockTypes"), job_type, valid_types)

    all_blocks: list[dict[str, Any]] = []
    all_values: list[dict[str, Any]] = []
    type_counts: dict[str, count] = {}

    for chunk_index, expected_types in enumerate(_chunked(plan), start=1):
        chunk_payload = _call_json(
            client,
            model,
            system,
            f"""직무: {job_label}
경력 수준: {career_label}
추가 요청: {request}
현재 생성할 블록 순서: {json.dumps(expected_types, ensure_ascii=False)}

명세:
{json.dumps([item for item in component_spec if item['id'] in expected_types], ensure_ascii=False)}

각 블록에 대응하는 항목을 같은 순서와 개수로 작성하세요.
value에는 편집기에서 바로 수정할 수 있는 한국어 안내 문구나 빈 값을 넣으세요.
이미지 URL과 개인 정보는 빈 문자열로 두세요.
응답 형식:
{{"items": [{{"type": "hero", "label": "Hero", "description": "...", "props": {{}}, "align": "left", "variant": "default", "emphasis": "high", "value": {{}}}}]}}""",
        )

        blocks, values = _normalize_chunk(
            expected_types,
            chunk_payload.get("items"),
            job_type,
            len(all_blocks),
            type_counts,
        )
        validation = json.loads(validate_layout({"blocks": blocks}))
        if not validation.get("is_valid"):
            raise PortfolioGenerationError(
                f"{chunk_index}번째 블록 묶음 검증에 실패했습니다: {validation.get('errors', [])}"
            )
        all_blocks.extend(blocks)
        all_values.extend(values)

    template_id = f"portfolio-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"
    return {
        "portfolioTemplate": {
            "id": template_id,
            "title": f"{job_label} 포트폴리오",
            "jobType": job_type,
            "description": request,
            "version": 1,
            "previewMode": "template",
            "blocks": all_blocks,
            "createdAt": datetime.now(timezone.utc).isoformat(),
        },
        "portfolioContent": {
            "templateId": template_id,
            "values": all_values,
        },
    }

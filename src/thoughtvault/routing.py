from __future__ import annotations

from dataclasses import dataclass
import re


VALID_QUERY_ROUTES = {
    "fact",
    "knowledge",
    "recall",
    "reference",
    "synthesis",
    "evidence",
}


@dataclass(frozen=True)
class QueryRoute:
    route: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class QueryScope:
    time_scope: tuple[str, ...]
    entities: tuple[str, ...]
    document_hints: tuple[str, ...]
    measure_hints: tuple[str, ...]
    intent: str
    ambiguity: str | None
    reason: str


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


def infer_query_scope(query: str) -> QueryScope:
    normalized = " ".join(query.lower().split())
    time_values = []
    for year in re.findall(r"\b((?:19|20)\d{2})\b", normalized):
        time_values.append(year)
    for match in re.finditer(r"(?:(20\d{2})\s*[-年/])?\s*(1[0-2]|0?[1-9])\s*月", normalized):
        year, month = match.groups()
        if year:
            time_values.append(f"{int(year):04d}-{int(month):02d}")
        else:
            time_values.append(f"{int(month):02d}")
    deduped_time = list(dict.fromkeys(time_values))
    specific_years = {value[:4] for value in deduped_time if re.fullmatch(r"\d{4}-\d{2}(?:-\d{2})?", value)}
    time_scope = tuple(
        value for value in deduped_time
        if not (re.fullmatch(r"\d{4}", value) and value in specific_years)
    )

    document_hints = []
    document_markers = {
        "attendance_sheet": ("勤怠表", "勤怠", "出勤表"),
        "application_form": ("申請書", "申请书", "申请", "form"),
        "wiki_page": ("wiki", "知识页", "知識ページ"),
        "project_note": ("项目", "project"),
    }
    for hint, markers in document_markers.items():
        if _contains_any(normalized, markers):
            document_hints.append(hint)

    measure_hints = []
    measure_markers = {
        "amount": ("金额", "费用", "多少", "合计", "总计", "いくら", "how much"),
        "transport_cost": ("交通费", "交通費", "移動費", "移动费", "电车费", "電車代"),
        "date": ("日期", "什么时候", "何时", "いつ", "when"),
        "location": ("地点", "地方", "哪里", "哪儿", "場所", "どこ", "location"),
        "contact": ("电话", "電話", "手机号", "phone"),
        "status": ("状态", "状態", "status"),
    }
    for hint, markers in measure_markers.items():
        if _contains_any(normalized, markers):
            measure_hints.append(hint)

    entity_candidates = []
    subject_patterns = (
        r"(.{2,40}?)(?:的)?(?:电话|電話|手机号|phone)",
        r"(.{2,40}?)(?:住在哪里|住在哪|在哪里|在哪|場所|どこ)",
    )
    for pattern in subject_patterns:
        for match in re.finditer(pattern, query, re.IGNORECASE):
            candidate = match.group(1).strip(" ，,：:？?の的")
            if candidate and candidate not in {"资料", "文件", "表格", "document", "file"}:
                entity_candidates.append(candidate)
    for token in re.findall(r"[A-Za-z][A-Za-z0-9_.:-]{1,}|[\u3400-\u9fff]{2,}", query):
        lowered = token.casefold()
        marker_values = tuple(marker for markers in [*document_markers.values(), *measure_markers.values()] for marker in markers)
        if any(marker in lowered for marker in marker_values):
            continue
        if lowered in {"什么", "多少", "哪里", "哪天", "哪个月", "时候", "资料", "文件", "帮我总结"}:
            continue
        if any(stop in lowered for stop in ("多少", "什么", "哪里", "哪天", "哪个月", "时候", "总结", "整理", "归纳")):
            continue
        entity_candidates.append(token)
    entities = tuple(dict.fromkeys(entity_candidates[:8]))

    intent = "open_lookup"
    if measure_hints:
        intent = "fact_lookup"
    if _contains_any(normalized, ("资料", "文件", "表格", "document", "file")) and _contains_any(
        normalized,
        ("哪里", "在哪", "どこ", "where"),
    ):
        intent = "document_lookup"
    if document_hints and _contains_any(normalized, ("哪里", "在哪", "どこ", "where")):
        intent = "document_lookup"
    if _contains_any(normalized, ("总结", "整理", "归纳", "summarize", "synthesize")):
        intent = "synthesis"
    if _contains_any(normalized, ("是什么", "什么意思", "解释", "what is", "explain")):
        intent = "knowledge_lookup"

    ambiguity = None
    reason = "general scope hints extracted from query"
    if intent == "fact_lookup" and not time_scope and any(
        hint in measure_hints for hint in ("amount", "transport_cost", "date", "status")
    ):
        ambiguity = "missing_time_scope"
        reason = "fact lookup may vary over time but the query has no explicit time scope"
    if intent == "fact_lookup" and not entities and any(
        hint in measure_hints for hint in ("contact", "location")
    ):
        ambiguity = "missing_entity_scope"
        reason = "fact lookup needs a subject or entity scope"
    if intent == "document_lookup" and not document_hints and not entities:
        ambiguity = "missing_document_scope"
        reason = "document lookup needs a document type, topic, or entity scope"

    return QueryScope(
        time_scope=time_scope,
        entities=entities,
        document_hints=tuple(document_hints),
        measure_hints=tuple(measure_hints),
        intent=intent,
        ambiguity=ambiguity,
        reason=reason,
    )


def classify_query(query: str) -> QueryRoute:
    normalized = " ".join(query.lower().split())

    fact_markers = (
        "多少",
        "合计",
        "总计",
        "哪天",
        "哪一天",
        "什么时候",
        "何时",
        "哪个月",
        "更高",
        "相差",
        "いくら",
        "いつ",
        "when",
        "how much",
        "where",
    )
    fact_entities = (
        "交通费",
        "交通費",
        "移動費",
        "电车费",
        "電車代",
        "出勤",
        "勤怠",
        "日期",
        "金额",
        "电话",
        "電話",
    )
    if _contains_any(normalized, fact_markers) and (
        _contains_any(normalized, fact_entities)
        or re.search(r"\b20\d{2}[-/年]\d{1,2}", normalized)
        or re.search(r"\b\d{1,2}\s*月", normalized)
    ):
        return QueryRoute("fact", 0.9, "question asks for a constrained date, amount, place, or comparison")

    reference_markers = (
        "文件",
        "资料",
        "表格",
        "申请",
        "提交",
        "在哪",
        "哪里有",
        "どこ",
        "資料",
        "document",
        "file",
        "form",
    )
    if _contains_any(normalized, reference_markers):
        return QueryRoute("reference", 0.78, "question asks where a reusable source or document lives")

    recall_markers = (
        "我做过",
        "做过什么",
        "以前",
        "过去",
        "参与过",
        "用过",
        "worked on",
        "used before",
        "remember",
        "recall",
    )
    if _contains_any(normalized, recall_markers):
        return QueryRoute("recall", 0.82, "question asks to recover past exposure or work history")

    synthesis_markers = (
        "总结",
        "整理",
        "归纳",
        "延展",
        "比较",
        "对比",
        "summarize",
        "organize",
        "synthesize",
        "compare",
    )
    if _contains_any(normalized, synthesis_markers):
        return QueryRoute("synthesis", 0.76, "question asks for organization, synthesis, or comparison")

    knowledge_markers = (
        "是什么",
        "什么意思",
        "解释",
        "概念",
        "知识页",
        "wiki",
        "とは",
        "explain",
        "what is",
    )
    if _contains_any(normalized, knowledge_markers):
        return QueryRoute("knowledge", 0.74, "question asks for a concept or generated knowledge page")

    return QueryRoute("evidence", 0.55, "default route for open-ended source-backed evidence retrieval")

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


def _contains_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker in text for marker in markers)


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

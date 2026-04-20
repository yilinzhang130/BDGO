"""Attachment extraction → user message prep.

Turns ``req.message + req.file_ids`` into the final user_text (with
inlined file contents and a system-instruction trailer) plus a JSON
blob of file IDs for persistence.
"""

from __future__ import annotations

import asyncio
import json
import logging

from .attachments import extract_text

logger = logging.getLogger(__name__)


_SYS_INSTR_SUCCESS = (
    "\n\n[系统指令：用户上传了文件，文件内容已在上方提供。请立即执行以下步骤："
    "1) 从文件内容中提取公司名、资产名、靶点、适应症等关键实体；"
    "2) 用提取的实体并行调用 search_companies、search_assets、search_clinical、search_deals 查询CRM数据；"
    "3) 如果文件涉及特定疾病，调用 query_treatment_guidelines 查询治疗格局；"
    "4) 综合文件内容和CRM数据，输出结构化分析报告（公司画像、管线评估、治疗格局、交易参考、BD建议）。"
    "不要只总结文件内容，必须交叉验证CRM数据。]"
)


async def prepare_message_with_attachments(
    message: str, file_ids: list[str] | None
) -> tuple[str, str | None]:
    """Return ``(user_text, attachments_json)``.

    If ``file_ids`` is falsy, returns the original message and ``None``.
    Otherwise extracts all attachments in parallel (each PDF may OCR for
    seconds), inlines successful extractions, and appends a system
    instruction describing how the LLM should use them.
    """
    if not file_ids:
        return message, None

    extracted_list = await asyncio.gather(
        *(asyncio.to_thread(extract_text, fid) for fid in file_ids)
    )
    attachment_parts = []
    failed_extractions = []
    for fid, extracted in zip(file_ids, extracted_list):
        if extracted:
            logger.info("Extracted %d chars from attachment: %s", len(extracted), fid)
            attachment_parts.append(f"\n\n[附件内容: {fid}]\n{extracted}")
        else:
            logger.warning("Failed to extract content from attachment: %s", fid)
            failed_extractions.append(fid)

    if attachment_parts:
        user_text = message + "".join(attachment_parts) + _SYS_INSTR_SUCCESS
    elif failed_extractions:
        user_text = message + (
            f"\n\n[系统提示：用户上传了文件 {', '.join(failed_extractions)}，"
            "但文件内容无法提取（可能是加密PDF或格式不支持）。"
            "请直接告知用户文件无法解析，并询问他们能否提供文字版或核心信息。]"
        )
    else:
        user_text = message

    return user_text, json.dumps(file_ids)

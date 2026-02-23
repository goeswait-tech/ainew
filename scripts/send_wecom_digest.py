#!/usr/bin/env python3
"""Build and send a daily AI digest to WeCom (Enterprise WeChat) robot webhook."""

from __future__ import annotations

import argparse
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import requests

DEFAULT_TZ = ZoneInfo("Asia/Shanghai")
DEFAULT_BYTE_LIMIT = 3800


def parse_iso_to_bj(iso_str: str | None) -> str:
    if not iso_str:
        return "--:--"
    try:
        dt = datetime.fromisoformat(iso_str.replace("Z", "+00:00"))
        return dt.astimezone(DEFAULT_TZ).strftime("%m-%d %H:%M")
    except Exception:
        return str(iso_str)


def shorten(text: str, limit: int) -> str:
    s = (text or "").replace("\n", " ").strip()
    if len(s) <= limit:
        return s
    if limit <= 1:
        return "…"
    return s[: limit - 1] + "…"


def _header_lines(snapshot: dict[str, Any], keyword: str, total: int, site_url: str | None) -> list[str]:
    generated_at = parse_iso_to_bj(str(snapshot.get("generated_at") or ""))
    lines = []
    if keyword:
        lines.append(keyword)
    lines.append("## AI 新闻日报（近24小时）")
    lines.append(f"> 生成时间：{generated_at}（北京时间）")
    lines.append(f"> AI 相关条数：{total}")
    if site_url:
        lines.append(f"> 查看详情：[{site_url}]({site_url})")
    lines.append("")
    return lines


def _item_lines(items: list[dict[str, Any]], top_n: int, title_limit: int) -> list[str]:
    lines: list[str] = []
    for idx, item in enumerate(items[:top_n], 1):
        title = shorten(
            str(item.get("title_bilingual") or item.get("title") or "Untitled"),
            title_limit,
        )
        url = str(item.get("url") or "").strip()
        site = str(item.get("site_name") or "").strip() or "-"
        source = str(item.get("source") or "").strip() or "-"
        published = parse_iso_to_bj(str(item.get("published_at") or ""))
        if url:
            lines.append(f"{idx}. [{title}]({url})")
        else:
            lines.append(f"{idx}. {title}")
        lines.append(f"> {site}/{source} · {published}")
    return lines


def pick_ai_items(snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    raw = snapshot.get("items_ai") or snapshot.get("items") or []
    if not isinstance(raw, list):
        return []
    return [it for it in raw if isinstance(it, dict)]


def build_digest_markdown(
    snapshot: dict[str, Any],
    *,
    keyword: str = "AI新闻雷达",
    top_n: int = 12,
    byte_limit: int = DEFAULT_BYTE_LIMIT,
    site_url: str | None = None,
) -> tuple[str, int]:
    items = pick_ai_items(snapshot)
    total = len(items)
    shown = min(max(top_n, 0), total)
    shown = shown if shown > 0 else min(total, 3)
    title_limit = 46

    header = _header_lines(snapshot, keyword, total, site_url)
    min_items = 1 if total else 0

    while True:
        body = _item_lines(items, shown, title_limit)
        if total > shown:
            body.extend(["", f"> 其余 {total - shown} 条请查看页面或仓库数据"])
        content = "\n".join(header + body).strip()

        if len(content.encode("utf-8")) <= byte_limit:
            return content, shown

        if shown > min_items:
            shown -= 1
            continue

        if title_limit > 20:
            title_limit -= 4
            continue

        return content, shown


def send_wecom_markdown(webhook_url: str, content: str, timeout: int = 15) -> dict[str, Any]:
    payload = {"msgtype": "markdown", "markdown": {"content": content}}
    resp = requests.post(webhook_url, json=payload, timeout=timeout)
    resp.raise_for_status()
    data = resp.json()
    if int(data.get("errcode", -1)) != 0:
        raise RuntimeError(f"WeCom push failed: {data}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description="Send AI digest from latest-24h.json to WeCom webhook")
    parser.add_argument("--input", default="data/latest-24h.json", help="Path to snapshot JSON")
    parser.add_argument("--top-n", type=int, default=12, help="Max items to include before truncation")
    parser.add_argument("--keyword", default="AI新闻雷达", help="Keyword required by WeCom robot security policy")
    parser.add_argument("--byte-limit", type=int, default=DEFAULT_BYTE_LIMIT, help="WeCom markdown content byte limit")
    parser.add_argument("--site-url", default="", help="Optional public site URL for a 'view details' link")
    parser.add_argument("--webhook-env", default="WECOM_WEBHOOK_URL", help="Env var name storing WeCom webhook URL")
    parser.add_argument("--webhook-url", default="", help="Webhook URL (overrides env var)")
    parser.add_argument("--dry-run", action="store_true", help="Print generated markdown instead of sending")
    args = parser.parse_args()

    input_path = Path(args.input)
    snapshot = json.loads(input_path.read_text(encoding="utf-8"))
    content, shown = build_digest_markdown(
        snapshot,
        keyword=args.keyword,
        top_n=args.top_n,
        byte_limit=args.byte_limit,
        site_url=args.site_url or None,
    )

    if args.dry_run:
        print(content)
        print(f"\n[dry-run] shown={shown}")
        return 0

    webhook = (args.webhook_url or os.getenv(args.webhook_env, "")).strip()
    if not webhook:
        raise SystemExit(f"Missing webhook URL. Provide --webhook-url or set env {args.webhook_env}")

    result = send_wecom_markdown(webhook, content)
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

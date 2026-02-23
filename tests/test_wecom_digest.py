import unittest

from scripts.send_wecom_digest import build_digest_markdown, parse_iso_to_bj, pick_ai_items


class WeComDigestTests(unittest.TestCase):
    def test_pick_ai_items_prefers_items_ai(self):
        snapshot = {"items_ai": [{"title": "A"}], "items": [{"title": "B"}]}
        self.assertEqual(pick_ai_items(snapshot)[0]["title"], "A")

    def test_parse_iso_to_bj_converts_utc(self):
        self.assertEqual(parse_iso_to_bj("2026-02-23T01:00:00Z"), "02-23 09:00")

    def test_build_digest_markdown_contains_keyword_and_truncation(self):
        items = []
        for i in range(5):
            items.append(
                {
                    "title": f"标题{i}",
                    "url": f"https://example.com/{i}",
                    "site_name": "NewsNow",
                    "source": "demo",
                    "published_at": "2026-02-23T01:00:00Z",
                }
            )
        snapshot = {"generated_at": "2026-02-23T02:00:00Z", "items_ai": items}
        content, shown = build_digest_markdown(snapshot, keyword="AI新闻雷达", top_n=3, byte_limit=10000)
        self.assertIn("AI新闻雷达", content)
        self.assertIn("AI 新闻日报（近24小时）", content)
        self.assertIn("其余 2 条请查看页面或仓库数据", content)
        self.assertEqual(shown, 3)

    def test_build_digest_markdown_shrinks_to_byte_limit(self):
        long_title = "超长标题" * 50
        items = [
            {
                "title_bilingual": long_title,
                "url": "https://example.com/1",
                "site_name": "Site",
                "source": "src",
                "published_at": "2026-02-23T01:00:00Z",
            },
            {
                "title_bilingual": long_title,
                "url": "https://example.com/2",
                "site_name": "Site",
                "source": "src",
                "published_at": "2026-02-23T01:00:00Z",
            },
        ]
        snapshot = {"generated_at": "2026-02-23T02:00:00Z", "items_ai": items}
        content, shown = build_digest_markdown(snapshot, top_n=2, byte_limit=600)
        self.assertLessEqual(len(content.encode("utf-8")), 600)
        self.assertGreaterEqual(shown, 1)


if __name__ == "__main__":
    unittest.main()

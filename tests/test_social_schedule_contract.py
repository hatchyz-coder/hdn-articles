import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
PLAN = ROOT / "data/facebook-editorial-plan.json"
EVIDENCE = ROOT / "data/facebook-publishing-evidence.json"


class SocialScheduleContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.plan = json.loads(PLAN.read_text(encoding="utf-8"))
        cls.evidence = json.loads(EVIDENCE.read_text(encoding="utf-8"))
        cls.records = {
            item["public_url"].rstrip("/") + "/": item
            for item in cls.evidence.get("records", [])
            if item.get("status") == "scheduled"
        }

    def test_plan_has_18_unique_articles(self):
        posts = self.plan["posts"]
        ids = [item["article_id"] for item in posts]
        self.assertEqual(len(posts), 18)
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_planned_facebook_copy_meets_contract(self):
        urls = []
        for item in self.plan["posts"]:
            slug = item["article_id"]
            path = ROOT / "social" / slug / "facebook.md"
            self.assertTrue(path.is_file(), slug)
            text = path.read_text(encoding="utf-8").strip()
            url = f"https://article.hdnjapan.com/articles/{slug}/"
            self.assertTrue(text.startswith("【"), slug)
            self.assertGreaterEqual(len(text), 1200, slug)
            self.assertLessEqual(len(text), 1500, slug)
            self.assertIn(url, text, slug)
            urls.append(url)
        self.assertEqual(len(urls), len(set(urls)))

    def test_every_planned_linkedin_and_x_copy_meets_contract(self):
        for item in self.plan["posts"]:
            slug = item["article_id"]
            url = f"https://article.hdnjapan.com/articles/{slug}/"
            facebook = (ROOT / "social" / slug / "facebook.md").read_text(encoding="utf-8").strip()

            linkedin_path = ROOT / "social" / slug / "linkedin.md"
            x_path = ROOT / "social" / slug / "x.md"
            self.assertTrue(linkedin_path.is_file(), slug)
            self.assertTrue(x_path.is_file(), slug)

            linkedin = linkedin_path.read_text(encoding="utf-8").strip()
            x_copy = x_path.read_text(encoding="utf-8").strip()

            self.assertTrue(linkedin.startswith("【"), slug)
            self.assertIn(" / ", linkedin.splitlines()[0], slug)
            self.assertIn("English follows below.", linkedin, slug)
            self.assertLessEqual(len(linkedin), 3000, slug)
            self.assertIn(url, linkedin, slug)
            self.assertNotEqual(linkedin, facebook, slug)

            self.assertTrue(x_copy.startswith("【"), slug)
            self.assertIn(url, x_copy, slug)
            self.assertNotEqual(x_copy, facebook, slug)

    def test_plan_and_metricool_evidence_match(self):
        self.assertEqual(len(self.records), 18)
        for item in self.plan["posts"]:
            slug = item["article_id"]
            url = f"https://article.hdnjapan.com/articles/{slug}/"
            record = self.records.get(url)
            self.assertIsNotNone(record, slug)
            self.assertEqual(record["scheduled_at"], item["scheduled_at"], slug)
            self.assertTrue(record.get("metricool_post_id"), slug)
            self.assertTrue(record.get("metricool_uuid"), slug)
            self.assertEqual(record.get("status"), "scheduled", slug)


if __name__ == "__main__":
    unittest.main()

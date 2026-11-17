import tempfile
import unittest
from pathlib import Path

from exchange import Exchange


class IdentityTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.service = Exchange(Path(self.temp.name) / "exchange.db")
        day = "2026-11-01"
        self.service.catalog.register("inspect", "暗访组", "甲地", "observation",
                                      [("finding", "服务观察", "text", False)], day)
        self.service.catalog.register("operator", "运营公司", "甲地", "response",
                                      [("statement", "说明与整改", "text", False)], day)
        self.service.identity.register("sub-a", "青云湖景区", "甲地", day, "资料室")
        self.service.identity.register("sub-b", "青云湖景区", "乙地", day, "资料室")
        self.service.catalog.ingest("obs-1", "inspect", {"finding": "咨询台无人值守"}, day)
        self.service.attributions.attribute("attr-1", "obs-1", "sub-a", "青云湖景区",
                                            "甲地名录 JT-甲-017", day, "资料室")

    def tearDown(self):
        self.service.close()
        self.temp.cleanup()

    def add_response(self, asset_id, attribution_id, subject="sub-a", day="2026-11-02"):
        self.service.catalog.ingest(asset_id, "operator", {"statement": "说明 " + asset_id}, day)
        self.service.attributions.attribute(attribution_id, asset_id, subject, "青云湖景区",
                                            "名录核对", day, "资料室")


class AttributionTest(IdentityTestCase):
    def test_same_name_subjects_stay_distinct(self):
        self.service.catalog.ingest("obs-2", "inspect", {"finding": "停车场指引缺失"}, "2026-11-02")
        self.service.attributions.attribute("attr-2", "obs-2", "sub-b", "青云湖景区",
                                            "乙地名录 JT-乙-004", "2026-11-02", "资料室")
        first = self.service.attributions.verify("obs-1")
        second = self.service.attributions.verify("obs-2")
        self.assertEqual(first["attribution"]["subject_id"], "sub-a")
        self.assertEqual(second["attribution"]["subject_id"], "sub-b")
        self.assertTrue(first["claimed_name_known"])
        self.assertTrue(second["claimed_name_known"])

    def test_attribution_requires_active_subject_and_single_current(self):
        with self.assertRaises(ValueError):
            self.service.attributions.attribute("attr-x", "obs-1", "sub-a", "青云湖景区",
                                                "重复登记", "2026-11-02", "资料室")
        with self.assertRaises(KeyError):
            self.service.attributions.attribute("attr-y", "obs-1", "sub-unknown", "青云湖景区",
                                                "未知主体", "2026-11-02", "资料室")

    def test_correction_keeps_previous_version(self):
        self.service.catalog.ingest("obs-2", "inspect", {"finding": "同名混淆记录"}, "2026-11-02")
        self.service.attributions.attribute("attr-2", "obs-2", "sub-b", "青云湖景区",
                                            "按名称初判", "2026-11-02", "资料室")
        self.service.attributions.correct("attr-2b", "obs-2", "sub-a", "青云湖景区",
                                          "甲地名录 JT-甲-017", "同名景区误并，按名录更正",
                                          "2026-11-03", "资料室")
        verified = self.service.attributions.verify("obs-2")
        self.assertEqual(verified["attribution"]["subject_id"], "sub-a")
        history = self.service.attributions.history("obs-2")
        self.assertEqual([row["state"] for row in history], ["superseded", "active"])
        self.assertEqual(history[1]["supersedes"], "attr-2")

    def test_rename_keeps_claimed_name_verifiable(self):
        self.service.identity.rename("ev-1", "sub-a", "青云湖国际旅游度假区",
                                     "2026-11-02", "资料室", "运营方更名备案")
        verified = self.service.attributions.verify("obs-1")
        self.assertTrue(verified["claimed_name_known"])
        lineage = self.service.identity.lineage("sub-a")
        self.assertEqual([name["name"] for name in lineage["names"]],
                         ["青云湖景区", "青云湖国际旅游度假区"])


class ResponseLinkTest(IdentityTestCase):
    def test_response_versions_and_sources_kept(self):
        self.add_response("resp-1", "attr-r1")
        self.add_response("resp-2", "attr-r2", day="2026-11-03")
        self.service.responses.link("link-1", "resp-1", "obs-1", "2026-11-02", "资料室")
        self.service.responses.link("link-2", "resp-2", "obs-1", "2026-11-03", "资料室")
        responses = self.service.responses.for_observation("obs-1")
        self.assertEqual([row["asset_id"] for row in responses], ["resp-1", "resp-2"])
        self.assertEqual({row["owner"] for row in responses}, {"运营公司"})
        self.assertNotEqual(responses[0]["digest"], responses[1]["digest"])

    def test_link_requires_same_subject(self):
        self.add_response("resp-1", "attr-r1", subject="sub-b")
        with self.assertRaises(ValueError):
            self.service.responses.link("link-1", "resp-1", "obs-1", "2026-11-02", "资料室")

    def test_link_requires_attributed_materials(self):
        self.service.catalog.ingest("resp-1", "operator", {"statement": "未归属"}, "2026-11-02")
        with self.assertRaises(ValueError):
            self.service.responses.link("link-1", "resp-1", "obs-1", "2026-11-02", "资料室")


class DisputeTest(IdentityTestCase):
    def test_open_dispute_excluded_until_decided(self):
        self.service.disputes.raise_dispute("dp-1", "obs-1", "sub-a",
                                            "记录日期与闭园维护日重合", "2026-11-02")
        first = self.service.conclusions.compile("sub-a", "第一次摘要", "2026-11-03", "评级组")
        item = self.service.conclusions.items("sub-a", first)[0]
        self.assertEqual(item["decision"], "excluded")
        self.assertIn("争议未裁定", item["reason"])
        self.assertEqual(item["dispute_id"], "dp-1")
        self.service.disputes.decide("dp-1", "rejected", "当日正常开放", "2026-11-04", "复核组")
        second = self.service.conclusions.compile("sub-a", "第二次摘要", "2026-11-05", "评级组")
        item = self.service.conclusions.items("sub-a", second)[0]
        self.assertEqual(item["decision"], "adopted")
        self.assertIn("质疑已驳回", item["reason"])

    def test_upheld_dispute_stays_excluded(self):
        self.service.disputes.raise_dispute("dp-1", "obs-1", "sub-a", "观察对象错误", "2026-11-02")
        self.service.disputes.decide("dp-1", "upheld", "核实为邻区设施", "2026-11-03", "复核组")
        revision = self.service.conclusions.compile("sub-a", "摘要", "2026-11-04", "评级组")
        item = self.service.conclusions.items("sub-a", revision)[0]
        self.assertEqual(item["decision"], "excluded")
        self.assertIn("质疑成立", item["reason"])

    def test_dispute_only_by_attributed_subject_and_single_open(self):
        with self.assertRaises(ValueError):
            self.service.disputes.raise_dispute("dp-1", "obs-1", "sub-b", "越权质疑", "2026-11-02")
        self.service.disputes.raise_dispute("dp-2", "obs-1", "sub-a", "合理质疑", "2026-11-02")
        with self.assertRaises(ValueError):
            self.service.disputes.raise_dispute("dp-3", "obs-1", "sub-a", "重复质疑", "2026-11-03")
        with self.assertRaises(ValueError):
            self.service.disputes.decide("dp-2", "maybe", "无效", "2026-11-04", "复核组")


class IdentityEventTest(IdentityTestCase):
    def test_merge_reattributes_and_trace_survives(self):
        self.service.catalog.ingest("obs-2", "inspect", {"finding": "停车场指引缺失"}, "2026-11-02")
        self.service.attributions.attribute("attr-2", "obs-2", "sub-b", "青云湖景区",
                                            "乙地名录 JT-乙-004", "2026-11-02", "资料室")
        self.add_response("resp-2", "attr-r2", subject="sub-b")
        self.service.responses.link("link-2", "resp-2", "obs-2", "2026-11-02", "资料室")
        self.service.identity.merge("ev-1", "sub-a", ["sub-b"], "2026-11-03", "资料室", "行政区划调整")
        verified = self.service.attributions.verify("obs-2")
        self.assertEqual(verified["attribution"]["subject_id"], "sub-a")
        self.assertEqual(verified["attribution"]["event_id"], "ev-1")
        self.assertTrue(verified["claimed_name_known"])
        trace = self.service.conclusions.trace("obs-2")
        self.assertEqual([row["subject_id"] for row in trace["attributions"]], ["sub-b", "sub-a"])
        self.assertEqual(trace["attributions"][0]["state"], "superseded")
        self.assertEqual(trace["responses"][0]["owner"], "运营公司")
        revision = self.service.conclusions.compile("sub-a", "并入后摘要", "2026-11-04", "评级组")
        adopted = {item["observation_asset_id"] for item in self.service.conclusions.items("sub-a", revision)
                   if item["decision"] == "adopted"}
        self.assertEqual(adopted, {"obs-1", "obs-2"})
        self.service.catalog.ingest("obs-9", "inspect", {"finding": "迟到的记录"}, "2026-11-04")
        with self.assertRaises(ValueError):
            self.service.attributions.attribute("attr-9", "obs-9", "sub-b", "青云湖景区",
                                                "停用主体", "2026-11-04", "资料室")

    def test_split_requires_full_assignment_and_reattributes(self):
        self.service.catalog.ingest("obs-2", "inspect", {"finding": "西区厕所缺位"}, "2026-11-02")
        self.service.attributions.attribute("attr-2", "obs-2", "sub-a", "青云湖景区",
                                            "甲地名录 JT-甲-017", "2026-11-02", "资料室")
        with self.assertRaises(ValueError):
            self.service.identity.split("ev-1", "sub-a", {"sub-east": "青云湖东园", "sub-west": "青云湖西园"},
                                        {"obs-1": "sub-east"}, "2026-11-03", "资料室", "遗漏材料")
        self.service.identity.split("ev-2", "sub-a", {"sub-east": "青云湖东园", "sub-west": "青云湖西园"},
                                    {"obs-1": "sub-east", "obs-2": "sub-west"},
                                    "2026-11-03", "资料室", "景区一分为二")
        self.assertEqual(self.service.attributions.current("obs-1")["subject_id"], "sub-east")
        self.assertEqual(self.service.attributions.current("obs-2")["subject_id"], "sub-west")
        lineage = self.service.identity.lineage("sub-west")
        self.assertEqual(lineage["events"][0]["kind"], "split")
        with self.assertRaises(ValueError):
            self.service.conclusions.compile("sub-a", "停用主体摘要", "2026-11-04", "评级组")

    def test_conclusion_pins_attribution_version(self):
        first = self.service.conclusions.compile("sub-a", "第一次摘要", "2026-11-02", "评级组")
        self.service.attributions.correct("attr-1b", "obs-1", "sub-a", "青云湖景区",
                                          "补充名录编号", "依据补全", "2026-11-03", "资料室")
        second = self.service.conclusions.compile("sub-a", "第二次摘要", "2026-11-04", "评级组")
        pinned = self.service.conclusions.items("sub-a", first)[0]
        current = self.service.conclusions.items("sub-a", second)[0]
        self.assertEqual(pinned["attribution_id"], "attr-1")
        self.assertEqual(current["attribution_id"], "attr-1b")
        trace = self.service.conclusions.trace("obs-1")
        self.assertEqual([row["revision"] for row in trace["conclusions"]], [first, second])

    def test_compile_requires_observations(self):
        with self.assertRaises(ValueError):
            self.service.conclusions.compile("sub-b", "空摘要", "2026-11-02", "评级组")


if __name__ == "__main__":
    unittest.main()

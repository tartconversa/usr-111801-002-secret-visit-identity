import argparse
import json
from .service import Exchange


def run(service):
    day = "2026-11-17"
    # 暗访组与景区运营方分别登记来源，观察与答复保持不同来源
    service.catalog.register("inspect", "暗访组", "甲地", "observation",
                             [("finding", "服务观察", "text", False)], day)
    service.catalog.register("operator", "青云湖运营公司", "甲地", "response",
                             [("statement", "说明与整改", "text", False)], day)
    # 两个同名景区主体，辖区不同，编号各自稳定
    service.identity.register("sub-east", "青云湖景区", "甲地", day, "资料室")
    service.identity.register("sub-west", "青云湖景区", "乙地", day, "资料室")
    # 暗访观察按主体编号归属，申报名称与名录依据留痕备核
    service.catalog.ingest("obs-1", "inspect", {"finding": "咨询台无人值守"}, day)
    service.attributions.attribute("attr-1", "obs-1", "sub-east", "青云湖景区",
                                   "甲地名录编号 JT-甲-017", day, "资料室")
    # 景区提交说明，归属同一主体后与观察建立对应
    service.catalog.ingest("resp-1", "operator", {"statement": "当日轮班表与整改措施附后"}, day)
    service.attributions.attribute("attr-2", "resp-1", "sub-east", "青云湖景区",
                                   "甲地名录编号 JT-甲-017", day, "资料室")
    service.responses.link("link-1", "resp-1", "obs-1", day, "资料室")
    # 景区提出质疑：争议未裁定时，观察不得进入评级摘要的已确认事实
    service.disputes.raise_dispute("dp-1", "obs-1", "sub-east", "记录日期与闭园维护日重合", day)
    first = service.conclusions.compile("sub-east", "第一次评级摘要", day, "评级组")
    # 质疑裁定驳回后，观察才列为已确认事实
    service.disputes.decide("dp-1", "rejected", "调阅开放记录，当日正常开放", "2026-11-18", "复核组")
    second = service.conclusions.compile("sub-east", "第二次评级摘要", "2026-11-18", "评级组")
    # 名称调整与同名主体并入：原有归属、答复与结论均可追溯
    service.identity.rename("ev-1", "sub-east", "青云湖国际旅游度假区", "2026-11-19", "资料室", "运营方更名备案")
    service.catalog.ingest("obs-2", "inspect", {"finding": "停车场指引缺失"}, "2026-11-19")
    service.attributions.attribute("attr-3", "obs-2", "sub-west", "青云湖景区",
                                   "乙地名录编号 JT-乙-004", "2026-11-19", "资料室")
    service.identity.merge("ev-2", "sub-east", ["sub-west"], "2026-11-20", "资料室", "行政区划调整，乙地主体并入")
    third = service.conclusions.compile("sub-east", "并入后评级摘要", "2026-11-20", "评级组")
    return {
        "revisions": [first, second, third],
        "items": service.conclusions.items("sub-east", third),
        "trace_obs_2": service.conclusions.trace("obs-2"),
        "lineage": service.identity.lineage("sub-east"),
    }


def main():
    parser = argparse.ArgumentParser(description="景区资料本地协作演练")
    parser.add_argument("--database", required=True)
    args = parser.parse_args()
    service = Exchange(args.database)
    try:
        report = run(service)
        print(json.dumps(report, ensure_ascii=False, sort_keys=True))
    finally:
        service.close()


if __name__ == "__main__":
    main()

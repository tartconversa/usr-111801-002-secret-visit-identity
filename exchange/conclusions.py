import json

from .audit import write
from .attribution import Attributions
from .disputes import Disputes
from .identity import Identities
from .responses import Responses


class Conclusions:
    """评级摘要：逐条记录观察的采用或排除及理由；争议未裁定的观察不得列为已确认事实。"""

    def __init__(self, connection):
        self.connection = connection
        self.attributions = Attributions(connection)
        self.disputes = Disputes(connection)
        self.identities = Identities(connection)
        self.responses = Responses(connection)

    def compile(self, subject_id, summary, at, actor):
        self.identities.require_active(subject_id)
        rows = self.connection.execute(
            "SELECT t.id AS attribution_id,t.asset_id FROM attributions t "
            "WHERE t.subject_id=? AND t.state='active' "
            "AND t.asset_id NOT IN (SELECT response_asset_id FROM response_links) "
            "ORDER BY t.asset_id",
            (subject_id,),
        ).fetchall()
        if not rows:
            raise ValueError("没有可总结的观察")
        revision = self.connection.execute(
            "SELECT COALESCE(MAX(revision),0)+1 FROM conclusions WHERE subject_id=?", (subject_id,),
        ).fetchone()[0]
        items = []
        for row in rows:
            state = self.disputes.state(row["asset_id"])
            if state["state"] == "open":
                decision, reason = "excluded", "争议未裁定，不得作为已确认事实"
            elif state["state"] == "upheld":
                decision, reason = "excluded", "质疑成立，观察不作为已确认事实"
            elif state["state"] == "rejected":
                decision, reason = "adopted", "质疑已驳回，列为已确认事实"
            else:
                decision, reason = "adopted", "无争议，列为已确认事实"
            items.append({
                "observation_asset_id": row["asset_id"],
                "attribution_id": row["attribution_id"],
                "dispute_id": state["dispute"]["id"] if state["dispute"] else None,
                "decision": decision,
                "reason": reason,
                "responses": self.responses.for_observation(row["asset_id"]),
            })
        with self.connection:
            self.connection.execute(
                "INSERT INTO conclusions(subject_id,revision,summary,created_at,created_by) VALUES(?,?,?,?,?)",
                (subject_id, revision, summary, at, actor),
            )
            self.connection.executemany(
                "INSERT INTO conclusion_items(subject_id,revision,observation_asset_id,attribution_id,dispute_id,decision,reason,responses)"
                " VALUES(?,?,?,?,?,?,?,?)",
                [(subject_id, revision, item["observation_asset_id"], item["attribution_id"], item["dispute_id"],
                  item["decision"], item["reason"],
                  json.dumps(item["responses"], ensure_ascii=False, sort_keys=True)) for item in items],
            )
            write(self.connection, at, actor, "conclusion.compile", subject_id, {
                "revision": revision,
                "adopted": [item["observation_asset_id"] for item in items if item["decision"] == "adopted"],
                "excluded": [item["observation_asset_id"] for item in items if item["decision"] == "excluded"],
            })
        return revision

    def items(self, subject_id, revision):
        rows = self.connection.execute(
            "SELECT * FROM conclusion_items WHERE subject_id=? AND revision=? ORDER BY observation_asset_id",
            (subject_id, revision),
        ).fetchall()
        result = []
        for row in rows:
            item = dict(row)
            item["responses"] = json.loads(item["responses"])
            result.append(item)
        return result

    def trace(self, asset_id):
        asset = self.connection.execute("SELECT * FROM assets WHERE id=?", (asset_id,)).fetchone()
        if asset is None:
            raise KeyError(asset_id)
        conclusions = [dict(row) for row in self.connection.execute(
            "SELECT subject_id,revision,attribution_id,dispute_id,decision,reason FROM conclusion_items "
            "WHERE observation_asset_id=? ORDER BY subject_id,revision",
            (asset_id,),
        )]
        disputes = [dict(row) for row in self.connection.execute(
            "SELECT * FROM disputes WHERE observation_asset_id=? ORDER BY raised_at,id",
            (asset_id,),
        )]
        return {
            "asset": dict(asset),
            "attributions": self.attributions.history(asset_id),
            "responses": self.responses.for_observation(asset_id),
            "answers": self.responses.answers(asset_id),
            "disputes": disputes,
            "conclusions": conclusions,
        }

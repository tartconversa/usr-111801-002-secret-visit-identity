from .audit import write
from .attribution import Attributions


class Disputes:
    """景区对观察的质疑与裁定；存在未裁定质疑的观察不得视为已确认事实。"""

    DECISIONS = {"upheld", "rejected"}

    def __init__(self, connection):
        self.connection = connection
        self.attributions = Attributions(connection)

    def raise_dispute(self, dispute_id, observation_asset_id, raised_by, grounds, at):
        attribution = self.attributions.current(observation_asset_id)
        if attribution is None:
            raise ValueError("观察尚未归属景区主体")
        if attribution["subject_id"] != raised_by:
            raise ValueError("质疑须由被归属的景区主体提出")
        if self.connection.execute(
            "SELECT 1 FROM disputes WHERE observation_asset_id=? AND state='open'",
            (observation_asset_id,),
        ).fetchone():
            raise ValueError("该观察已有未裁定的质疑")
        with self.connection:
            self.connection.execute(
                "INSERT INTO disputes(id,observation_asset_id,raised_by,raised_at,grounds) VALUES(?,?,?,?,?)",
                (dispute_id, observation_asset_id, raised_by, at, grounds),
            )
            write(self.connection, at, raised_by, "dispute.raise", dispute_id,
                  {"observation": observation_asset_id, "grounds": grounds})

    def decide(self, dispute_id, decision, note, at, actor):
        if decision not in self.DECISIONS:
            raise ValueError("裁定结果无效")
        row = self.connection.execute("SELECT * FROM disputes WHERE id=?", (dispute_id,)).fetchone()
        if row is None:
            raise KeyError(dispute_id)
        if row["state"] != "open":
            raise ValueError("质疑已裁定")
        with self.connection:
            self.connection.execute(
                "UPDATE disputes SET state=?,decided_at=?,decided_by=?,decision_note=? WHERE id=?",
                (decision, at, actor, note, dispute_id),
            )
            write(self.connection, at, actor, "dispute.decide", dispute_id,
                  {"decision": decision, "observation": row["observation_asset_id"], "note": note})

    def state(self, observation_asset_id):
        row = self.connection.execute(
            "SELECT * FROM disputes WHERE observation_asset_id=? AND state='open' ORDER BY raised_at,id LIMIT 1",
            (observation_asset_id,),
        ).fetchone()
        if row is None:
            row = self.connection.execute(
                "SELECT * FROM disputes WHERE observation_asset_id=? ORDER BY decided_at DESC,id DESC LIMIT 1",
                (observation_asset_id,),
            ).fetchone()
        if row is None:
            return {"state": None, "dispute": None}
        return {"state": row["state"], "dispute": dict(row)}

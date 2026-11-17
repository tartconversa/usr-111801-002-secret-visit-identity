from .audit import write
from .identity import Identities


class Attributions:
    """把在册原件归属到景区主体：按主体编号归属，保留申报名称与依据，可核对、可更正。"""

    def __init__(self, connection):
        self.connection = connection
        self.identities = Identities(connection)

    def attribute(self, attribution_id, asset_id, subject_id, claimed_name, basis, at, actor, note=None):
        self._require_asset(asset_id)
        self.identities.require_active(subject_id)
        existing = self.connection.execute(
            "SELECT id FROM attributions WHERE asset_id=? AND state='active'", (asset_id,),
        ).fetchone()
        if existing:
            raise ValueError("材料已有有效归属，需更正或经身份事件迁移")
        with self.connection:
            self._insert(attribution_id, asset_id, subject_id, claimed_name, basis, note, at, actor, None, None)
            write(self.connection, at, actor, "attribution.attribute", attribution_id,
                  {"asset": asset_id, "subject": subject_id, "claimed_name": claimed_name, "basis": basis})

    def correct(self, attribution_id, asset_id, subject_id, claimed_name, basis, reason, at, actor):
        current = self.connection.execute(
            "SELECT * FROM attributions WHERE asset_id=? AND state='active'", (asset_id,),
        ).fetchone()
        if current is None:
            raise ValueError("材料尚无有效归属，应直接登记")
        self.identities.require_active(subject_id)
        with self.connection:
            self.connection.execute("UPDATE attributions SET state='superseded' WHERE id=?", (current["id"],))
            self._insert(attribution_id, asset_id, subject_id, claimed_name, basis, reason, at, actor, current["id"], None)
            write(self.connection, at, actor, "attribution.correct", attribution_id,
                  {"asset": asset_id, "from": current["subject_id"], "to": subject_id, "reason": reason})

    def current(self, asset_id):
        row = self.connection.execute(
            "SELECT * FROM attributions WHERE asset_id=? AND state='active'", (asset_id,),
        ).fetchone()
        return dict(row) if row else None

    def for_subject(self, subject_id):
        rows = self.connection.execute(
            "SELECT * FROM attributions WHERE subject_id=? AND state='active' ORDER BY asset_id",
            (subject_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def history(self, asset_id):
        rows = self.connection.execute(
            "SELECT * FROM attributions WHERE asset_id=? ORDER BY created_at,id", (asset_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def verify(self, asset_id):
        row = self.current(asset_id)
        if row is None:
            return {"asset": asset_id, "attributed": False}
        subject = self.identities.get(row["subject_id"])
        known = self.identities.known_names(row["subject_id"])
        return {
            "asset": asset_id,
            "attributed": True,
            "attribution": row,
            "subject_status": subject["status"],
            "claimed_name_known": row["claimed_name"] in known,
            "known_names": known,
        }

    def _require_asset(self, asset_id):
        row = self.connection.execute(
            "SELECT id FROM assets WHERE id=? AND state='active'", (asset_id,),
        ).fetchone()
        if row is None:
            raise KeyError(asset_id)

    def _insert(self, attribution_id, asset_id, subject_id, claimed_name, basis, note, at, actor, supersedes, event_id):
        self.connection.execute(
            "INSERT INTO attributions(id,asset_id,subject_id,claimed_name,basis,note,state,created_at,created_by,supersedes,event_id)"
            " VALUES(?,?,?,?,?,?,'active',?,?,?,?)",
            (attribution_id, asset_id, subject_id, claimed_name, basis, note, at, actor, supersedes, event_id),
        )

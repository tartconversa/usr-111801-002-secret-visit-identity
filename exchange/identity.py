import json

from .audit import write


class Identities:
    """景区主体身份登记与沿革：更名、合并、拆分均留痕，主体编号稳定。"""

    def __init__(self, connection):
        self.connection = connection

    def register(self, subject_id, name, jurisdiction, at, actor):
        with self.connection:
            self.connection.execute(
                "INSERT INTO subjects(id,jurisdiction,created_at) VALUES(?,?,?)",
                (subject_id, jurisdiction, at),
            )
            self.connection.execute(
                "INSERT INTO subject_names(subject_id,name,valid_from) VALUES(?,?,?)",
                (subject_id, name, at),
            )
            write(self.connection, at, actor, "subject.register", subject_id,
                  {"name": name, "jurisdiction": jurisdiction})

    def get(self, subject_id):
        row = self.connection.execute("SELECT * FROM subjects WHERE id=?", (subject_id,)).fetchone()
        if row is None:
            raise KeyError(subject_id)
        return dict(row)

    def require_active(self, subject_id):
        row = self.get(subject_id)
        if row["status"] != "active":
            raise ValueError("景区主体已停用：" + subject_id)
        return row

    def rename(self, event_id, subject_id, new_name, at, actor, reason):
        self.require_active(subject_id)
        current = self.connection.execute(
            "SELECT name FROM subject_names WHERE subject_id=? AND valid_to IS NULL",
            (subject_id,),
        ).fetchone()
        if current and current["name"] == new_name:
            raise ValueError("新名称与现用名称相同")
        with self.connection:
            self.connection.execute(
                "UPDATE subject_names SET valid_to=? WHERE subject_id=? AND valid_to IS NULL",
                (at, subject_id),
            )
            self.connection.execute(
                "INSERT INTO subject_names(subject_id,name,valid_from) VALUES(?,?,?)",
                (subject_id, new_name, at),
            )
            self._record_event(event_id, "rename", at, actor, reason, [subject_id], [subject_id])
            write(self.connection, at, actor, "subject.rename", subject_id,
                  {"from": current["name"] if current else None, "to": new_name, "event": event_id})

    def merge(self, event_id, into, from_subjects, at, actor, reason):
        from_subjects = list(dict.fromkeys(from_subjects))
        if not from_subjects or into in from_subjects:
            raise ValueError("合并对象无效")
        self.require_active(into)
        for subject in from_subjects:
            self.require_active(subject)
        with self.connection:
            self._record_event(event_id, "merge", at, actor, reason, from_subjects, [into])
            for subject in from_subjects:
                self.connection.execute("UPDATE subjects SET status='merged' WHERE id=?", (subject,))
                moved = self._move_attributions(
                    subject,
                    {row["asset_id"]: into for row in self._active_attributions(subject)},
                    event_id, at, actor,
                )
                write(self.connection, at, actor, "subject.merge", event_id,
                      {"into": into, "from": subject, "reason": reason, "reattributed": moved})

    def split(self, event_id, from_subject, new_subjects, assignments, at, actor, reason):
        self.require_active(from_subject)
        if not new_subjects:
            raise ValueError("拆分缺少新主体")
        unknown = set(assignments.values()) - set(new_subjects)
        if unknown:
            raise ValueError("拆分去向不是新主体")
        current = {row["asset_id"] for row in self._active_attributions(from_subject)}
        if set(assignments) != current:
            raise ValueError("拆分方案未覆盖全部在册材料")
        jurisdiction = self.get(from_subject)["jurisdiction"]
        with self.connection:
            self._record_event(event_id, "split", at, actor, reason, [from_subject], list(new_subjects))
            self.connection.execute("UPDATE subjects SET status='split' WHERE id=?", (from_subject,))
            for subject_id, name in new_subjects.items():
                self.connection.execute(
                    "INSERT INTO subjects(id,jurisdiction,created_at) VALUES(?,?,?)",
                    (subject_id, jurisdiction, at),
                )
                self.connection.execute(
                    "INSERT INTO subject_names(subject_id,name,valid_from) VALUES(?,?,?)",
                    (subject_id, name, at),
                )
            moved = self._move_attributions(from_subject, assignments, event_id, at, actor)
            write(self.connection, at, actor, "subject.split", event_id,
                  {"from": from_subject, "into": list(new_subjects), "reason": reason, "reattributed": moved})

    def lineage(self, subject_id):
        subject = self.get(subject_id)
        names = [dict(row) for row in self.connection.execute(
            "SELECT * FROM subject_names WHERE subject_id=? ORDER BY valid_from", (subject_id,))]
        events = []
        for row in self.connection.execute("SELECT * FROM identity_events ORDER BY at,id"):
            from_subjects = json.loads(row["from_subjects"])
            to_subjects = json.loads(row["to_subjects"])
            if subject_id in from_subjects or subject_id in to_subjects:
                events.append({
                    "id": row["id"], "kind": row["kind"], "at": row["at"],
                    "actor": row["actor"], "reason": row["reason"],
                    "from_subjects": from_subjects, "to_subjects": to_subjects,
                })
        return {"subject": subject, "names": names, "events": events}

    def known_names(self, subject_id):
        self.get(subject_id)
        events = list(self.connection.execute("SELECT from_subjects,to_subjects FROM identity_events"))
        seen, queue, names = set(), [subject_id], set()
        while queue:
            current = queue.pop()
            if current in seen:
                continue
            seen.add(current)
            for row in self.connection.execute("SELECT name FROM subject_names WHERE subject_id=?", (current,)):
                names.add(row["name"])
            for event in events:
                from_subjects = json.loads(event["from_subjects"])
                to_subjects = json.loads(event["to_subjects"])
                if current in from_subjects:
                    queue.extend(to_subjects)
                if current in to_subjects:
                    queue.extend(from_subjects)
        return sorted(names)

    def _record_event(self, event_id, kind, at, actor, reason, from_subjects, to_subjects):
        self.connection.execute(
            "INSERT INTO identity_events(id,kind,at,actor,reason,from_subjects,to_subjects) VALUES(?,?,?,?,?,?,?)",
            (event_id, kind, at, actor, reason, json.dumps(from_subjects), json.dumps(to_subjects)),
        )

    def _active_attributions(self, subject_id):
        return self.connection.execute(
            "SELECT * FROM attributions WHERE subject_id=? AND state='active'", (subject_id,),
        ).fetchall()

    def _move_attributions(self, from_subject, assignments, event_id, at, actor):
        moved = []
        for row in self._active_attributions(from_subject):
            target = assignments[row["asset_id"]]
            new_id = event_id + "/" + row["id"]
            self.connection.execute("UPDATE attributions SET state='superseded' WHERE id=?", (row["id"],))
            self.connection.execute(
                "INSERT INTO attributions(id,asset_id,subject_id,claimed_name,basis,note,state,created_at,created_by,supersedes,event_id)"
                " VALUES(?,?,?,?,?,?,'active',?,?,?,?)",
                (new_id, row["asset_id"], target, row["claimed_name"], row["basis"],
                 row["note"], at, actor, row["id"], event_id),
            )
            write(self.connection, at, actor, "attribution.reassign", new_id,
                  {"asset": row["asset_id"], "from": from_subject, "to": target, "event": event_id})
            moved.append({"asset": row["asset_id"], "to": target, "attribution": new_id})
        return moved

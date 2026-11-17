from .audit import write
from .attribution import Attributions


class Responses:
    """景区答复与暗访观察的对应关系；答复与观察各自保持来源与版本，对应关系逐条留痕。"""

    def __init__(self, connection):
        self.connection = connection
        self.attributions = Attributions(connection)

    def link(self, link_id, response_asset_id, observation_asset_id, at, actor):
        if response_asset_id == observation_asset_id:
            raise ValueError("答复与观察不能是同一份材料")
        for asset_id in (response_asset_id, observation_asset_id):
            row = self.connection.execute(
                "SELECT id FROM assets WHERE id=? AND state='active'", (asset_id,),
            ).fetchone()
            if row is None:
                raise KeyError(asset_id)
        if self.connection.execute(
            "SELECT 1 FROM response_links WHERE response_asset_id=?", (observation_asset_id,),
        ).fetchone():
            raise ValueError("该材料已登记为答复，不能作为观察")
        if self.connection.execute(
            "SELECT 1 FROM response_links WHERE response_asset_id=? AND observation_asset_id=?",
            (response_asset_id, observation_asset_id),
        ).fetchone():
            raise ValueError("答复与观察的对应已存在")
        observation = self.attributions.current(observation_asset_id)
        response = self.attributions.current(response_asset_id)
        if observation is None or response is None:
            raise ValueError("观察与答复均需先完成景区归属")
        if observation["subject_id"] != response["subject_id"]:
            raise ValueError("答复与观察归属的景区主体不一致")
        with self.connection:
            self.connection.execute(
                "INSERT INTO response_links(id,observation_asset_id,response_asset_id,created_at,created_by) VALUES(?,?,?,?,?)",
                (link_id, observation_asset_id, response_asset_id, at, actor),
            )
            write(self.connection, at, actor, "response.link", link_id,
                  {"observation": observation_asset_id, "response": response_asset_id,
                   "subject": observation["subject_id"]})

    def for_observation(self, observation_asset_id):
        rows = self.connection.execute(
            "SELECT l.id AS link_id,l.created_at,l.created_by,a.id AS asset_id,a.digest,a.received_at,"
            "s.id AS source_id,s.owner FROM response_links l "
            "JOIN assets a ON a.id=l.response_asset_id JOIN sources s ON s.id=a.source_id "
            "WHERE l.observation_asset_id=? ORDER BY l.created_at,l.id",
            (observation_asset_id,),
        ).fetchall()
        return [dict(row) for row in rows]

    def answers(self, response_asset_id):
        rows = self.connection.execute(
            "SELECT l.id AS link_id,l.observation_asset_id,l.created_at,l.created_by "
            "FROM response_links l WHERE l.response_asset_id=? ORDER BY l.created_at,l.id",
            (response_asset_id,),
        ).fetchall()
        return [dict(row) for row in rows]

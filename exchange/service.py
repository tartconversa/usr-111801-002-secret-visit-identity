from .attribution import Attributions
from .audit import history
from .catalog import Catalog
from .conclusions import Conclusions
from .db import connect
from .delivery import Delivery
from .disputes import Disputes
from .grants import Grants
from .identity import Identities
from .policy import Policies
from .products import Products
from .responses import Responses


class Exchange:
    def __init__(self, database):
        self.connection = connect(database)
        self.catalog = Catalog(self.connection)
        self.grants = Grants(self.connection)
        self.policies = Policies(self.connection)
        self.products = Products(self.connection)
        self.delivery = Delivery(self.connection)
        self.identity = Identities(self.connection)
        self.attributions = Attributions(self.connection)
        self.responses = Responses(self.connection)
        self.disputes = Disputes(self.connection)
        self.conclusions = Conclusions(self.connection)

    def history(self, subject):
        return history(self.connection, subject)

    def close(self):
        self.connection.close()

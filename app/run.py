"""A Twisted rtstats ingest + server


"""
import json
import os
import datetime

from twisted.internet import reactor
from twisted.enterprise import adbapi
from applib import ldmbridge

# This is a hack that prevents a strange exception with datetime and threading
datetime.datetime.strptime("2017", "%Y")


def ready(_, dbpool):
    """run the server components"""
    protocol = ldmbridge.RTStatsIngestor()
    protocol.dbpool = dbpool
    ldmbridge.LDMProductFactory(protocol)


def load_dbtables(cursor):
    pass


if __name__ == "__main__":
    fn = "%s/settings.json" % (
        os.path.join(os.path.dirname(__file__), "../config"),
    )
    config = json.load(open(fn))
    dbopts = config["databaserw"]
    dbpool = adbapi.ConnectionPool(
        "psycopg2",
        database=dbopts["name"],
        cp_reconnect=True,
        cp_max=20,
        host=dbopts["host"],
        user=dbopts["user"],
        password=dbopts["password"],
    )

    df = dbpool.runInteraction(load_dbtables)
    df.addCallback(ready, dbpool)

    reactor.run()

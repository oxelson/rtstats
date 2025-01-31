#!/usr/bin/env python
"""Emit JSON of hosts

    /services/hosts.geojson

This service caches for 1 hour before refreshing.
"""
import json
import datetime

import memcache
from paste.request import parse_formvars
import rtstats_util as util


def run(feedtype):
    """Generate geojson for this feedtype"""
    pgconn = util.get_dbconn()
    cursor = pgconn.cursor()
    sts = datetime.datetime.utcnow()
    flimiter = ""
    if feedtype is not None:
        flimiter = (" WHERE p.feedtype_id = get_ldm_feedtype_id('%s') ") % (
            feedtype,
        )
    cursor.execute(
        """
    WITH data as (
        SELECT distinct feedtype_path_id, version_id from ldm_rtstats_hourly
        WHERE valid > now() - '24 hours'::interval),
    agg1 as (
        SELECT distinct p.node_host_id, d.version_id from
        data d JOIN ldm_feedtype_paths p on (d.feedtype_path_id = p.id)
        """
        + flimiter
        + """)
    SELECT ST_asGeoJson(h.geom, 2), h.hostname, v.version
    from agg1 a1, ldm_versions v, ldm_hostnames h
    WHERE a1.node_host_id = h.id and v.id = a1.version_id
    ORDER by hostname ASC
    """
    )
    utcnow = datetime.datetime.utcnow()
    res = {
        "type": "FeatureCollection",
        "crs": {
            "type": "EPSG",
            "properties": {"code": 4326, "coordinate_order": [1, 0]},
        },
        "features": [],
        "query_time[secs]": (utcnow - sts).total_seconds(),
        "generation_time": utcnow.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "count": cursor.rowcount,
    }
    for row in cursor:
        res["features"].append(
            dict(
                type="Feature",
                id=row[1],
                properties=dict(hostname=row[1], ldmversion=row[2]),
                geometry=(None if row[0] is None else json.loads(row[0])),
            )
        )

    return json.dumps(res)


def application(environ, start_response):
    """Answer request."""
    fields = parse_formvars(environ)

    cb = fields.get("callback", None)
    feedtype = fields.get("feedtype", None)
    mckey = "/services/hosts.geojson?feedtype=%s" % (feedtype,)
    mc = memcache.Client(["localhost:11211"], debug=0)
    res = mc.get(mckey)
    if not res:
        res = run(feedtype)
        mc.set(mckey, res, 3600)
    if cb is None:
        data = res
    else:
        data = "%s(%s)" % (cb, res)

    headers = [("Content-type", "application/vnd.geo+json")]
    start_response("200 OK", headers)
    return [data.encode("ascii")]

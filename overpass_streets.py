import overpy
from geographiclib.geodesic import Geodesic
from google_key import KEY
import requests

def get_bearing(lat1, lat2, long1, long2):
    obj = Geodesic.WGS84.Inverse(lat1, long1, lat2, long2)
    brng = obj['azi1']
    length = obj['s12']
    return brng, length

api = overpy.Overpass()

query="""
area["ISO3166-2"="DE-BE"][admin_level=4];
(way[highway="residential"](area);
 way[highway="living_street"](area);
 way[highway="tertiary"](area);
 way[highway="service"](area);
 way[highway="secondary"](area);
);
out;
"""

result = api.query(query)

sliced_ways = result.ways[0:3]

for way in sliced_ways:
    print ("Way " + str(way.id))
    nodes = way.get_nodes(resolve_missing=True)
    for segment in range(0,len(nodes)-1):
        print ("\tSegment " + str(segment))
        start = dict()
        end = dict()
        start['lat'] = nodes[segment].lat
        start['lon'] = nodes[segment].lon
        end['lat'] = nodes[segment+1].lat
        end['lon'] = nodes[segment+1].lon
        print ("\t\tstart:" + str(start['lat']) + ", " + str(start['lon']))
        print ("\t\tend:" + str(end['lat']) + ", " + str(end['lon']))
        bearing, length = get_bearing(start['lat'], end['lat'], start['lon'], end['lon'])
        print("\t\tBearing: " + str(bearing))
        left = bearing - 90
        right = bearing + 90
        mid = Geodesic.WGS84.Direct(start['lat'], start['lon'], bearing, length/2)
        print("\t\tMid: " + str(mid['lat2']) + ", " + str(mid['lon2']))
        url_base = "https://maps.googleapis.com/maps/api/streetview?location=" + \
                str(mid['lat2']) + "," + str(mid['lon2']) + \
                "&size=640x480&key=" + KEY + "&fov=90&" + \
                "heading="
        url_left = url_base + str(left)
        url_right = url_base + str(right)
        print(url_left)
        print(url_right)

        r = requests.get(url_left)
        open(str(way.id) + "-" + str(segment) + "-left" + str(".jpeg"), 'wb').write(r.content)
        r = requests.get(url_right)
        open(str(way.id) + "-" + str(segment) + "-right" + str(".jpeg"), 'wb').write(r.content)


import overpy
from geographiclib.geodesic import Geodesic
from google_key import KEY
import requests
import os
import json
import argparse

verbose = False
debug = False


def verbose_info(*args, **kwargs):
    if verbose:
        print(*args, **kwargs)
    else:
        pass


def get_geoline_props(lat1, lat2, long1, long2):
    geoline = Geodesic.WGS84.Inverse(lat1, long1, lat2, long2)
    azimuth = geoline['azi1']
    length = geoline['s12']
    return azimuth, length


def streetview_available(lat, lon):
    google_meta_api_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    meta_request_params = {
        "location": f"{lat:f},{lon:f}",
        "key": KEY,
    }
    r = requests.get(google_meta_api_url, params=meta_request_params)
    verbose_info(f"\t\tStreet View meta request: {r.request.url}")
    image_meta = json.loads(r.content)
    if image_meta['status'] != "OK":
        return False

    return True


def grab_streetview(lat, lon, heading, download_dir, filename):
    google_api_url = "https://maps.googleapis.com/maps/api/streetview"
    view_request_params = {
        "location": f"{lat:f}, {lon:f}",
        "size": "640x480",
        "key": KEY,
        "fov": "90",
        "heading": f"{heading:f}"
    }
    r = requests.get(google_api_url, params=view_request_params)
    verbose_info(f"\t\tStreet View request: {r.request.url}")
    full_file = os.path.join(download_dir, filename)
    verbose_info(f"\t\t\tFile to save: {full_file}")
    open(full_file, 'wb').write(r.content)


def main():
    argparser = argparse.ArgumentParser(description="The script grabs Google Street View for a city.")
    argparser.add_argument("--debug", action="store_true", help="run in debug mode")
    argparser.add_argument("--verbose", action="store_true", help="show info about all the processed points")
    argparser.add_argument("--city", required=True, help="the city for which street views shall be downloaded. "
                                                         "The name should be written in its original language.")
    args = argparser.parse_args()
    global verbose, debug
    verbose = args.verbose
    debug = args.debug

    verbose_info(f"The city: {args.city}")

    query = f"""
    area[name="{args.city}"];
    (way["highway"](area); >;);
    out skel;
    """
    api = overpy.Overpass()
    print("Requesting the OSM data... ", end="", flush=True)
    result = api.query(query)
    print("done!")

    ways = result.ways
    if debug:
        ways = ways[0:1]

    images_dir = "images"
    if not os.path.isdir(images_dir):
       os.mkdir(images_dir)

    for way in ways:
        verbose_info(f"Way {way.id:d}")
        nodes = way.get_nodes()
        for segment in range(0, len(nodes)-1):
            verbose_info(f"\tSegment {segment:d}")
            node_start = nodes[segment]
            node_end = nodes[segment+1]
            verbose_info(f"\t\tstart: {node_start.lat:f}, {node_start.lon:f}")
            verbose_info(f"\t\tend: {node_end.lat:f}, {node_end.lon:f}")
            azimuth, length = get_geoline_props(node_start.lat, node_end.lat, node_start.lon, node_end.lon)
            verbose_info(f"\t\tazimuth: {azimuth:f}")
            verbose_info(f"\t\tlength: {length:f}")

            # Count the mid point of the way. Later - switch to a loop for each 10 meters.
            geodesic_mid = Geodesic.WGS84.Direct(node_start.lat, node_start.lon, azimuth, length/2)
            mid_lat = geodesic_mid['lat2']
            mid_lon = geodesic_mid['lon2']
            verbose_info(f"\t\tmid: {mid_lat:f}, {mid_lon:f}")

            if not streetview_available(mid_lat, mid_lon):
                continue

            heading_left = azimuth - 90
            filename = f"{way.id:d}-{segment:d}-left.jpeg"
            grab_streetview(mid_lat, mid_lon, heading_left, images_dir, filename)

            heading_right = azimuth + 90
            filename = f"{way.id:d}-{segment:d}-right.jpeg"
            grab_streetview(mid_lat, mid_lon, heading_right, images_dir, filename)


main()

import overpy
from geographiclib.geodesic import Geodesic
from google_key import KEY
import requests
import requests.compat
import os
import json
import argparse
import sys

verbose = False
debug = False
count_only = False


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
    verbose_info(f"\t\t\t\tStreet View meta request: {r.request.url}")
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
    verbose_info(f"\t\t\t\tStreet View request: {r.request.url}")
    full_file = os.path.join(download_dir, filename)
    verbose_info(f"\t\t\t\tFile to save: {full_file}")
    open(full_file, 'wb').write(r.content)


def grab_streetviews(lat, lon, forward_heading, images_dir, id, way_id):
    heading_left = forward_heading - 90
    filename = f"{id:d}-{way_id:d}-left.jpeg"
    grab_streetview(lat, lon, heading_left, images_dir, filename)

    heading_right = forward_heading + 90
    filename = f"{id:d}-{way_id:d}-right.jpeg"
    grab_streetview(lat, lon, heading_right, images_dir, filename)


def create_download_dir(city):
    images_dir = os.path.join("images", city)
    if not os.path.isdir(images_dir):
        os.makedirs(images_dir)
    return images_dir


def main():
    argparser = argparse.ArgumentParser(description="The script grabs Google Street View for a city.")
    argparser.add_argument("--debug", action="store_true", help="run in debug mode")
    argparser.add_argument("--verbose", action="store_true", help="show info about all the processed points")
    argparser.add_argument("--city", required=True, help="the city for which street views shall be downloaded. "
                                                         "The name should be written in its original language.")
    argparser.add_argument("--count-only", action="store_true",
                           help="do not download the images, only count their amount and calculate approximate total "
                                "size")
    argparser.add_argument("--alternative-server", default="https://lz4.overpass-api.de/api/interpreter",
                           help="alternative server of Overpass API if the main one refuses to handle. Must start with "
                                "\"http(s)\" and contain the right URL (usually, \"api/interpreter\")")
    args = argparser.parse_args()
    global verbose, debug, count_only
    verbose = args.verbose
    debug = args.debug
    count_only = args.count_only

    if count_only:
        print(f"Calculate approximate total size of the data to be downloaded for {args.city}")
    else:
        print(f"Download the street views for {args.city}")

    query = f"""
    area[name="{args.city}"];
    (way["highway"](area); >;);
    out skel;
    """
    verbose_info(query)

    api = overpy.Overpass()
    print("Requesting the OSM data... ", end="", flush=True)
    try:
        result = api.query(query)
    except overpy.exception.OverpassTooManyRequests as e:
        verbose_info("failed!")
        verbose_info(e)
        verbose_info(f"The main server refused to handle, try {args.alternative_server}")
        api = overpy.Overpass(args.alternative_server.encode())
        verbose_info("Requesting the OSM data... ", end="", flush=True)
        try:
            result = api.query(query)
        except TypeError as e:
            print("failed!")
            print(e)
            print(f"Failed to connect to the alternative server ({args.alternative_server}). Make sure it's correct ("
                  f"read help for the script for the details).")
            sys.exit(1)
        except overpy.exception.OverpassTooManyRequests as e:
            print("failed!")
            print(e)
            sys.exit(1)
    except Exception as e:
        print("failed!")
        print(e)
        raise

    print("done!")

    ways = result.ways
    if debug:
        ways = ways[0:1]

    images_dir = ""
    if not count_only:
        images_dir = create_download_dir(args.city)

    streeviews_count = 0

    if count_only:
        print("Counting... ", end="", flush=True)
    else:
        print("Downloading... ", end="", flush=True)

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

            verbose_info("\t\tStepping the segment...")
            offset = 5
            while offset < length:
                shifted_geonode = Geodesic.WGS84.Direct(node_start.lat, node_start.lon, azimuth, offset)
                curr_lat = shifted_geonode['lat2']
                curr_lon = shifted_geonode['lon2']
                verbose_info(f"\t\t\tHave passed {offset:d} meters from the start of the street, "
                             f"came into {curr_lat:f},{curr_lon:f}")
                offset += 10
                if not streetview_available(curr_lat, curr_lon):
                    continue
                streeviews_count += 1
                if not count_only:
                    grab_streetviews(curr_lat, curr_lon, azimuth, images_dir, streeviews_count, way.id)

    if count_only:
        print(f"Total images to download: {streeviews_count:d}, the size will be ~ {streeviews_count*0.05859*2:0.2f} Mb")


main()

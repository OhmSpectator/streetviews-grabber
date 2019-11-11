from random import randrange

import overpy
from geographiclib.geodesic import Geodesic
from google_key import KEY
import requests
import requests.compat
import os
import json
import argparse
import sys
import matplotlib.pyplot as plt
import math

verbose = False
debug = False
count_only = False
plot = False


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
    if image_meta['copyright'] != "© Google":
        return False
    return True


def grab_streetview(lat, lon, heading, fov, download_dir, filename):
    google_api_url = "https://maps.googleapis.com/maps/api/streetview"
    view_request_params = {
        "location": f"{lat:f}, {lon:f}",
        "size": "640x480",
        "key": KEY,
        "fov": fov,
        "heading": f"{heading:f}"
    }
    r = requests.get(google_api_url, params=view_request_params)
    verbose_info(f"\t\t\t\tStreet View request: {r.request.url}")
    full_file = os.path.join(download_dir, filename)
    verbose_info(f"\t\t\t\tFile to save: {full_file}")
    open(full_file, 'wb').write(r.content)
    if debug and plot:
        v = math.cos(math.radians(heading))
        u = math.sin(math.radians(heading))
        plt.quiver(lon, lat, u, v)


def look_around(lat, lon, forward_heading, fov, images_dir, id, way_id):
    heading_left = forward_heading - 90
    filename = f"{id:d}-{way_id:d}-left.jpeg"
    grab_streetview(lat, lon, heading_left, fov, images_dir, filename)

    heading_right = forward_heading + 90
    filename = f"{id:d}-{way_id:d}-right.jpeg"
    grab_streetview(lat, lon, heading_right, fov, images_dir, filename)


def create_download_dir(city):
    images_dir = os.path.join("images", city)
    if not os.path.isdir(images_dir):
        os.makedirs(images_dir)
    return images_dir


def parse_args():
    argparser = argparse.ArgumentParser(description="The script grabs Google Street View for a city.")
    argparser.add_argument("--debug", action="store_true", help="run in debug mode")
    argparser.add_argument("--verbose", action="store_true", help="show info about all the processed points")
    argparser.add_argument("city", help="the city for which street views shall be downloaded. The name should be "
                                        "written in its original language (e.g. Москва, not Moscow).")
    argparser.add_argument("--count-only", action="store_true",
                           help="do not download the images, only count their amount and calculate approximate total "
                                "size")
    argparser.add_argument("--alternative-server", default="https://lz4.overpass-api.de/api/interpreter",
                           help="alternative server of Overpass API if the main one refuses to handle. Must start with "
                                "\"http(s)\" and contain the right URL (usually, \"api/interpreter\")")
    argparser.add_argument("--fov", default=50, type=int, choices=range(20, 121), metavar="[20-120]",
                           help="field of view of the street views. Less the value, more zoomed the images. Must be in "
                                "a range between 20 and 120. Default is 50.")
    argparser.add_argument("--rand", action="store_true", help="in the case of debug run, randomize the route to be "
                                                               "handled (by default, the first one is taken)")
    argparser.add_argument("--visualize", action="store_true", help="visualize the walking process: show all the points "
                                                                    "of interest and the vectors of the available looks")
    args = argparser.parse_args()
    global verbose, debug, count_only, plot
    verbose = args.verbose
    debug = args.debug
    count_only = args.count_only
    plot = args.visualize
    return args


def get_osm_data(city, alternative_server):
    query = f"""
    area[name="{city}"];
    (way["highway"](area); >;);
    out skel;
    """
    verbose_info("Overpass API queue:")
    verbose_info(query)
    api = overpy.Overpass()
    print("Requesting the OSM data... ", end="", flush=True)
    try:
        result = api.query(query)
    except overpy.exception.OverpassTooManyRequests as e:
        verbose_info("failed!")
        verbose_info(e)
        verbose_info(f"The main server refused to handle, try {alternative_server}")
        api = overpy.Overpass(alternative_server.encode())
        verbose_info("Requesting the OSM data... ", end="", flush=True)
        try:
            result = api.query(query)
        except TypeError as e:
            print("failed!")
            print(e)
            print(f"Failed to connect to the alternative server ({alternative_server}). Make sure it's correct ("
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
    return result


def walk_the_routes(fov, images_dir, routes):
    street_views_count = 0
    for route in routes:
        verbose_info(f"Route {route.id:d}")
        milestones = route.get_nodes()
        for segment in range(0, len(milestones) - 1):
            verbose_info(f"\tSegment {segment:d}")
            starting_milestone = milestones[segment]
            ending_milestone = milestones[segment + 1]
            if debug and plot:
                plt.plot([starting_milestone.lon, ending_milestone.lon], [starting_milestone.lat, ending_milestone.lat], 'or-')
            verbose_info(f"\t\tstart: {starting_milestone.lat:f}, {starting_milestone.lon:f}")
            verbose_info(f"\t\tend: {ending_milestone.lat:f}, {ending_milestone.lon:f}")
            azimuth, length = get_geoline_props(starting_milestone.lat, ending_milestone.lat, starting_milestone.lon, ending_milestone.lon)
            verbose_info(f"\t\tazimuth: {azimuth:f}")
            verbose_info(f"\t\tlength: {length:f}")
            verbose_info("\t\tStepping the segment...")
            street_views_count += walk_segment(starting_milestone, length, azimuth, fov, images_dir, route.id)
    if debug and plot:
        plt.title('The Segments')
        plt.xlabel('Longitude')
        plt.ylabel('Latitude')
        plt.axis('equal')
        plt.show()
    return street_views_count


def walk_segment(start_point, length, azimuth, fov, images_dir, id):
    count = 0
    offset = 5
    while offset < length:
        shifted_geonode = Geodesic.WGS84.Direct(start_point.lat, start_point.lon, azimuth, offset)
        curr_lat = shifted_geonode['lat2']
        curr_lon = shifted_geonode['lon2']
        verbose_info(f"\t\t\tHave passed {offset:d} meters from the start of the street, "
                     f"came into {curr_lat:f},{curr_lon:f}")
        if debug and plot:
            plt.plot([curr_lon], [curr_lat], 'go')
        offset += 10
        if not streetview_available(curr_lat, curr_lon):
            continue
        count += 1
        if not count_only:
            assert images_dir
            look_around(curr_lat, curr_lon, azimuth, fov, images_dir, count, id)
    return count


def main():
    args = parse_args()

    if count_only:
        print(f"Calculate approximate total size of the data to be downloaded for {args.city}")
    else:
        print(f"Download the street views for {args.city}")

    osm_data = get_osm_data(args.city, args.alternative_server)

    routes = osm_data.ways
    if debug:
        test_route = 0
        if args.rand:
            test_route = randrange(0, len(routes)-1, 1)
        verbose_info(f"Handle route #{test_route:d}")
        routes = routes[test_route:test_route + 1]

    images_dir = None
    if not count_only:
        images_dir = create_download_dir(args.city)

    if count_only:
        print("Counting... ", end="", flush=True)
    else:
        print("Downloading... ", end="", flush=True)

    street_views_count = walk_the_routes(args.fov, images_dir, routes)

    if count_only:
        print(f"Total images to download: {street_views_count:d}, the size will be ~ {street_views_count*0.05859*2:0.2f} Mb")


main()

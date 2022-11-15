import argparse
import concurrent.futures
import json
import math
import os
import sys
from random import randrange

import matplotlib.pyplot as plt
import overpy
import requests
from geographiclib.geodesic import Geodesic
from matplotlib import patches

verbose = False
debug = False
download = False
plot = False


def verbose_info(*args, **kwargs):
    if verbose:
        print(*args, **kwargs)
    else:
        pass


def google_api_key():
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        print("No GOOGLE_API_KEY env variable provided...")
        sys.exit(1)
    return api_key


KEY = google_api_key()

def get_geoline_props(lat1, lat2, long1, long2):
    geoline = Geodesic.WGS84.Inverse(lat1, long1, lat2, long2)
    azimuth = geoline['azi1']
    length = geoline['s12']
    return azimuth, length


# TODO Make the session logic a dedicated class
sessions = {}


def get_session(session_type):
    if sessions.get(session_type):
        return sessions.get(session_type)
    session = requests.session()
    sessions[session_type] = session
    return session


def streetview_available(lat, lon, radius):
    session = get_session("meta")
    google_meta_api_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    meta_request_params = {
        "location": f"{lat:f},{lon:f}",
        "key": KEY,
        "radius": radius
    }
    r = session.get(google_meta_api_url, params=meta_request_params)
    verbose_info(f"\t\t\t\tStreet View meta request: {r.request.url}")
    image_meta = json.loads(r.content)
    if image_meta['status'] != "OK":
        return None
    if image_meta['copyright'] != "© Google":
        return None
    if debug and plot:
        plt.plot(image_meta['location']['lng'], image_meta['location']['lat'], 'b*')
    return image_meta['pano_id']


def grab_streetview(lat, lon, heading, fov, radius, download_dir, filename):
    session = get_session("streetview")
    google_api_url = "https://maps.googleapis.com/maps/api/streetview"
    view_request_params = {
        "location": f"{lat:f}, {lon:f}",
        "size": "640x480",
        "key": KEY,
        "fov": fov,
        "heading": f"{heading:f}",
        "radius": radius
    }
    r = session.get(google_api_url, params=view_request_params)
    verbose_info(f"\t\t\t\tStreet View request: {r.request.url}")
    full_file = os.path.join(download_dir, filename)
    verbose_info(f"\t\t\t\tFile to save: {full_file}")
    open(full_file, 'wb').write(r.content)
    if debug and plot:
        v = math.cos(math.radians(heading))
        u = math.sin(math.radians(heading))
        meters_in_lon = Geodesic.WGS84.Direct(lat, lon, 90, 1)['lon2'] - lon
        meters_in_lat = Geodesic.WGS84.Direct(lat, lon, 0, 1)['lat2'] - lat
        ratio = meters_in_lat / meters_in_lon
        plt.quiver(lon, lat, u * ratio, v)


def look_around(lat, lon, forward_heading, fov, radius, images_dir, uniq_id):
    heading_left = forward_heading - 90
    filename = f"{uniq_id}-left.jpeg"
    grab_streetview(lat, lon, heading_left, fov, radius, images_dir, filename)

    heading_right = forward_heading + 90
    filename = f"{uniq_id}-right.jpeg"
    grab_streetview(lat, lon, heading_right, fov, radius, images_dir, filename)


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
    argparser.add_argument("--download", action="store_true",
                           help="download the images. If not set, only count amount and calculate approximate total "
                                "size")
    argparser.add_argument("--alternative-server", default="https://lz4.overpass-api.de/api/interpreter",
                           help="alternative server of Overpass API if the main one refuses to handle. Must start with "
                                "\"http(s)\" and contain the right URL (usually, \"api/interpreter\")")
    argparser.add_argument("--fov", default=50, type=int, choices=range(20, 121), metavar="[20-120]",
                           help="field of view of the street views. Less the value, more zoomed the images. Must be in "
                                "a range between 20 and 120. Default is 50.")
    argparser.add_argument("--step", default=10, type=float, help="a step in meters with which the script walks through "
                                                                "routes, i.e., probes for a street view availability. "
                                                                "Also it effect the radius of the search for a street "
                                                                "view. The radius is a half of a step. Default is 10.")
    argparser.add_argument("--rand", action="store_true", help="in the case of debug run, randomize the route to be "
                                                               "handled (by default, the first one is taken)")
    argparser.add_argument("--visualize", action="store_true", help="visualize the walking process: show all the points "
                                                                    "of interest and the vectors of the available looks")
    args = argparser.parse_args()
    global verbose, debug, download, plot
    verbose = args.verbose
    debug = args.debug
    download = args.download
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


def handle_route(fov, images_dir, route, step):
    verbose_info(f"Route {route.id:d}")
    milestones = route.get_nodes()
    panos_in_route = 0
    for segment in range(0, len(milestones) - 1):
        verbose_info(f"\tSegment {segment:d}")
        starting_milestone = milestones[segment]
        ending_milestone = milestones[segment + 1]
        if debug and plot:
            plt.plot([starting_milestone.lon, ending_milestone.lon], [starting_milestone.lat, ending_milestone.lat],
                     'or-')
        verbose_info(f"\t\tstart: {starting_milestone.lat:f}, {starting_milestone.lon:f}")
        verbose_info(f"\t\tend: {ending_milestone.lat:f}, {ending_milestone.lon:f}")
        azimuth, length = get_geoline_props(starting_milestone.lat, ending_milestone.lat, starting_milestone.lon,
                                            ending_milestone.lon)
        verbose_info(f"\t\tazimuth: {azimuth:f}")
        verbose_info(f"\t\tlength: {length:f}")
        verbose_info("\t\tStepping the segment...")
        panos_in_segment = walk_segment(starting_milestone, length, azimuth, fov, step, images_dir)
        panos_in_route += panos_in_segment
    return panos_in_route


def walk_the_routes(fov, step, images_dir, routes):
    panos = 0
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(handle_route, fov, images_dir, route, step) for route in routes}
        for future in concurrent.futures.as_completed(futures):
            panos += future.result()
    if debug and plot:
        plt.title('The Segments')
        plt.xlabel('Longitude')
        plt.ylabel('Latitude')
        plt.axis('equal')
        plt.show()
    return panos


def walk_segment(start_point, length, azimuth, fov, step, images_dir):
    panos_in_segment = 0
    search_radius = math.ceil(step / 2)
    debug_search_radius = step / 2
    verbose_info(f"\t\tStep: {step:.02f}")
    verbose_info(f"\t\tSearch radius: {search_radius:.02f}")
    offset = search_radius
    plt.plot(start_point.lon, start_point.lat, 'g^')
    while offset + search_radius < length:
        shifted_geonode = Geodesic.WGS84.Direct(start_point.lat, start_point.lon, azimuth, offset)
        curr_lat = shifted_geonode['lat2']
        curr_lon = shifted_geonode['lon2']
        verbose_info(f"\t\t\tHave passed {offset:.02f} meters from the start of the street, "
                     f"came into {curr_lat:f},{curr_lon:f}")
        if debug and plot:
            plt.plot([curr_lon], [curr_lat], 'go')
            geo_radius_lon = Geodesic.WGS84.Direct(curr_lat, curr_lon, 90, search_radius)['lon2'] - curr_lon
            geo_radius_lat = Geodesic.WGS84.Direct(curr_lat, curr_lon, 0, search_radius)['lat2'] - curr_lat
            search_area = patches.Ellipse((curr_lon, curr_lat), geo_radius_lon * 2, geo_radius_lat * 2, fill=False, color='b')
            plt.gca().add_patch(search_area)

            debug_geo_radius_lon = Geodesic.WGS84.Direct(curr_lat, curr_lon, 90, debug_search_radius)['lon2'] - curr_lon
            debug_geo_radius_lat = Geodesic.WGS84.Direct(curr_lat, curr_lon, 0, debug_search_radius)['lat2'] - curr_lat
            search_area = patches.Ellipse((curr_lon, curr_lat), debug_geo_radius_lon * 2, debug_geo_radius_lat * 2, fill=False, color='r')
            plt.gca().add_patch(search_area)

        offset += step
        pano_id = streetview_available(curr_lat, curr_lon, search_radius)
        if not pano_id:
            continue
        panos_in_segment += 1
        if download:
            assert images_dir
            look_around(curr_lat, curr_lon, azimuth, fov, search_radius, images_dir, pano_id)
    return panos_in_segment


def main():
    args = parse_args()

    if not download:
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
    if download:
        images_dir = create_download_dir(args.city)

    if not download:
        print("Counting... ", end="", flush=True)
    else:
        print("Downloading... ", end="", flush=True)

    street_views_count = walk_the_routes(args.fov, args.step, images_dir, routes)

    if not download:
        print(f"Total images to download: {street_views_count*2:d}, the size will be ~ {street_views_count*0.05859*2:0.2f} Mb")


main()

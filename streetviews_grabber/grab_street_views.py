import argparse
import concurrent.futures
import math
import os
from random import randrange

from geographiclib.geodesic import Geodesic
from matplotlib import patches

from streetviews_grabber.debugplot import is_plot, set_visualize, get_plt
from streetviews_grabber.streetview import streetview_available, streetview_grab
from streetviews_grabber.osm import get_osm_data
from streetviews_grabber.tmp_logger import verbose_info, set_verbose


debug = False
download = False


def get_geoline_props(lat1, lat2, long1, long2):
    geoline = Geodesic.WGS84.Inverse(lat1, long1, lat2, long2)
    azimuth = geoline['azi1']
    length = geoline['s12']
    return azimuth, length


def look_around(lat, lon, forward_heading, fov, radius, images_dir, uniq_id):
    heading_left = forward_heading - 90
    filename = f"{uniq_id}-left.jpeg"
    streetview_grab(lat, lon, heading_left, fov, radius, images_dir, filename, debug)

    heading_right = forward_heading + 90
    filename = f"{uniq_id}-right.jpeg"
    streetview_grab(lat, lon, heading_right, fov, radius, images_dir, filename, debug)


def create_download_dir(city):
    images_dir = os.path.join("../images", city)
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
    global debug, download
    set_verbose(args.verbose)
    set_visualize(args.visualize)
    debug = args.debug
    download = args.download
    return args


def handle_route(fov, images_dir, route, step):
    verbose_info(f"Route {route.id:d}")
    milestones = route.get_nodes()
    panos_in_route = 0
    for segment in range(0, len(milestones) - 1):
        verbose_info(f"\tSegment {segment:d}")
        starting_milestone = milestones[segment]
        ending_milestone = milestones[segment + 1]
        if debug and is_plot():
            get_plt().plot([starting_milestone.lon, ending_milestone.lon], [starting_milestone.lat, ending_milestone.lat],
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
    if debug and is_plot():
        get_plt().title('The Segments')
        get_plt().xlabel('Longitude')
        get_plt().ylabel('Latitude')
        get_plt().axis('equal')
        get_plt().show()
    return panos


def walk_segment(start_point, length, azimuth, fov, step, images_dir):
    panos_in_segment = 0
    search_radius = math.ceil(step / 2)
    debug_search_radius = step / 2
    verbose_info(f"\t\tStep: {step:.02f}")
    verbose_info(f"\t\tSearch radius: {search_radius:.02f}")
    offset = search_radius
    get_plt().plot(start_point.lon, start_point.lat, 'g^')
    while offset + search_radius < length:
        shifted_geonode = Geodesic.WGS84.Direct(start_point.lat, start_point.lon, azimuth, offset)
        curr_lat = shifted_geonode['lat2']
        curr_lon = shifted_geonode['lon2']
        verbose_info(f"\t\t\tHave passed {offset:.02f} meters from the start of the street, "
                     f"came into {curr_lat:f},{curr_lon:f}")
        if debug and is_plot():
            get_plt().plot([curr_lon], [curr_lat], 'go')
            geo_radius_lon = Geodesic.WGS84.Direct(curr_lat, curr_lon, 90, search_radius)['lon2'] - curr_lon
            geo_radius_lat = Geodesic.WGS84.Direct(curr_lat, curr_lon, 0, search_radius)['lat2'] - curr_lat
            search_area = patches.Ellipse((curr_lon, curr_lat), geo_radius_lon * 2, geo_radius_lat * 2, fill=False, color='b')
            get_plt().gca().add_patch(search_area)

            debug_geo_radius_lon = Geodesic.WGS84.Direct(curr_lat, curr_lon, 90, debug_search_radius)['lon2'] - curr_lon
            debug_geo_radius_lat = Geodesic.WGS84.Direct(curr_lat, curr_lon, 0, debug_search_radius)['lat2'] - curr_lat
            search_area = patches.Ellipse((curr_lon, curr_lat), debug_geo_radius_lon * 2, debug_geo_radius_lat * 2, fill=False, color='r')
            get_plt().gca().add_patch(search_area)

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

import argparse
import concurrent.futures
import logging
import math
import os
import sys
from random import randrange

from geographiclib.geodesic import Geodesic
import matplotlib.pyplot as plt
import matplotlib

import streetview
from osm import get_osm_data
import context


def get_geoline_props(lat1, lat2, long1, long2):
    geoline = Geodesic.WGS84.Inverse(lat1, long1, lat2, long2)
    azimuth = geoline['azi1']
    length = geoline['s12']
    return azimuth, length


def look_around(lat, lon, forward_heading, fov, radius, images_dir, uniq_id,
                ctx):
    heading_left = forward_heading - 90
    filename = f"{uniq_id}-left.jpeg"
    streetview.streetview_grab(lat, lon, heading_left, fov, radius,
                               images_dir, filename, ctx)

    heading_right = forward_heading + 90
    filename = f"{uniq_id}-right.jpeg"
    streetview.streetview_grab(lat, lon, heading_right, fov, radius,
                               images_dir, filename, ctx)


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
    return args


def handle_route(fov, images_dir, route, step, ctx):
    logging.debug("Route %d", route.id)
    milestones = route.get_nodes()
    panos_in_route = 0
    for segment in range(0, len(milestones) - 1):
        logging.debug("\tSegment %d", segment)
        starting_milestone = milestones[segment]
        ending_milestone = milestones[segment + 1]
        if ctx.debug and ctx.plot:
            plt.plot([starting_milestone.lon, ending_milestone.lon],
                     [starting_milestone.lat, ending_milestone.lat],
                     'or-')
        logging.debug("\t\tstart: %f, %f", starting_milestone.lat, starting_milestone.lon)
        logging.debug("\t\tend: %f, %f", ending_milestone.lat, ending_milestone.lon)
        azimuth, length = get_geoline_props(starting_milestone.lat, ending_milestone.lat, starting_milestone.lon,
                                            ending_milestone.lon)
        logging.debug("\t\tazimuth: %f", azimuth)
        logging.debug("\t\tlength: %f", length)
        logging.debug("\t\tStepping the segment...")
        panos_in_segment = walk_segment(starting_milestone, length, azimuth,
                                        fov, step, images_dir, ctx)
        panos_in_route += panos_in_segment
    return panos_in_route


def walk_the_routes(fov, step, images_dir, routes, ctx):
    panos = 0
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = {executor.submit(handle_route, fov, images_dir, route,
                                   step, ctx) for route in routes}
        for future in concurrent.futures.as_completed(futures):
            panos += future.result()
    if ctx.debug and ctx.plot:
        plt.title('The Segments')
        plt.xlabel('Longitude')
        plt.ylabel('Latitude')
        plt.axis('equal')
        plt.show()
    return panos


def walk_segment(start_point, length, azimuth, fov, step, images_dir, ctx):
    panos_in_segment = 0
    search_radius = math.ceil(step / 2)
    logging.debug("\t\tStep: %.02f", step)
    logging.debug("\t\tSearch radius: %.02f", search_radius)
    offset = search_radius
    plt.plot(start_point.lon, start_point.lat, 'g^')
    while offset + search_radius < length:
        shifted_geonode = Geodesic.WGS84.Direct(start_point.lat, start_point.lon, azimuth, offset)
        curr_lat = shifted_geonode['lat2']
        curr_lon = shifted_geonode['lon2']
        logging.debug("\t\t\tHave passed %.02f meters from the start of the street, came into %f,%f", offset, curr_lat,
                      curr_lon)
        if ctx.debug and ctx.plot:
            plt.plot([curr_lon], [curr_lat], 'go')
            geo_radius_lon = Geodesic.WGS84.Direct(curr_lat, curr_lon, 90, search_radius)['lon2'] - curr_lon
            geo_radius_lat = Geodesic.WGS84.Direct(curr_lat, curr_lon, 0, search_radius)['lat2'] - curr_lat
            search_area = matplotlib.patches.Ellipse((curr_lon, curr_lat), geo_radius_lon * 2, geo_radius_lat * 2,
                                              fill=False, color='b')
            plt.gca().add_patch(search_area)

        offset += step
        pano_id = streetview.streetview_available(curr_lat, curr_lon,
                                                  search_radius, ctx)
        if not pano_id:
            continue
        panos_in_segment += 1
        if ctx.download:
            assert images_dir
            look_around(curr_lat, curr_lon, azimuth, fov, search_radius, images_dir, pano_id, ctx)
    return panos_in_segment


def main():
    args = parse_args()
    ctx = context.Context(args.debug, args.download, args.visualize)
    logging.basicConfig(format="%(message)s", stream=sys.stdout)
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
        # Supress excessive debug from matplotib and liburl3
        logging.getLogger('plt').setLevel(logging.ERROR)
        logging.getLogger('matplotlib.font_manager').setLevel(logging.ERROR)
        logging.getLogger('urllib3.connectionpool').setLevel(logging.ERROR)
    else:
        logging.getLogger().setLevel(logging.INFO)

    streetview.streetview_check_key()

    plt.plot()

    if not ctx.download:
        logging.info("Calculate approximate total size of the data to be downloaded for %s", args.city)
    else:
        logging.info("Download the street views for %s", args.city)

    osm_data = get_osm_data(args.city, args.alternative_server)

    routes = osm_data.ways
    if ctx.debug:
        test_route = 0
        if args.rand:
            test_route = randrange(0, len(routes)-1, 1)
        logging.debug("Handle route #%d", test_route)
        routes = routes[test_route:test_route + 1]

    images_dir = None
    if ctx.download:
        images_dir = create_download_dir(args.city)

    if not ctx.download:
        logging.info("Counting... ")
    else:
        logging.info("Downloading... ")

    street_views_count = walk_the_routes(args.fov, args.step, images_dir,
                                         routes, ctx)

    if not ctx.download:
        logging.info("Total images to download: %d, the size will be ~ %0.2f Mb", street_views_count * 2,
                     street_views_count * 0.05859 * 2)

if __name__ == "__main__":
    main()

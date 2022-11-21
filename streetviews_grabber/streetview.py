import json
import logging
import math
import os
import sys

from geographiclib.geodesic import Geodesic
import matplotlib.pyplot as plt
import requests


def streetview_check_key():
    _google_api_key()


def streetview_available(lat, lon, radius, debug=False, plot=False):
    session = _get_session("meta")
    google_meta_api_url = "https://maps.googleapis.com/maps/api/streetview/metadata"
    meta_request_params = {
        "location": f"{lat:f},{lon:f}",
        "key": _google_api_key(),
        "radius": radius
    }
    r = session.get(google_meta_api_url, params=meta_request_params)
    logging.debug("\t\t\t\tStreet View meta request: %s", r.request.url)
    image_meta = json.loads(r.content)
    if image_meta['status'] != "OK":
        return None
    if image_meta['copyright'] != "© Google":
        return None
    if debug and plot:
        plt.plot(image_meta['location']['lng'], image_meta['location']['lat'], 'b*')
    return image_meta['pano_id']


def streetview_grab(lat, lon, heading, fov, radius, download_dir, filename, debug=False, plot=False):
    session = _get_session("12")
    google_api_url = "https://maps.googleapis.com/maps/api/streetview"
    view_request_params = {
        "location": f"{lat:f}, {lon:f}",
        "size": "640x480",
        "key": _google_api_key(),
        "fov": fov,
        "heading": f"{heading:f}",
        "radius": radius
    }
    r = session.get(google_api_url, params=view_request_params)
    logging.debug("\t\t\t\tStreet View request: %s", r.request.url)
    full_file = os.path.join(download_dir, filename)
    logging.debug("\t\t\t\tFile to save: %s", full_file)
    with open(full_file, 'wb') as image_file:
        image_file.write(r.content)
    if debug and plot:
        v = math.cos(math.radians(heading))
        u = math.sin(math.radians(heading))
        meters_in_lon = Geodesic.WGS84.Direct(lat, lon, 90, 1)['lon2'] - lon
        meters_in_lat = Geodesic.WGS84.Direct(lat, lon, 0, 1)['lat2'] - lat
        ratio = meters_in_lat / meters_in_lon
        plt.quiver(lon, lat, u * ratio, v)


sessions = {}


def _get_session(session_type):
    if sessions.get(session_type):
        return sessions.get(session_type)
    session = requests.session()
    sessions[session_type] = session
    return session


def _google_api_key():
    api_key = os.getenv('GOOGLE_API_KEY')
    if not api_key:
        logging.error("No GOOGLE_API_KEY env variable provided!")
        sys.exit(1)
    return api_key

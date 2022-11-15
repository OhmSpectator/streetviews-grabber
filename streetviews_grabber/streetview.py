import json
import math
import os
import sys

import requests
from geographiclib.geodesic import Geodesic
from matplotlib import pyplot

from streetviews_grabber.debugplot import is_plot
from streetviews_grabber.tmp_logger import verbose_info


def streetview_available(lat, lon, radius, debug=False):
    session = _get_session("meta")
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
    if debug and is_plot():
        pyplot.plot(image_meta['location']['lng'], image_meta['location']['lat'], 'b*')
    return image_meta['pano_id']


def streetview_grab(lat, lon, heading, fov, radius, download_dir, filename, debug=False):
    session = _get_session("12")
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
    with open(full_file, 'wb') as image_file:
        image_file.write(r.content)
    if debug and is_plot():
        v = math.cos(math.radians(heading))
        u = math.sin(math.radians(heading))
        meters_in_lon = Geodesic.WGS84.Direct(lat, lon, 90, 1)['lon2'] - lon
        meters_in_lat = Geodesic.WGS84.Direct(lat, lon, 0, 1)['lat2'] - lat
        ratio = meters_in_lat / meters_in_lon
        pyplot.quiver(lon, lat, u * ratio, v)


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
        print("No GOOGLE_API_KEY env variable provided...")
        sys.exit(1)
    return api_key


KEY = _google_api_key()

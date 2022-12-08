import logging
import sys

import overpy


def get_osm_data(city, alternative_server):
    query = f"""
    area[name="{city}"][1];
    (way["highway"](area); >;);
    out skel;
    """
    logging.debug("Overpass API queue:")
    logging.debug(query)
    api = overpy.Overpass()
    logging.info("Requesting the OSM data... ")
    try:
        result = api.query(query)
    except overpy.exception.OverpassTooManyRequests as e:
        logging.debug("failed!")
        logging.debug(e)
        logging.debug("The main server refused to handle, try %s", alternative_server)
        api = overpy.Overpass(alternative_server.encode())
        logging.debug("Requesting the OSM data... ")
        try:
            result = api.query(query)
        except TypeError as e:
            logging.info("failed!")
            logging.info(e)
            logging.info("Failed to connect to the alternative server (%s). Make sure it's correct (read help for the"
                         "script for the details).", alternative_server)
            sys.exit(1)
        except overpy.exception.OverpassTooManyRequests as e:
            logging.info("failed!")
            logging.info(e)
            sys.exit(1)
    except Exception as e:
        logging.info("failed!")
        logging.info(e)
        raise
    return result

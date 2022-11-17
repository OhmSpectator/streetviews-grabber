import sys

import overpy
import simple_logger

logger = simple_logger.Logger()

def get_osm_data(city, alternative_server):
    query = f"""
    area[name="{city}"];
    (way["highway"](area); >;);
    out skel;
    """
    logger.verbose("Overpass API queue:")
    logger.verbose(query)
    api = overpy.Overpass()
    logger.info("Requesting the OSM data... ", end="", flush=True)
    try:
        result = api.query(query)
    except overpy.exception.OverpassTooManyRequests as e:
        logger.verbose("failed!")
        logger.verbose(e)
        logger.verbose(f"The main server refused to handle, try {alternative_server}")
        api = overpy.Overpass(alternative_server.encode())
        logger.verbose("Requesting the OSM data... ", end="", flush=True)
        try:
            result = api.query(query)
        except TypeError as e:
            logger.info("failed!")
            logger.info(e)
            logger.info(f"Failed to connect to the alternative server ({alternative_server}). Make sure it's correct ("
                  f"read help for the script for the details).")
            sys.exit(1)
        except overpy.exception.OverpassTooManyRequests as e:
            logger.info("failed!")
            logger.info(e)
            sys.exit(1)
    except Exception as e:
        logger.info("failed!")
        logger.info(e)
        raise
    logger.info("done!")
    return result

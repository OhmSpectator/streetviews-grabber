# The Street Views Grabber

The script grabs Google Street View for a city.

## How does it work
It works in several steps:
1. Get a list of the roads (of all types, including pedestrian, service, etc.) for the area passed as a parameter. That
is done via Overpass API.
2. Count the intermediate points of the roads.
3. For all the intermediate points - check whether a street view is available there, and download if yes. That is done
via the Google Street View Metadata API (for checking), and the Google Street View Static API (for downloading).

## Requirements

### Modules
A list of python3 modules are necessary for the script.

At least they are:
* `overpy`
* `geographiclib`
* ...

### Google API key
Moreover, an API key is necessary to get access to the Google APIs. It should be stored as the `KEY` variable in the
`__init__.py` file of the `google_key` module.

A key for a project can be obtained at Google Cloud (https://cloud.google.com/).

## Usage:
```
python3 grab_street_views.py [-h] [--debug] [--verbose] [--count-only]
                            [--alternative-server ALTERNATIVE_SERVER]
                            city

positional arguments:
  city                  the city for which street views shall be downloaded.
                        The name should be written in its original language
                        (e.g. Москва, not Moscow).
optional arguments:
  -h, --help            show this help message and exit
  --debug               run in debug mode
  --verbose             show info about all the processed points
  --count-only          do not download the images, only count their amount
                        and calculate approximate total size
  --alternative-server ALTERNATIVE_SERVER
                        alternative server of Overpass API if the main one
                        refuses to handle. Must start with "http(s)" and
                        contain the right URL (usually, "api/interpreter")
  --fov [20-120]        field of view of the street views. Less the value,
                        more zoomed the images. Must be in a range between 20
                        and 120. Default is 50.
  --rand                in the case of debug run, randomize the route to be
                        handled (by default, the first one is taken)
```

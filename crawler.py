import argparse
import json
import math
import os
import time
from pathlib import Path
from typing import Any
import googlemaps
import h3

# Google Places api response example:
# {'business_status': 'OPERATIONAL',
#  'geometry': {'location': {'lat': 37.5663339, 'lng': -122.3223532},
#               'viewport': {'northeast': {'lat': 37.5674944302915,
#                                          'lng': -122.3212776197085},
#                            'southwest': {'lat': 37.5647964697085,
#                                          'lng': -122.3239755802915}}},
#  'icon': 'https://maps.gstatic.com/mapfiles/place_api/icons/v1/png_71/movies-71.png',
#  'icon_background_color': '#13B5C7',
#  'icon_mask_base_uri': 'https://maps.gstatic.com/mapfiles/place_api/icons/v2/movie_pinlet',
#  'name': 'Cinemark Century San Mateo 12',
#  'photos': [{'height': 2500,
#              'html_attributions': ['<a '
#                                    'href="https://maps.google.com/maps/contrib/111383913900870229200">Lawrence '
#                                    'Marcus</a>'],
#              'photo_reference': 'AVzFdbkewl2VtR33d_wzgh97eMyLYTqmMofO8k6I7DtGojPWLrrJKLIuLDrjvyo3gw4AKDZRfH101NHnPxWq8T11s7bhyGk_BflWY_35_YpUTmGFIkxWYYssDWbkUXXXUV7dPP6VCPxxdwnzKEQR4P0CY44CoWn-YwwJEKnC8ySlWJF4gUlJ',
#              'width': 2268}],
#  'place_id': 'ChIJd3dEm3Cej4ARl8USef836uE',
#  'plus_code': {'compound_code': 'HM8H+G3 San Mateo, CA, USA',
#                'global_code': '849VHM8H+G3'},
#  'rating': 4.4,
#  'reference': 'ChIJd3dEm3Cej4ARl8USef836uE',
#  'scope': 'GOOGLE',
#  'types': ['movie_theater',
#            'meal_takeaway',
#            'restaurant',
#            'food',
#            'point_of_interest',
#            'establishment'],
#  'user_ratings_total': 1822,
#  'vicinity': '320 2nd Avenue, San Mateo'}

# https://t1nak.github.io/blog/2020/h3intro/
h3_resolution_to_edge_length_in_meters = {
    7: 5161.2,
    8: 461.354,
    9: 174.375,
    10: 65.907,
    11: 24.910,
    # 12: 9.4155,
    # 13: 3.5599,
    # 14: 1.3486,
    # 15: 0.5197,
}


def get_hex_centers(
        lat: float, lng: float, distance_meters: int, h_resolution: int
) -> tuple[tuple[float, float]]:
    """
    returns a list of latitude and longitude centroids based on
    distance_meters and h3 resolution

    :param lat: latitude center
    :param lng: longitude center
    :param distance_meters: distance in meters to generate cells
    :param h_resolution:
    :return:
    """
    k_distance = math.floor(
        distance_meters / h3_resolution_to_edge_length_in_meters[h_resolution]
    )
    hex_origin = h3.latlng_to_cell(lat, lng, h_resolution)
    hexes = h3.grid_disk(hex_origin, k_distance)  # Get surrounding hexagons
    hex_centroids = tuple(h3.cell_to_latlng(h) for h in hexes)
    print(f"Broke up {lat},{lng},r={distance_meters} to {len(hex_centroids)} hexes of {k_distance} hops.")
    return hex_centroids  # noqa


def geocode(gclient: Any, zipcode: str):
    geocode_result = gclient.geocode(zipcode)
    if not geocode_result:
        raise Exception("Invalid ZIP code.")

    loc = geocode_result[0]["geometry"]["location"]

    return loc["lat"], loc["lng"]


def get_places(gclient: Any, lat: float, lng: float, radius_m: int):
    next_page_token = None
    places = []
    while True:
        places_result = gclient.places_nearby(
            location=(lat, lng),
            radius=radius_m,
            type="restaurant",
            page_token=next_page_token,
        )
        next_page_token = places_result.get("next_page_token")

        for place in places_result["results"]:
            # pp(place)
            print(
                f"{place['name']:<30} {place['vicinity']:<40} {place['geometry']['location']}"
            )
        places.extend(places_result["results"])

        time.sleep(2)  # google rate-limits
        if not next_page_token:
            break


    print(f"Found a total of {len(places)} places at {lat}, {lng} radius={radius_m}m")
    return places


def search_radius(search_lat, search_long, h_resolution: int, radius_m: int, dict_storage: dict):
    print(f"Searching radius...{search_lat},{search_long}, r={radius_m}m")
    hex_radius = math.ceil(h3_resolution_to_edge_length_in_meters[h_resolution])
    hex_coords = get_hex_centers(search_lat, search_long, radius_m, h_resolution)

    for hex_lat, hex_lng in hex_coords:
        places_found = get_places(client, hex_lat, hex_lng, hex_radius)
        for place in places_found:
            dict_storage[place["place_id"]] = place

        if len(places_found) == 60:
            print(
                "Warning: found maximum number of places, recursing into ",
                f"lat:{hex_lat} lng:{hex_lng}, radius_m:{radius_m}"
            )
            search_radius(hex_lat, hex_lng, h_resolution + 1, hex_radius, dict_storage)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("zipcode", type=str, help="Zip code")
    api_key = os.getenv("API_KEY")

    assert api_key, "API_KEY environment variable not set"

    storage = Path("places_storage.json")
    if storage.exists():
        place_store = json.load(storage.open("r"))
    else:
        place_store = {}

    options = parser.parse_args()
    client = googlemaps.Client(key=api_key)

    zip_lat, zip_lng = geocode(client, options.zipcode)

    start_resolution = 7
    search_radius_m = 5000

    try:
        search_radius(zip_lat, zip_lng, start_resolution, search_radius_m, place_store)
    except KeyboardInterrupt:
        print("Keyboard Interrupt detected, flushing map.")
    finally:
        with storage.open("w") as fh:
            json.dump(place_store, fh)  # noqa


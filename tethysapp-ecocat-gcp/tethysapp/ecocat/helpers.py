import os
import tempfile
import geojson
from shapely import transform
from shapely.geometry import mapping, shape
from shapely.ops import unary_union
from typing import List, Optional, Tuple, Union
from geojson import Point, Polygon, Feature, FeatureCollection
from pyproj import Transformer
from .app import App
from .model import *

def handle_upload(request: dict, id: str) -> Optional[dict]:
    """
    Reads in the uploaded GeoJSON file and returns it as a dictionary.
    """

    uploaded_file = request.FILES[id]
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = os.path.join(temp_dir, 'temp.geojson')
        with open(temp_path, 'wb') as temp_file:
            for chunk in uploaded_file.chunks():
                temp_file.write(chunk)
        try:
            with open(temp_path, 'r') as f:
                geojson_dict = geojson.load(f)
            return geojson_dict
        except:
            return None

def buffer_collection(collection: dict, buffer: int) -> dict:
    """
    Buffer a FeatureCollection and dissolve overlapping features
    """

    # Define the transformers for reprojecting to and from geographic/projected CRS
    geo_to_proj = Transformer.from_crs(4326, 3857, always_xy=True)
    proj_to_geo = Transformer.from_crs(3857, 4326, always_xy=True)

    # Convert the geometries to Shapely shapes
    geoms = [shape(geom) for geom in collection['features']]

    # Loop through all geometries and buffer them individually
    buffered_features = []
    for geom in geoms:
        shape_proj = transform(geom, geo_to_proj.transform, interleaved=False)
        buffered_shape_proj = shape_proj.buffer(int(buffer) * 1e3)
        shape_geo = transform(buffered_shape_proj, proj_to_geo.transform, interleaved=False)
        buffered_features.append(shape_geo)

    # Find the union of all buffered geometries
    union_geoms = unary_union(buffered_features)

    # Return the dissolved buffer of the collection as a GeoJSON
    buffered_collection = mapping(union_geoms)

    return buffered_collection
        
def calculate_area(collection: dict) -> float:
    """
    Calculates the total area of a FeatureCollection.
    """

    # Define the CRS transform
    transformer = Transformer.from_crs(4326, 3857, always_xy=True)

    # Loop over the features and calculate the total area
    area = 0
    for geom in collection['features']:
        shape_geo = shape(geom['geometry'])
        shape_proj = transform(shape_geo, transformer.transform, interleaved=False)
        area += shape_proj.area

    return area
    
def calculate_extent(collection: dict) -> List[float]:
    """
    Calculate the min/max extent of a list of geometries.
    """

    if isinstance(collection, str):
        collection = geojson.loads(collection)

    geoms = [feature['geometry'] for feature in collection['features']]

    lats = []
    lons = []
    for geom in geoms:
        if geom['type'] == 'Point':
            lons.append(geom['coordinates'][0])
            lats.append(geom['coordinates'][1])
        elif geom['type'] == 'Polygon':
            coords = geom['coordinates'][0]
            for coord in coords:
                lons.append(coord[0])
                lats.append(coord[1])
        elif geom['type'] == 'MultiPolygon':
            for coords in geom['coordinates']:
                for coord in coords[0][0]:
                    lons.append(coord[0])
                    lats.append(coord[1])

    # Get the min/max latitude/longitude coordinates
    min_lon, min_lat, max_lon, max_lat = [min(lons), min(lats), max(lons), max(lats)]

    # Buffer the coordinates
    lon_delta = 0.1 * (max_lon - min_lon)
    lat_delta = 0.1 * (max_lat - min_lat)
    extent = [min_lon - lon_delta, min_lat - lat_delta, max_lon + lon_delta, max_lat + lat_delta]

    return extent

def check_area(collection: dict, scale: int) -> float:
    """
    Check the number of pixels in the RoI
    """

    # Get the area of the RoI in m2
    roi_area = calculate_area(collection)

    # Find the number of pixels (RoI area / pixel area)
    n_pixels = roi_area / (scale**2)

    return n_pixels

def check_geom(geom: Union[str, dict]) -> Tuple[FeatureCollection, str]:
    """
    Check and validate the geometry
    """

    # Convert the GeoJSON representation of the geometry into a dictionary
    if isinstance(geom, str):
        geom = geojson.loads(geom)

    # Check that there are geometries
    if 'geodesic' in geom.keys() and not geom.get('geodesic'):
        return FeatureCollection([]), f"No geometries found within the RoI"

    # Create a FeatureCollection containing a single Point or Polygon geometry
    if geom['type'] == 'Point' or geom['type'] == 'Polygon':
        return FeatureCollection([Feature(geometry=geom, properties={})]), ""
    
    # Convert a MultiPoint into a FeatureCollection of Point geometries
    elif geom['type'] == 'MultiPoint':
        return FeatureCollection([Feature(geometry=Point(i), properties={}) for i in geom['coordinates']]), ""
    
    # Convert a MultiPolygon into a FeatureCollection of Polygon geometries
    elif geom['type'] == 'MultiPolygon':
        return FeatureCollection([Feature(geometry=Polygon(i), properties={}) for i in geom['coordinates']]), ""
    
    # Explode any MultiPoint or MultiPolygon geometries in a GeometryCollection
    elif geom['type'] == 'GeometryCollection':
        features = []
        geom_types = []
        for i in geom['geometries']:
            properties = {} if i.get('properties', None) is None else i['properties']
            if i['type'] == 'Point':
                geom_types.append(i['type'])
                features.append(Feature(geometry=Point(i['coordinates']), properties=properties))
            elif i['type'] == 'Polygon':
                geom_types.append(i['type'])
                features.append(Feature(geometry=Polygon(i['coordinates']), properties=properties))
            elif i['type'] == 'MultiPoint':
                for j in i['coordinates']:
                    geom_types.append('Point')
                    features.append(Feature(geometry=Point(j), properties=properties))
            elif i['type'] == 'MultiPolygon':
                for j in i['coordinates']:
                    geom_types.append('Polygon')
                    features.append(Feature(geometry=Polygon(j), properties=properties))
        
        # Check that the FeatureCollection contains only Point or only Polygon geometries
        if len(list(set(geom_types))) == 1:
            return FeatureCollection(features), ""
        else:
            return FeatureCollection([feat for feat in features if feat['geometry']['type'] == 'Polygon']), f"More than one geometry type found. Got {list(set(geom_types))}, try buffering"

    # Explode any MultiPoint or MultiPolygon geometries in a FeatureCollection    
    elif geom['type'] == 'FeatureCollection':
        features = []
        geom_types = []
        for i in geom['features']:
            if i['geometry']['type'] == 'Point':
                geom_types.append('Point')
                features.append(Feature(geometry=Point(i['geometry']['coordinates']), properties=i['properties']))
            elif i['geometry']['type'] == 'Polygon':
                geom_types.append('Polygon')
                features.append(Feature(geometry=Polygon(i['geometry']['coordinates']), properties=i['properties']))
            elif i['geometry']['type'] == 'MultiPoint':
                for j in i['geometry']['coordinates']:
                    geom_types.append('Point')
                    features.append(Feature(geometry=Point(j), properties=i['properties']))
            elif i['geometry']['type'] == 'MultiPolygon':
                for j in i['geometry']['coordinates']:
                    geom_types.append('Polygon')
                    features.append(Feature(geometry=Polygon(j), properties=i['properties']))

        # Check that the FeatureCollection contains only Point or only Polygon geometries
        if len(list(set(geom_types))) == 1:
            return FeatureCollection(features), ""
        else:
            return FeatureCollection([feat for feat in features if feat['type'] == 'Polygon']), f"More than one geometry type found. Got {list(set(geom_types))}, try buffering"
    
    else:
        FeatureCollection([]), f"Geometry should be a Feature/GeometryCollection, Point, MultiPoint, Polygon or MultiPolygon. Got {geom['type']}"

def update_settings(user_workspace: str) -> None:

    # Read in the current user input
    user_dict = get_user_input(user_workspace.path, 'input')

    # Unpack the current settings stored in the user input
    scale = user_dict.get('scale', None)
    model = user_dict.get('model', None)
    method = user_dict.get('method', None)

    # Retrieve the settings from the App portal
    new_scale = App.get_custom_setting('scale')
    new_model = App.get_custom_setting('model')
    new_method = App.get_custom_setting('method')

    # Set default scale if none has been defined
    if not new_scale:
        new_scale = App.set_custom_setting('scale', 100)
        new_scale = App.get_custom_setting('scale')

    # Set default model choice if none has been defined
    if not new_model:
        new_model = App.set_custom_setting('model', 'RF')
        new_model = App.get_custom_setting('model')

    # Set default classification method if none has been defined
    if not new_method:
        new_method = App.set_custom_setting('method', 'pixels')
        new_method = App.get_custom_setting('method')

    # Verify the settings
    if new_scale < 30:
        raise ValueError(f"The scale of analysis (in m/px) should be no smaller than 30 m/px due to the datasets being used. Got {new_scale}")
    if new_model not in ['RF', 'kNN', 'SVM', 'CART']:
        raise NotImplementedError(f"Your chosen model ({new_model}) is not supported. Please choose one of 'RF' (Random Forest), 'kNN' (k Nearest Neighbour), 'SVM' (Support Vector Machine), or 'CART'")
    if new_method not in ['clusters', 'pixels']:
        raise NotImplementedError(f"Only two classification methods are supported. Direct pixel classification ('pixels') or classification of clusters produced by SNIC ('clusters')")

    # Check if the settings have been changed
    if (scale != new_scale) or (model != new_model) or (method != new_method):

        # Remove all classification and export information from all years
        for year in user_dict['years']:
            if user_dict.get(str(year), None):
                for key in ['prob_url', 'class_url', 'thresh', 'task']:
                    if user_dict[str(year)].get(key, None) is not None:
                        user_dict[str(year)].pop(key)

        # Save the user input
        user_dict['scale'] = new_scale
        user_dict['model'] = new_model
        user_dict['method'] = new_method
        add_user_input(user_workspace.path, user_dict, 'input')
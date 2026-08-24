import ee
import shapely
from datetime import datetime as dt
from geojson import Point, Polygon, MultiPolygon, Feature, FeatureCollection
from ee.ee_exception import EEException
from pygbif import occurrences as occ
from pygbif import species
from typing import Optional, Tuple
from . import params as gee_account
from .gee_functions import *
from ..helpers import *
from ..model import *

if gee_account.service_account:
    try:
        credentials = ee.ServiceAccountCredentials(gee_account.service_account, gee_account.private_key)
        ee.Initialize(credentials)
    except EEException as e:
        print(str(e))
else:
    try:
        ee.Initialize()
    except EEException as e:
        print('Unable to initialize GEE. If installing ignore this warning.')

def get_taxon_key(name: str, rank: Optional[str] = None) -> Tuple[Optional[str], str, float]:
    """
    Retrieve the GBIF taxon key for a classification at a certain rank
    """

    # Look up names in all taxonomies in GBIF
    if rank:
        query = species.name_backbone(scientificName=name, taxonRank=rank)
    else:
        query = species.name_backbone(scientificName=name)

    # Check that a match was found
    conf = float(query['diagnostics']['confidence'])
    if query['diagnostics']['matchType'] != 'NONE':
        taxon_key = query['usage']['key']
        taxon_name = query['usage']['name']
        return taxon_key, taxon_name, conf
    else:
        return None, 'No match found', conf

def get_gbif_occurrences(user_dict: dict, year: str, taxonKey: str, basis: Optional[str] = None) -> FeatureCollection:
    """
    Get all occurrences of a classification within the RoI during the assessment period.
    """

    # Get the user inputs
    roi_geoms = user_dict['roi']
    year = int(year)

    # Convert the RoI from a FeatureCollection to a single geometry (Polygon or MultiPolygon)
    coords = [i['geometry']['coordinates'] for i in roi_geoms['features']]
    if len(coords) == 1:
        roi_geom = Polygon(coords[0])
    else:
        roi_geom = MultiPolygon(coords)

    # Convert geometry from GeoJSON to Well Known Text (WKT)
    roi_wkt = shapely.geometry.shape(roi_geom)

    # Get the bounds of the RoI
    roi_bounds_wkt = shapely.geometry.box(*(roi_wkt.bounds), ccw=True)

    # Get all occurrences within the bounds of the RoI
    if basis:
        query = occ.search(taxonKey=taxonKey, 
                        basisOfRecord=basis,
                        geometry=roi_bounds_wkt, 
                        hasGeospatialIssue=False, 
                        hasCoordinate=True, 
                        # year=(year - 1, year + 1), 
                        limit=1000)
    else:
        query = occ.search(taxonKey=taxonKey,
                        geometry=roi_bounds_wkt, 
                        hasGeospatialIssue=False, 
                        hasCoordinate=True, 
                        # year=(year - 1, year + 1), 
                        limit=1000)

    # Extract the coordinates and properties of each occurrence
    cols = ['taxonKey', 'scientificName', 'decimalLatitude', 'decimalLongitude', 'coordinateUncertaintyInMeters', 'eventDate', 'occurrenceStatus', 'basisOfRecord', 'institutionCode', 'license']
    occurrences = [{k: v for k, v in result.items() if k in cols} for result in query['results']]

    # Convert the occurrences to a GeoJSON and filter the occurrences for just those inside the RoI
    occ_features = [Feature(geometry=Point((occ['decimalLongitude'], occ['decimalLatitude'])), properties={k: v for k, v in occ.items() if k not in ['decimalLatitude', 'decimalLongitude']}) for occ in occurrences if roi_wkt.contains(shapely.Point(occ['decimalLongitude'], occ['decimalLatitude']))]

    # Remove occurrences with poor coordinate uncertainty and non-commercial licenses
    occ_features = [feature for feature in occ_features if feature['properties'].get('coordinateUncertaintyInMeters', None) is not None]
    occ_features = [feature for feature in occ_features if feature['properties']['coordinateUncertaintyInMeters'] <= 100]
    occ_features = [feature for feature in occ_features if feature['properties']['license'] != "http://creativecommons.org/licenses/by-nc/4.0/legalcode"]

    return FeatureCollection(occ_features)

def image_to_map_id(image_name: str, vis_params: ee.Dictionary) -> str:
    """
    Get map_id parameters.
    """

    # Make sure the input is a GEE image
    ee_image = ee.Image(image_name)

    # Get the map ID for the image with the given visualisation parameters
    map_id = ee_image.getMapId(vis_params)

    # Return the tile URL
    tile_url = map_id['tile_fetcher'].url_format

    return tile_url

def get_image_url(user_workspace: str, year: str, layer: str, tile_scale: int = 1, min_val: Optional[str] = None, max_val: Optional[str] = None, max_window: int = 5) -> Tuple[str, str, str, Optional[str]]:
    """
    Get a URL for a GEE image asset.
    """

    # Get the user input as a dictionary if it exists
    user_dict = get_user_input(user_workspace.path, 'input')

    # Record the window for collecting images for each assessment year
    if user_dict.get(str(year), None) is None:
        user_dict[str(year)] = {}
    
    # Get the window for the assessment year
    window = user_dict[str(year)].get('window', None)

    # Initialise the warning shown to the user if a non-zero window is used
    warning = None

    # Get the scale of the mapping and the model name (for DI calculation)
    scale = user_dict['scale']
    model_name = user_dict['model']

    # Get the RoI as a GeoJSON if it exists
    roi_geom = get_user_input(user_workspace.path, 'roi')

    # Convert the list of geometries to a FeatureCollection and get the bounding box
    roi_collection = ee.FeatureCollection(roi_geom)
    roi_geom = roi_collection.geometry().bounds()

    # Initialise the visualisation parameters
    vis_params = {}

    # Get the start and end date to use for filtering
    start_date = ee.Date.fromYMD(int(year), 1, 1)
    end_date = ee.Date.fromYMD(1 + int(year), 1, 1)

    # Elevation
    if layer == 'dem':
        collection = ee.ImageCollection('projects/sat-io/open-datasets/FABDEM').filterBounds(roi_geom)
        if collection.size().getInfo() == 0:
            raise ValueError("No DEM data is available for this Region of Interest (RoI). Please use a different RoI")
        image = collection.mosaic().setDefaultProjection('EPSG:3857', None, 30)

    # Slope
    elif layer == 'slope':
        collection = ee.ImageCollection('projects/sat-io/open-datasets/FABDEM').filterBounds(roi_geom)
        if collection.size().getInfo() == 0:
            raise ValueError("No DEM data is available for this Region of Interest (RoI). Please use a different RoI")
        image = ee.Terrain.slope(collection.mosaic().setDefaultProjection('EPSG:3857', None, 30))
        vis_params['palette'] = ['red', 'white', 'green']

    # Global Canopy Height Model for 2019
    elif layer == 'chm':
        collection = ee.ImageCollection('projects/sat-io/open-datasets/GLAD/GEDI_V27').filterBounds(roi_geom)
        if collection.size().getInfo() == 0:
            raise EEException("No canopy height data is available for this Region of Interest. Please use a different RoI")
        image = collection.mosaic()
        vis_params['palette'] = ['red', 'white', 'green']

    # MODIS Net Primary Productivity
    elif layer == 'npp':
        npp_terra_collection = ee.ImageCollection('MODIS/061/MOD17A3HGF').filterBounds(roi_geom).filterDate(start_date, end_date)
        npp_aqua_collection = ee.ImageCollection('MODIS/061/MYD17A3HGF').filterBounds(roi_geom).filterDate(start_date, end_date)
        collection = npp_terra_collection.merge(npp_aqua_collection)
        if collection.size().getInfo() == 0:
            raise EEException("No NPP data is available for this Region of Interest. Please use a different RoI")
        image = collection.select('Npp').median()#.reproject(crs='EPSG:4326', scale=500)
        vis_params['palette'] = ['red', 'white', 'green']

    # MODIS Leaf Area Index
    elif layer == 'lai':
        collection = ee.ImageCollection('MODIS/061/MCD15A3H').filterBounds(roi_geom).filterDate(start_date, end_date)
        if collection.size().getInfo() == 0:
            raise EEException("No LAI data is available for this Region of Interest. Please use a different RoI")
        image = collection.select('Lai').median()
        vis_params['palette'] = ['red', 'white', 'green']

    # If a optical image (visible or index) is selected
    else:

        # If the assessment window has not been checked yet
        if window is None:

            # Check an assessment window from 0 to 5 years
            for window in range(0, max_window + 1):

                start_year = int(year) - window if int(year) - window >= 1982 else 1982
                end_year = int(year) + window if int(year) + window <= 2025 else 2025

                # Find all valid Sentinel-2 images covering the RoI if 2017 or later
                if int(year) >= 2017 and int(year) <= 2025:
                    collection = get_sentinel_collection(year=year, window=window, roi_geom=roi_geom)

                # Find all valid Landsat 4-8 images covering the RoI if between 1982 and 2017
                elif int(year) >= 1982 and int(year) < 2017:
                    collection = get_landsat_collection(year=year, window=window, roi_geom=roi_geom)

                else:
                    raise ValueError(f"Invalid year. Got {year}")

                # Find the first quartile (Q1) of the observation counts per pixel across the RoI
                Q1_count = collection.select('R').count().reduceRegion(geometry=roi_geom, reducer=ee.Reducer.percentile([25]), maxPixels=1e13, scale=scale, tileScale=tile_scale).get('R').getInfo()

                # Check that the count was correctly calculated
                if Q1_count is None:
                    raise EEException("Number of observations per pixel in the RoI could not be checked")

                # If there are sufficient observations per pixel, break the loop
                if Q1_count >= 10:

                    # Save the optimal assessment window in the user input
                    user_dict[str(year)]['window'] = window
                    add_user_input(user_workspace.path, user_dict, 'input')

                    # Warn the user of when their assessment starts and end
                    if window != 0:
                        start_year = int(year) - window if int(year) - window >= 1982 else 1982
                        end_year = int(year) + window if int(year) + window <= 2025 else 2025
                        if int(year) < 2017:
                            warning = f"To ensure that there is sufficient data, assessment will occurr between {start_year} and {end_year} inclusive-inclusive"
                        else:
                            warning = f"To preserve quality, the image shown on screen will include data from {start_year} to {end_year} inclusive-inclusive"
                    break

                # Otherwise, if the window optimisation failed, raise an error
                elif window == max_window:
                    raise ValueError(f"Insufficient data could be found for this RoI between {start_year} and {end_year} (inclusive-inclusive). Please use a different RoI or a larger resolution")

        else:

            # Find all valid Sentinel-2 images covering the RoI if 2017 or later
            if int(year) >= 2017 and int(year) <= 2025:
                collection = get_sentinel_collection(year=year, window=window, roi_geom=roi_geom)

            # Find all valid Landsat 4-8 images covering the RoI if between 1982 and 2017
            elif int(year) >= 1982 and int(year) < 2017:
                collection = get_landsat_collection(year=year, window=window, roi_geom=roi_geom)

            else:
                raise ValueError(f"Invalid year. Got {year}")
                
        # Median of visible bands
        if layer == 'visible':
            image = collection.median()
            vis_params['bands'] = ['R', 'G', 'B']

        # Number of observations per pixel
        elif layer == 'count':
            image = collection.select('R').count()
            vis_params['palette'] = ['red', 'white', 'green']

        # Normalised Difference Vegetation Index (NDVI) - Median
        elif layer == 'ndvi':
            image = collection.map(lambda img: img.normalizedDifference(['NIR', 'R'])).median()
            vis_params['palette'] = ['red', 'white', 'green']

        # Normalised Difference Vegetation Index (NDVI) - Std. Dev.
        elif layer == 'ndvi-std':
            image = collection.map(lambda img: img.normalizedDifference(['NIR', 'R'])).reduce(ee.Reducer.stdDev())
            vis_params['palette'] = ['red', 'white', 'green']

        # Enhanced Vegetation Index (EVI) - Median
        elif layer == 'evi':
            image = collection.map(lambda img: calculate_evi(img)).median()
            vis_params['palette'] = ['red', 'white', 'green']

        # Enhanced Vegetation Index (EVI) - Std. Dev.
        elif layer == 'evi-std':
            image = collection.map(lambda img: calculate_evi(img)).reduce(ee.Reducer.stdDev())
            vis_params['palette'] = ['red', 'white', 'green']

        # Soil-Adjusted Vegetation Index (SAVI) - Median
        elif layer == 'savi':
            image = collection.map(lambda img: calculate_savi(img)).median()
            vis_params['palette'] = ['red', 'white', 'green']

        # Soil-Adjusted Vegetation Index (SAVI) - Std. Dev.
        elif layer == 'savi-std':
            image = collection.map(lambda img: calculate_savi(img)).reduce(ee.Reducer.stdDev())
            vis_params['palette'] = ['red', 'white', 'green']

        # # Normalised Difference Moisture Index (NDMI) - Median
        elif layer == 'ndmi':
            image = collection.map(lambda img: img.normalizedDifference(['NIR', 'SWIR1'])).median()
            vis_params['palette'] = ['red', 'white', 'green']

        # Normalised Difference Moisture Index (NDMI) - Std. Dev.
        elif layer == 'ndmi-std':
            image = collection.map(lambda img: img.normalizedDifference(['NIR', 'SWIR1'])).reduce(ee.Reducer.stdDev())
            vis_params['palette'] = ['red', 'white', 'green']

        # # Normalised Difference Greenness Index (NDGI) - Median
        elif layer == 'ndgi':
            image = collection.map(lambda img: calculate_ndgi(img)).median()
            vis_params['palette'] = ['red', 'white', 'green']

        # Normalised Difference Greenness Index (NDGI) - Std. Dev.
        elif layer == 'ndgi-std':
            image = collection.map(lambda img: calculate_ndgi(img)).reduce(ee.Reducer.stdDev())
            vis_params['palette'] = ['red', 'white', 'green']
        
        # # Normalised Difference Phenology Index (NDPI) - Median
        elif layer == 'ndpi':
            image = collection.map(lambda img: calculate_ndpi(img)).median()
            vis_params['palette'] = ['red', 'white', 'green']

        # Normalised Difference Phenology Index (NDPI) - Std. Dev.
        elif layer == 'ndpi-std':
            image = collection.map(lambda img: calculate_ndpi(img)).reduce(ee.Reducer.stdDev())
            vis_params['palette'] = ['red', 'white', 'green']

        # Normalised Difference Water Index (NDWI) - Median
        elif layer == 'ndwi':
            image = collection.map(lambda img: img.normalizedDifference(['G', 'SWIR1'])).median()
            vis_params['palette'] = ['red', 'white', 'green']

        # Normalised Difference Built-up Index (NDBI) - Median
        elif layer == 'ndbi':
            image = collection.map(lambda img: img.normalizedDifference(['SWIR1', 'NIR'])).median()
            vis_params['palette'] = ['red', 'white', 'green']

        # Dissimilarity Index
        elif layer == 'di':
            ecosystem = get_user_input(user_workspace.path, 'ecosystem', year)
            background = get_user_input(user_workspace.path, 'background', year)
            samples = get_user_input(user_workspace.path, 'samples', year)
            image = get_dissimilarity_index(year=year, roi_geom=roi_geom, collection=collection, ecosystem=ecosystem, background=background, samples=samples, scale=scale, model_name=model_name, aoa=False, tile_scale=tile_scale)
            vis_params['palette'] = ['green', 'white', 'red']
    
        # Area of Applicability
        elif layer == 'aoa':
            ecosystem = get_user_input(user_workspace.path, 'ecosystem', year)
            background = get_user_input(user_workspace.path, 'background', year)
            samples = get_user_input(user_workspace.path, 'samples', year)
            image = get_dissimilarity_index(year=year, roi_geom=roi_geom, collection=collection, ecosystem=ecosystem, background=background, samples=samples, scale=scale, model_name=model_name, aoa=False, tile_scale=tile_scale)
            vis_params['palette'] = ['red', 'white', 'green']
    
    # If the user has provided min/max values
    if (min_val is not None and max_val is not None) and (min_val != '' and max_val != ''):
        # image = image.updateMask(image.gte(float(min_val))).updateMask(image.lte(float(max_val)))
        if layer == 'dem':
            image = image.visualize(min=float(min_val), max=float(max_val), palette=['blue', 'green', 'yellow', 'brown', 'white']).divide(255).multiply(ee.Terrain.hillshade(image).divide(255))
            vis_params['min'], vis_params['max'] = 0.0, 1.0
        else:
            vis_params['min'], vis_params['max'] = float(min_val), float(max_val)
        min_str, max_str = f"Current min: {float(min_val):0.2f}", f"Current max: {float(max_val):0.2f}"

    # Otherwise, show the visible bands with the regular min/max values
    elif layer == 'visible':
        if int(year) >= 1983:
            vis_params['min'], vis_params['max'] = 0.0, 0.3
            min_str, max_str = f"Current min: 0.00", f"Current max: 0.30"
        else:
            vis_params['min'], vis_params['max'] = 0.0, 1.0
            min_str, max_str = f"Current min: 0.00", f"Current max: 1.00"

    # Otherwise, show the Dissimilarity Index between 0 to 1
    elif layer == 'di' or layer == 'aoa':
        vis_params['min'], vis_params['max'] = 0.0, 1.0
        min_str, max_str = f"Current min: 0.00", f"Current max: 1.00"
    
    # Automatically scale the image to its min/max values
    else:

        # Get the min/max values of the layer
        min_max = image.reduceRegion(geometry=roi_geom, reducer=ee.Reducer.minMax(), maxPixels=1e13, tileScale=tile_scale)
        min_max = ee.Dictionary(min_max).values().getInfo()

        # Check that there an error has not occurred
        if min_max[0] is None or min_max[1] is None or min_max[0] == min_max[1]:
            raise EEException(f"Issue with scaling image to its min/max values (got min: {min_max[0]}, max: {min_max[1]}). To display the image, input your own values (e.g. -1 to 1 for NDVI)")

        # Normalise the image between the minimum and maximum values
        min_val, max_val = float(min_max[1]), float(min_max[0])

        # Mask the image by it's min and max values
        # image = image.updateMask(image.gte(float(min_val))).updateMask(image.lte(float(max_val)))
        if layer == 'dem':
            image = image.visualize(min=float(min_val), max=float(max_val), palette=['blue', 'green', 'yellow', 'brown', 'white']).divide(255).multiply(ee.Terrain.hillshade(image).divide(255))
            vis_params['min'], vis_params['max'] = 0.0, 1.0
        else:
            vis_params['min'], vis_params['max'] = float(min_val), float(max_val)
        min_str, max_str = f"Current min: {float(min_val):0.2f}", f"Current max: {float(max_val):0.2f}"

    # Get the URL for the resulting image
    url = image_to_map_id(image.clipToCollection(roi_collection), vis_params=vis_params)

    return url, min_str, max_str, warning

def get_samples_collection(user_workspace: str, year: str, tile_scale: int) -> str:

    # Get the user input as a dictionary if it exists
    user_dict = get_user_input(user_workspace.path, 'input')

    # Get the RoI as a GeoJSON if it exists
    roi = get_user_input(user_workspace.path, 'roi')

    # Get the ecosystem and background labels as GeoJSONs if they exist
    ecosystem = get_user_input(user_workspace.path, 'ecosystem', year)
    background = get_user_input(user_workspace.path, 'background', year)

    # Check that the user input has been created
    if user_dict and roi:

        # Get the scale
        scale = user_dict['scale']        

        # Get the assessment window
        if user_dict.get(str(year), None) is None:
            raise OSError(f"Please create and save your ecosystem and background labels before attempting to download the training data")
        elif user_dict[str(year)].get('window', None) is None:
            raise OSError("Please display an image at least once (to calculate the optimal assessment window) before attempting to download training data")
        else:
            window = user_dict[str(year)]['window']
        
    else:
        raise OSError("Please complete the 'User Input' page before attempting to download training data")

    # Check that the ecosystem and background labels are present
    if not (ecosystem and background):
        raise OSError("Please create and save your ecosystem and background labels before attempting to download the training data")

    # Convert the RoI and ecosystem labels to GEE FeatureCollections
    roi_collection = ee.FeatureCollection(roi)

    # Get the RoI as a geometry
    roi_geom = roi_collection.geometry()

    # If using MODIS as the training data
    if int(year) >= 2000 and scale >= 500:

        # Get a composite of MODIS data
        training_data = get_modis_composite(year=year,
                                            roi_geom=roi_geom,
                                            tile_scale=tile_scale)

    # If using Landsat as the training data
    elif int(year) < 2017:

        # Get the Landsat collection
        training_data = get_landsat_composite(year=year, 
                                            roi_geom=roi_geom, 
                                            window=window, 
                                            tile_scale=tile_scale)

    # If using AlphaEarth satellite embeddings as the training data
    elif int(year) >= 2017:

        # Get the start and end date to use for filtering
        start_date = ee.Date.fromYMD(int(year), 1, 1)
        end_date = start_date.advance(1, 'year')

        # Collect the AlphaEarth satellite embeddings and filter by year
        training_data = ee.ImageCollection("GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL").filterBounds(roi_geom).filterDate(start_date, end_date).median()

    # Reproject to the chosen scale
    training_data = training_data.reproject(crs='EPSG:4326', scale=scale)

    # Define a function for creating a fixed grid of points within a polygon
    def fixed_grid(feat):
        geom = ee.Feature(feat).geometry()
        grids = geom.coveringGrid(proj=geom.projection(), scale=2 * scale)
        return grids.map(lambda grid: ee.Feature(ee.Feature(grid).centroid(maxError=0.1))).filter(ee.Filter.contains(leftValue=geom, rightField='.geo'))

    # Convert the ecosystem and background labels to GEE FeatureCollections
    ecosystem_collection = ee.FeatureCollection(ecosystem)
    background_collection = ee.FeatureCollection(background)

    # If the ecosystem was labelled using points
    if ecosystem['features'][0]['geometry']['type'] == 'Point':
        ecosystem_samples = training_data.sampleRegions(collection=ecosystem_collection, tileScale=tile_scale, geometries=True)

    # If the ecosystem was labelled using polygons
    elif ecosystem['features'][0]['geometry']['type'] == 'Polygon':
        ecosystem_points = ecosystem_collection.map(fixed_grid).flatten()
        ecosystem_samples = training_data.sampleRegions(collection=ecosystem_points, tileScale=tile_scale, geometries=True)
        # ecosystem_samples = ecosystem_samples.filter(ee.Filter.contains(leftValue=ecosystem_collection.geometry(), rightField='.geo'))

    # If the background was labelled using points
    if background['features'][0]['geometry']['type'] == 'Point':
        background_samples = training_data.sampleRegions(collection=background_collection, tileScale=tile_scale, geometries=True)

    # If the background was labelled using polygons
    elif background['features'][0]['geometry']['type'] == 'Polygon':
        background_points = background_collection.map(fixed_grid).flatten()
        background_samples = training_data.sampleRegions(collection=background_points, tileScale=tile_scale, geometries=True)
        # background_samples = background_samples.filter(ee.Filter.contains(leftValue=background_collection.geometry(), rightField='.geo'))

    # Assign the class label to each sample
    ecosystem_samples = ecosystem_samples.map(lambda feat: feat.set('class', 1))
    background_samples = background_samples.map(lambda feat: feat.set('class', 0))
    samples = ecosystem_samples.merge(background_samples)

    # Get the predictors from the training data
    predictors = training_data.bandNames()

    # Remove all null samples
    samples = samples.select(predictors.add('class')).filter(ee.Filter.notNull(predictors.add('class')))
    
    return samples.getInfo()

def get_classification_url(user_workspace: str, year: str, tile_scale: int) -> Tuple[str, str]:
    """
    Get the URL for the classification made on a Landsat composite or AlphaEarth embeddings.
    """

    # Get the user input as a dictionary if it exists
    user_dict = get_user_input(user_workspace.path, 'input')

    # Get the RoI as a GeoJSON if it exists
    roi = get_user_input(user_workspace.path, 'roi')

    # Get the samples, ecosystem labels and background labels as GeoJSONs if they exist
    samples = get_user_input(user_workspace.path, 'samples', year)
    ecosystem = get_user_input(user_workspace.path, 'ecosystem', year)
    background = get_user_input(user_workspace.path, 'background', year)

    # Check that all user input has been created
    if user_dict and roi and ((ecosystem and background) or samples):

        # Get the scale, model choice and method
        scale = user_dict['scale']
        model_name = user_dict['model']
        method = user_dict['method'] 

        # Get the assessment window
        if user_dict.get(str(year), None) is None:
            raise OSError("Please complete the 'Labelling' page before attempting mapping")
        elif user_dict[str(year)].get('window', None) is None:
            raise OSError("Please display an image at least once (to calculate the optimal assessment window) before attempting mapping")
        else:
            window = user_dict[str(year)]['window']
        
    else:
        raise OSError("Please complete the 'User Input' and 'Labelling' pages before attempting mapping")

    # Check to see if the classification has already been made
    prob_url = user_dict[str(year)].get('prob_url', None)
    class_url = user_dict[str(year)].get('class_url', None)
    if prob_url is None or class_url is None:

        # Classify the ecosystem
        if method == 'pixels':
            probabilities, _, _, _ = classify_ecosystem(roi=roi, 
                                                    ecosystem=ecosystem, 
                                                    background=background,
                                                    samples=samples,
                                                    year=year,
                                                    window=window,
                                                    tile_scale=tile_scale,
                                                    scale=scale,
                                                    model_name=model_name)
        elif method == 'clusters':
            probabilities, _, _, _ = cluster_ecosystem(roi=roi, 
                                                    ecosystem_geoms=ecosystem, 
                                                    background_geoms=background,
                                                    samples=samples,
                                                    year=year,
                                                    window=window,
                                                    tile_scale=tile_scale,
                                                    scale=scale,
                                                    model_name=model_name)
        else:
            raise NotImplementedError("Chosen classification method not supported")
        
        # Threshold the probabilities to get the classification
        classification = probabilities.gte(0.5).toUint8()

        # Get the tile urls for the classification and probabilities
        prob_url = image_to_map_id(probabilities, vis_params={'min': 0, 'max': 1, 'palette': ['#d7191c', '#fdae61', '#ffffc0', '#a6d96a', '#1a9641']})
        class_url = image_to_map_id(classification.selfMask(), vis_params={'min': 0, 'max': 1, 'palette': ['#FDBB13']})

        # Persist the classification url to the user input
        user_dict[str(year)]['prob_url'] = prob_url
        user_dict[str(year)]['class_url'] = class_url
        add_user_input(user_workspace.path, user_dict, 'input')

    return prob_url, class_url

def generate_metrics(user_workspace: str, year: str, tile_scale: int) -> Tuple[str, float, float, float, float]:
    """
    Get the validation metrics and max importance variable.
    """

    # Get the user input as a dictionary if it exists
    user_dict = get_user_input(user_workspace.path, 'input')

    # Get the RoI as a GeoJSON if it exists
    roi = get_user_input(user_workspace.path, 'roi')

    # Get the samples, ecosystem labels and background labels as GeoJSONs if they exist
    samples = get_user_input(user_workspace.path, 'samples', year)
    ecosystem = get_user_input(user_workspace.path, 'ecosystem', year)
    background = get_user_input(user_workspace.path, 'background', year)

    # Check that all user input has been created
    if user_dict and roi and ((ecosystem and background) or samples):

        # Get the scale, model choice and method
        scale = user_dict['scale']
        model_name = user_dict['model']
        method = user_dict['method'] 

        # Get the assessment window
        if user_dict.get(str(year), None) is None:
            raise OSError("Please complete the 'Labelling' page before attempting mapping")
        elif user_dict[str(year)].get('window', None) is None:
            raise OSError("Please display an image at least once (to calculate the optimal assessment window) before attempting mapping")
        else:
            window = user_dict[str(year)]['window']
        
    else:
        raise OSError("Please complete the 'User Input' and 'Labelling' pages before attempting mapping")

    # Classify the ecosystem
    if method == 'pixels':
        _, model_info, train_matrix, val_matrix = classify_ecosystem(roi=roi, 
                                                    ecosystem=ecosystem, 
                                                    background=background,
                                                    samples=samples,
                                                    year=year,
                                                    window=window,
                                                    tile_scale=tile_scale,
                                                    scale=scale,
                                                    model_name=model_name)
    elif method == 'clusters':
        _, model_info, train_matrix, val_matrix = cluster_ecosystem(roi=roi, 
                                                    ecosystem=ecosystem, 
                                                    background=background,
                                                    samples=samples,
                                                    year=year,
                                                    window=window,
                                                    tile_scale=tile_scale,
                                                    scale=scale,
                                                    model_name=model_name)
    else:
        raise NotImplementedError("Chosen classification method not supported")
    
    # Retrieve the importances of each variable
    importance_dict = ee.Dictionary(model_info.get('importance'))
    important_vars = importance_dict.keys().sort(importance_dict.values()).reverse()
    max_importances = ee.List(important_vars).slice(0, 3).getInfo()

    # Convert the band ID to an understandable name (except for AlphaEarth bands)
    for v, var in enumerate(max_importances):
        if var == 'R':
            max_importances[v] = 'Red band'
        elif var == 'G':
            max_importances[v] = 'Green band'
        elif var == 'B':
            max_importances[v] = 'Blue band'
        elif var == 'NDVI_med':
            max_importances[v] = "NDVI (Vegetation) - median"
        elif var == 'NDVI_std':
            max_importances[v] = "NDVI (Vegetation) - st. dev."
        elif var == 'EVI_med':
            max_importances[v] = "EVI (Enhanced Veg.) - median"
        elif var == 'EVI_std':
            max_importances[v] = "EVI (Enhanced Veg.) - st. dev."
        elif var == 'SAVI_med':
            max_importances[v] = "SAVI (Soil-adj. Veg.) - median"
        elif var == 'SAVI_std':
            max_importances[v] = "SAVI (Soil-adj. Veg.) - st. dev."
        elif var == 'NDMI_med':
            max_importances[v] = "NDMI (Moisture) - median"
        elif var == 'NDMI_std':
            max_importances[v] = "NDMI (Moisture) - st. dev."
        elif var == 'NDWI':
            max_importances[v] = "NDWI (Water) - median"
        elif var == 'NDBI':
            max_importances[v] = "NDWI (Urban) - median"
        elif var == 'elevation':
            max_importances[v] = "Elevation"
        elif var == 'slope':
            max_importances[v] = "Slope"
    max_importances = ', '.join(max_importances)
    
    # Calculate the precision (consumer's accuracy)
    train_precision = train_matrix.consumersAccuracy().get([0, 1]).getInfo()
    val_precision = val_matrix.consumersAccuracy().get([0, 1]).getInfo()

    # Calculate the recall (producer's accuracy)
    train_recall = train_matrix.producersAccuracy().get([1, 0]).getInfo()
    val_recall = val_matrix.producersAccuracy().get([1, 0]).getInfo()

    # Calculate the F1-score (harmonic mean between precision and recall)
    train_f1_score = train_matrix.fscore().get([1]).getInfo()
    val_f1_score = val_matrix.fscore().get([1]).getInfo()

    # Calculate the overall accuracy (TP + TN / TP + TN + FP + FN)
    train_accuracy = train_matrix.accuracy().getInfo()
    val_accuracy = val_matrix.accuracy().getInfo()

    return max_importances, train_precision, train_recall, train_f1_score, train_accuracy, val_precision, val_recall, val_f1_score, val_accuracy

def export_classification(user_workspace: str, user_name: str, year: str, tile_scale: int) -> Tuple[str, str, dict]:
    """
    Export the classification to EcoCAT's Google Cloud bucket.
    """
    
    # Get the user input as a dictionary if it exists
    user_dict = get_user_input(user_workspace.path, 'input')

    # Get the RoI as a GeoJSON if it exists
    roi = get_user_input(user_workspace.path, 'roi')

    # Get the samples, ecosystem labels and background labels as GeoJSONs if they exist
    samples = get_user_input(user_workspace.path, 'samples', year)
    ecosystem = get_user_input(user_workspace.path, 'ecosystem', year)
    background = get_user_input(user_workspace.path, 'background', year)

    # Check that all user input has been created
    if user_dict and roi and ((ecosystem and background) or samples):

        # Get the scale, model choice and method
        scale = user_dict['scale']
        model_name = user_dict['model']
        method = user_dict['method'] 

        # Get the assessment window
        if user_dict.get(str(year), None) is None:
            raise OSError("Please complete the 'Labelling' page before attempting mapping")
        elif user_dict[str(year)].get('window', None) is None:
            raise OSError("Please display an image at least once (to calculate the optimal assessment window) before attempting mapping")
        else:
            window = user_dict[str(year)]['window']
        
    else:
        raise OSError("Please complete the 'User Input' and 'Labelling' pages before attempting mapping")

    # Classify the ecosystem
    if method == 'pixels':
        probabilities, _, train_matrix, val_matrix = classify_ecosystem(roi=roi, 
                                                        ecosystem=ecosystem, 
                                                        background=background,
                                                        samples=samples,
                                                        year=year,
                                                        window=window,
                                                        tile_scale=tile_scale,
                                                        scale=scale,
                                                        model_name=model_name)
    elif method == 'clusters':
        probabilities, _, train_matrix, val_matrix = cluster_ecosystem(roi=roi, 
                                                        ecosystem=ecosystem, 
                                                        background=background,
                                                        samples=samples,
                                                        year=year,
                                                        window=window,
                                                        tile_scale=tile_scale,
                                                        scale=scale,
                                                        model_name=model_name)
    else:
        raise NotImplementedError("Chosen classification method not supported")
    
    # Define the region for the export
    # region = ee.FeatureCollection(roi_geoms).geometry()

    # # Get the standard deviation of the probabilites
    # prob_std = ee.Number(probabilities.reduceRegion(reducer=ee.Reducer.stdDev(), geometry=region.bounds(), maxPixels=1e13, tileScale=tile_scale).get('classification'))

    # Threshold the probability map
    # classification = ee.Image([probabilities.gte(thresh.add(prob_std)), probabilities.gte(thresh), probabilities.gte(thresh.subtract(prob_std))]).toUint8().rename(['min', 'opt', 'max'])
    classification = probabilities.gte(0.5).toUint8().rename('ecosystem')

    # Set all masked pixels to zero
    classification = classification.unmask(0)

    # Set some properties
    val_matrix_arr = val_matrix.array()
    val_TP = val_matrix_arr.get([1, 1])
    val_FP = val_matrix_arr.get([0, 1])
    val_TN = val_matrix_arr.get([0, 0])
    val_FN = val_matrix_arr.get([1, 0])
    start_year = int(year) - window if int(year) - window >= 1982 else 1982
    end_year = int(year) + window if int(year) + window <= 2025 else 2025
    classification = classification.set({'VALIDATION_TRUE_POS': val_TP,
                                        'VALIDATION_FALSE_POS': val_FP,
                                        'VALIDATION_TRUE_NEG': val_TN,
                                        'VALIDATION_FALSE_NEG': val_FN,
                                        'ASSESSMENT_YEAR' : int(year),
                                        'ASSESSMENT_START_YEAR': int(start_year),
                                        'ASSESSMENT_END_YEAR': int(end_year)})

    # Define the filename
    file_name = f'classification_{user_name}_{year}_{method}_{model_name}_{scale}m'

    # Export the classification
    task = ee.batch.Export.image.toCloudStorage(image=classification,
                                                description=f"EcoCAT classification export for {user_name} at {dt.today()}",
                                                bucket='ecocat-classifications',
                                                fileNamePrefix=file_name,
                                                region=ee.FeatureCollection(roi).geometry().bounds(),
                                                scale=scale,
                                                crs='EPSG:4326',
                                                maxPixels=1e13,
                                                fileFormat='GeoTIFF',
                                                formatOptions={'cloudOptimized': True, 'noData': 0.0},
                                                skipEmptyTiles=True)

    # Start the export task
    task.start()

    return task, file_name, classification.toDictionary().getInfo()

def get_task_status(user_dict: dict) -> str:
    """
    Get the task status of an export operation.
    """

    # Get the operation name
    name = user_dict['task']['operation_name']

    # Get the status
    metadata = ee.data.getOperation(name)
    status = metadata['metadata']['state']
    error = metadata.get('error')
    if error is not None:
        error_message = error['message']
    else:
        error_message = ""

    return status, error_message
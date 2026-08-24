import ee
from typing import Optional, Tuple
from .roi_assets import ASSETS as ROI_ASSETS
from .overlay_assets import ASSETS as OVERLAY_ASSETS
from ee.ee_exception import EEException

def apply_scale_factors(image: ee.Image) -> ee.Image:
    """
    Apply scaling factors to Landsat bands.
    """

    optical_bands = image.multiply(0.0000275).add(-0.2)

    return image.addBands(optical_bands, None, True).copyProperties(image, ['system:time_start', 'CLOUD_COVER_LAND'])

def calculate_evi(image: ee.Image) -> ee.Image:
    """
    Calculating Enhanced Vegetation Index (EVI).
    """

    NIR = image.select('NIR')
    R = image.select('R')
    B = image.select('B')
    top = NIR.subtract(R)
    bottom = NIR.add(ee.Image.constant(6).multiply(R)).subtract(ee.Image.constant(7.5).multiply(B)).add(ee.Image.constant(1))

    return ee.Image.constant(2.5).multiply(top.divide(bottom))

def calculate_ndgi(image: ee.Image) -> ee.Image:
    """
    Calculate Normalised Difference Greenness Index (NDGI)
    """

    NIR = image.select('NIR')
    R = image.select('R')
    G = image.select('G')
    top = ee.Image(0.63).multiply(G).add(ee.Image(0.37).multiply(NIR)).subtract(R)
    bottom = ee.Image(0.63).multiply(G).add(ee.Image(0.37).multiply(NIR)).add(R)

    return ee.Image(top.divide(bottom))

def calculate_ndpi(image: ee.Image) -> ee.Image:
    """
    Calculate Normalised Difference Phenology Index (NDPI)
    """

    NIR = image.select('NIR')
    R = image.select('R')
    SWIR = image.select('SWIR1')
    top = NIR.subtract(ee.Image(0.74).multiply(R)).add(ee.Image(0.26).multiply(SWIR))
    bottom = NIR.add(ee.Image(0.74).multiply(R)).add(ee.Image(0.26).multiply(SWIR))

    return ee.Image(top.divide(bottom))

def calculate_savi(image: ee.Image) -> ee.Image:
    """
    Calculating Soil-Adjusted Vegetation Index (SAVI).
    """

    NIR = image.select('NIR')
    R = image.select('R')
    top = NIR.subtract(R)
    bottom = NIR.add(R).add(ee.Image.constant(0.5))

    return ee.Image.constant(1.5).multiply(top.divide(bottom))

def classify_ecosystem(roi: dict, ecosystem: Optional[dict], background: Optional[dict], samples: Optional[dict], year: int, window: int, tile_scale: int, scale: int, model_name: str, seed: int = 42) -> Tuple[ee.Image, ee.ConfusionMatrix]:
    """
    Classify the ecosystem labelled by the user within their defined RoI.
    """

    # Convert the RoI and ecosystem labels to GEE FeatureCollections
    roi_collection = ee.FeatureCollection(roi)

    # Get a bounding box around the RoI
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
    training_data = training_data.reproject(crs='EPSG:4326', scale=scale).clipToCollection(roi_collection)

    # Define a function for creating a fixed grid of points within a polygon
    def fixed_grid(feat):
        geom = ee.Feature(feat).geometry()
        grids = geom.coveringGrid(proj=geom.projection(), scale=2 * scale)
        return grids.map(lambda grid: ee.Feature(ee.Feature(grid).centroid(maxError=0.1))).filter(ee.Filter.contains(leftValue=geom, rightField='.geo'))

    # If training samples have not been provided, but point/polygon labels have
    if (ecosystem is not None and background is not None):

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

        # Split the classes equally between training and validation sets
        ecosystem_samples = ecosystem_samples.randomColumn(columnName='split', seed=seed)
        background_samples = background_samples.randomColumn(columnName='split', seed=seed)

        # Get the training samples
        train_ecosystem_samples = ecosystem_samples.filter('split <= 0.8')
        train_background_samples = background_samples.filter('split <= 0.8')
        train_samples = train_ecosystem_samples.merge(train_background_samples)

        # Get the validation samples
        val_ecosystem_samples = ecosystem_samples.filter('split > 0.8')
        val_background_samples = background_samples.filter('split > 0.8')
        val_samples = val_ecosystem_samples.merge(val_background_samples)

        # If the user has also provided training samples, merge them
        if samples is not None:

            # Convert the samples to a GEE FeatureCollection and then separate by class
            samples = ee.FeatureCollection(samples)
            user_ecosystem_samples = samples.filter(ee.Filter.eq('class', 1))
            user_background_samples = samples.filter(ee.Filter.eq('class', 0))

            # Split the classes equally between training and validation sets
            user_ecosystem_samples = user_ecosystem_samples.randomColumn(columnName='split', seed=seed)
            user_background_samples = user_background_samples.randomColumn(columnName='split', seed=seed)

            # Get the training samples
            user_train_ecosystem_samples = user_ecosystem_samples.filter('split <= 0.8')
            user_train_background_samples = user_background_samples.filter('split <= 0.8')
            user_train_samples = user_train_ecosystem_samples.merge(user_train_background_samples)
    
            # Get the validation samples
            user_val_ecosystem_samples = user_ecosystem_samples.filter('split > 0.8')
            user_val_background_samples = user_background_samples.filter('split > 0.8')
            user_val_samples = user_val_ecosystem_samples.merge(user_val_background_samples)

            # Merge with the existing training/validation samples
            train_samples = train_samples.merge(user_train_samples)
            val_samples = val_samples.merge(user_val_samples)

    # If training samples have been provided
    elif samples is not None:

        # Convert the samples to a GEE FeatureCollection and then separate by class
        samples = ee.FeatureCollection(samples)
        ecosystem_samples = samples.filter(ee.Filter.eq('class', 1))
        background_samples = samples.filter(ee.Filter.eq('class', 0))

        # Split the classes equally between training and validation sets
        ecosystem_samples = ecosystem_samples.randomColumn(columnName='split', seed=seed)
        background_samples = background_samples.randomColumn(columnName='split', seed=seed)

        # Get the training samples
        train_ecosystem_samples = ecosystem_samples.filter('split <= 0.8')
        train_background_samples = background_samples.filter('split <= 0.8')
        train_samples = train_ecosystem_samples.merge(train_background_samples)

        # Get the validation samples
        user_val_ecosystem_samples = ecosystem_samples.filter('split > 0.8')
        user_val_background_samples = background_samples.filter('split > 0.8')
        val_samples = val_ecosystem_samples.merge(val_background_samples)

    else:
        raise ValueError(f"Neither ecosystem/background labels, or sampled pixel values, have been provided for {year}")
    
    # Get the predictors from the training data
    predictors = training_data.bandNames()

    # Remove all null samples
    train_samples = train_samples.select(predictors.add('class')).filter(ee.Filter.notNull(predictors.add('class')))
    val_samples = val_samples.select(predictors.add('class')).filter(ee.Filter.notNull(predictors.add('class')))

    # Define the parameters for a random forest classifier
    if model_name == 'RF':
        sqrt_features = ee.Number(predictors.length()).pow(0.5).round().int()
        model = ee.Classifier.smileRandomForest(numberOfTrees=500,                  # Number of trees in the entire forest [Recommended value: 100-500]
                                                variablesPerSplit=sqrt_features,    # Max. features to consider for a node split [Recommended value: sqrt(no. features)]
                                                minLeafPopulation=3,                # Min. samples in a leaf to create a node [Recommended value: 1-5]
                                                bagFraction=0.5,                    # Fraction of the training data to be randomly selected per tree [Recommended value: 0.5]
                                                maxNodes=20,                        # Max. nodes in a single tree [Recommended value: 10-30]
                                                seed=seed)                          # Set the random seed for reproducability
    
    # Define the parameters for a k-NN classifier
    elif model_name == 'kNN':
        model = ee.Classifier.smileKNN(k=5,                                         # Number of neighbours for classification
                                    searchMethod='AUTO',                            # Automatically choose search method
                                    metric='EUCLIDEAN')                             # Distance metric to use
        
    # Define the parameters for a support vector machine classifier
    elif model_name == 'SVM':
        model = ee.Classifier.libsvm(decisionProcedure='Voting',                    # Decision procedure to use for classification (Voting or Margin)
                                    svmType='C_SVC',                                # SVM type (only C_SVC and NU_SVC work with probability mode)
                                    kernelType='RBF',                               # Kernel type (LINEAR, POLY, RBF or SIGMOID)
                                    shrinking=True,                                 # Whether to use shrinking heuristics
                                    degree=None,                                    # Degree of polynomial if using POLY for kernelType
                                    gamma=None,                                     # Gamma value in kernel function, defaults to 1/N_features (POLY, RBF and SIGMOID only)
                                    coef0=None,                                     # Coefficient value in POLY and SIGMOID functions, defaults to 0
                                    cost=10,                                        # Cost parameter for C-SVC, defaults to 1
                                    nu=None)                                        # Nu parameter for NU-SVC, defaults to 0.5

    # Define the parameters for a CART classifier
    elif model_name == 'CART':
        model = ee.Classifier.smileCart(maxNodes=10,                                # Max number of leaf nodes in each tree
                                        minLeafPopulation=1)                        # Only create nodes whose training set contains at least this many points

    else:
        raise NotImplementedError("Only random forest ('RF'), k-NN ('kNN') and support vector machine ('SVM') classifiers are implemented.")

    # Train the model
    trained_model = model.setOutputMode('PROBABILITY').train(features=train_samples, classProperty="class", inputProperties=predictors)

    # Get information on the trained model
    model_info = trained_model.explain()

    # Classify the model on the entire RoI (in probability mode)
    probabilities = training_data.classify(trained_model)

    # Reverse the probabilities if using SVM as the model
    if model_name == 'SVM':
        probabilities = ee.Image(1).subtract(probabilities)

    # Get the model probabilities for just the training and validation samples
    train_probs = train_samples.classify(trained_model)
    val_probs = val_samples.classify(trained_model)

    # Threshold the probability to get a binary classification
    def get_class(feat):
        feat = ee.Feature(feat)
        return feat.set('classification', ee.Number(feat.get('classification')).gte(0.5).toInt())

    # Get the classification of each training and validation sample
    train_preds = train_probs.map(get_class)
    val_preds = val_probs.map(get_class)
    
    # Get the confusion matrix for the training and validation samples
    train_matrix = train_preds.errorMatrix('class', 'classification')
    val_matrix = val_preds.errorMatrix('class', 'classification')

    # # Try to optimise the probability threshold using the validation samples
    # try:

    #     # # Sample the probabilities using the validation points
    #     # probs_collection = probabilities.sampleRegions(collection=val_samples.sort('split').limit(50), properties=['class'], tileScale=tile_scale)

    #     # # Get the probabilities as lists for what was labelled as ecosystem and background separately
    #     # ecosystem_probs = ee.Array(probs_collection.filter(ee.Filter.eq('class', 1)).aggregate_array('classification'))
    #     # background_probs = ee.Array(probs_collection.filter(ee.Filter.eq('class', 0)).aggregate_array('classification'))

    #     # Get a range of confidence thresholds from 50-100%
    #     thresholds = ee.List.sequence(0.5, 1, 0.01)

    #     # # For each confidence threshold, calculate the TP, FP and FN
    #     # true_pos = ee.Array(thresholds.map(lambda thresh: ecosystem_probs.gte(ee.Number(thresh)).reduce(ee.Reducer.sum(), axes=[0]).get([0])))
    #     # false_pos = ee.Array(thresholds.map(lambda thresh: background_probs.gte(ee.Number(thresh)).reduce(ee.Reducer.sum(), axes=[0]).get([0])))
    #     # false_neg = ee.Array(thresholds.map(lambda thresh: ecosystem_probs.lt(ee.Number(thresh)).reduce(ee.Reducer.sum(), axes=[0]).get([0])))

    #     # # Calculate the precision and recall
    #     # precision = true_pos.divide(true_pos.add(false_pos))
    #     # recall = true_pos.divide(true_pos.add(false_neg))

    #     # # Calculate the F1 score
    #     # f1_score = (precision.multiply(recall).multiply(2)).divide(precision.add(recall))

    #     # Classify the model on just the validation samples
    #     val_probabilities = val_samples.classify(trained_model)

    #     # Loop through each threshold
    #     def get_f1_scores(thresh):

    #         # Loop over each feature
    #         def get_class(feat):
    #             feat = ee.Feature(feat)
    #             return ee.Feature(feat.geometry()).copyProperties(feat, ['class']).set('classification', ee.Number(feat.get('classification')).gte(thresh))
            
    #         # Get the classification of each validation sample
    #         val_classifications = val_probabilities.map(get_class)

    #         # Get the confusion matrix for the validation samples
    #         val_matrix = val_classifications.errorMatrix('class', 'classification').array()

    #         # TPs = [1, 1], FPs = [0, 1], TNs = [0, 0], FNs = [1, 0]
    #         precision = val_matrix.get([1, 1]).divide(val_matrix.get([1, 1]).add(val_matrix.get([0, 1])))
    #         recall = val_matrix.get([1, 1]).divide(val_matrix.get([1, 1]).add(val_matrix.get([1, 0])))

    #         return ee.Number(2).multiply((precision.multiply(recall)).divide(precision.add(recall)))

    #     # Get the F1 score for each threshold
    #     f1_scores = thresholds.map(get_f1_scores)

    #     # Find where the F1 score is maximum
    #     max_f1_ind = ee.Array(f1_scores).argmax()

    #     # Find the confidence score that maximises the validation F1 score
    #     thresh = ee.Number(thresholds.get(max_f1_ind.get(0)))
        
    # # Otherwise, just use a threshold of 50%
    # except:
    #     raise ValueError("Optimal threshold could not be found")
    
    return probabilities, model_info, train_matrix, val_matrix

def cluster_ecosystem(roi: dict, ecosystem: Optional[dict], background: Optional[dict], samples: Optional[dict], year: int, window: int, tile_scale: int, scale: int, model_name: str, seed: int = 42) -> Tuple[ee.Image, ee.ConfusionMatrix]:
    """
    Cluster and then classify the ecosystem labelled by the user within their defined RoI.
    """

    # Convert the RoI and ecosystem labels to GEE FeatureCollections
    roi_collection = ee.FeatureCollection(roi)

    # Get a bounding box around the RoI
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
    training_data = training_data.reproject(crs='EPSG:4326', scale=scale).clipToCollection(roi_collection)

    # Define a function for creating a fixed grid of points within a polygon
    def fixed_grid(feat):
        geom = ee.Feature(feat).geometry()
        grids = geom.coveringGrid(proj=geom.projection(), scale=2 * scale)
        return grids.map(lambda grid: ee.Feature(ee.Feature(grid).centroid(maxError=0.1))).filter(ee.Filter.contains(leftValue=geom, rightField='.geo'))

    # If training samples have not been provided, but point/polygon labels have
    if (ecosystem is not None and background is not None):

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

        # Split the classes equally between training and validation sets
        ecosystem_samples = ecosystem_samples.randomColumn(columnName='split', seed=seed)
        background_samples = background_samples.randomColumn(columnName='split', seed=seed)

        # Get the training samples
        train_ecosystem_samples = ecosystem_samples.filter('split <= 0.8')
        train_background_samples = background_samples.filter('split <= 0.8')
        train_samples = train_ecosystem_samples.merge(train_background_samples)

        # Get the validation samples
        val_ecosystem_samples = ecosystem_samples.filter('split > 0.8')
        val_background_samples = background_samples.filter('split > 0.8')
        val_samples = val_ecosystem_samples.merge(val_background_samples)

        # If the user has also provided training samples, merge them
        if samples is not None:

            # Convert the samples to a GEE FeatureCollection and then separate by class
            samples = ee.FeatureCollection(samples)
            user_ecosystem_samples = samples.filter(ee.Filter.eq('class', 1))
            user_background_samples = samples.filter(ee.Filter.eq('class', 0))

            # Split the classes equally between training and validation sets
            user_ecosystem_samples = user_ecosystem_samples.randomColumn(columnName='split', seed=seed)
            user_background_samples = user_background_samples.randomColumn(columnName='split', seed=seed)

            # Get the training samples
            user_train_ecosystem_samples = user_ecosystem_samples.filter('split <= 0.8')
            user_train_background_samples = user_background_samples.filter('split <= 0.8')
            user_train_samples = user_train_ecosystem_samples.merge(user_train_background_samples)
    
            # Get the validation samples
            user_val_ecosystem_samples = user_ecosystem_samples.filter('split > 0.8')
            user_val_background_samples = user_background_samples.filter('split > 0.8')
            user_val_samples = user_val_ecosystem_samples.merge(user_val_background_samples)

            # Merge with the existing training/validation samples
            train_samples = train_samples.merge(user_train_samples)
            val_samples = val_samples.merge(user_val_samples)

    # If training samples have been provided
    elif samples is not None:

        # Convert the samples to a GEE FeatureCollection and then separate by class
        samples = ee.FeatureCollection(samples)
        ecosystem_samples = samples.filter(ee.Filter.eq('class', 1))
        background_samples = samples.filter(ee.Filter.eq('class', 0))

        # Split the classes equally between training and validation sets
        ecosystem_samples = ecosystem_samples.randomColumn(columnName='split', seed=seed)
        background_samples = background_samples.randomColumn(columnName='split', seed=seed)

        # Get the training samples
        train_ecosystem_samples = ecosystem_samples.filter('split <= 0.8')
        train_background_samples = background_samples.filter('split <= 0.8')
        train_samples = train_ecosystem_samples.merge(train_background_samples)

        # Get the validation samples
        user_val_ecosystem_samples = ecosystem_samples.filter('split > 0.8')
        user_val_background_samples = background_samples.filter('split > 0.8')
        val_samples = val_ecosystem_samples.merge(val_background_samples)

    else:
        raise ValueError(f"Neither ecosystem/background labels, or sampled pixel values, have been provided for {year}")

    # Get the predictors from the training data
    predictors = training_data.bandNames()

    # Remove all null samples
    train_samples = train_samples.select(predictors.add('class')).filter(ee.Filter.notNull(predictors.add('class')))
    val_samples = val_samples.select(predictors.add('class')).filter(ee.Filter.notNull(predictors.add('class')))

    # Generate a grid of seed locations for the clusters
    seeds = ee.Algorithms.Image.Segmentation.seedGrid(10)

    # Cluster the composite or AlphaEarth embedding using SNIC
    snic = ee.Algorithms.Image.Segmentation.SNIC(image=training_data, 
                                                seeds=seeds,
                                                compactness=0.1, 
                                                connectivity=8)

    # Remove the cluster band from the SNIC output
    training_data = snic.select(snic.bandNames().removeAll(ee.List(['clusters', 'seeds']))).rename(predictors)

    # Define the parameters for a random forest classifier
    if model_name == 'RF':
        sqrt_features = ee.Number(predictors.length()).pow(0.5).round().int()
        model = ee.Classifier.smileRandomForest(numberOfTrees=500,                  # Number of trees in the entire forest [Recommended value: 100-500]
                                                variablesPerSplit=sqrt_features,    # Max. features to consider for a node split [Recommended value: sqrt(no. features)]
                                                minLeafPopulation=3,                # Min. samples in a leaf to create a node [Recommended value: 1-5]
                                                bagFraction=0.5,                    # Fraction of the training data to be randomly selected per tree [Recommended value: 0.5]
                                                maxNodes=20,                        # Max. nodes in a single tree [Recommended value: 10-30]
                                                seed=seed)                          # Set the random seed for reproducability
    
    # Define the parameters for a k-NN classifier
    elif model_name == 'kNN':
        model = ee.Classifier.smileKNN(k=5,                                         # Number of neighbours for classification
                                    searchMethod='AUTO',                            # Automatically choose search method
                                    metric='EUCLIDEAN')                             # Distance metric to use
        
    # Define the parameters for a support vector machine classifier
    elif model_name == 'SVM':
        model = ee.Classifier.libsvm(decisionProcedure='Voting',                    # Decision procedure to use for classification (Voting or Margin)
                                    svmType='C_SVC',                                # SVM type (only C_SVC and NU_SVC work with probability mode)
                                    kernelType='RBF',                               # Kernel type (LINEAR, POLY, RBF or SIGMOID)
                                    shrinking=True,                                 # Whether to use shrinking heuristics
                                    degree=None,                                    # Degree of polynomial if using POLY for kernelType
                                    gamma=None,                                     # Gamma value in kernel function, defaults to 1/N_features (POLY, RBF and SIGMOID only)
                                    coef0=None,                                     # Coefficient value in POLY and SIGMOID functions, defaults to 0
                                    cost=10,                                      # Cost parameter for C-SVC, defaults to 1
                                    nu=None)                                        # Nu parameter for NU-SVC, defaults to 0.5

    # Define the parameters for a CART classifier
    elif model_name == 'CART':
        model = ee.Classifier.smileCart(maxNodes=10,                                # Max number of leaf nodes in each tree
                                        minLeafPopulation=1)                        # Only create nodes whose training set contains at least this many points

    else:
        raise NotImplementedError("Only random forest ('RF'), k-NN ('kNN') and support vector machine ('SVM') classifiers are implemented.")

    # Train the model
    trained_model = model.setOutputMode('PROBABILITY').train(features=train_samples, classProperty="class", inputProperties=predictors)

    # Get information on the trained model
    model_info = trained_model.explain()

    # Classify the model on the entire RoI (in probability mode)
    probabilities = training_data.classify(trained_model)

    # Reverse the probabilities if using SVM as the model
    if model_name == 'SVM':
        probabilities = ee.Image(1).subtract(probabilities)

    # Get the model probabilities for just the training and validation samples
    train_probs = train_samples.classify(trained_model)
    val_probs = val_samples.classify(trained_model)

    # Threshold the probability to get a binary classification
    def get_class(feat):
        feat = ee.Feature(feat)
        return feat.set('classification', ee.Number(feat.get('classification')).gte(0.5).toInt())

    # Get the classification of each training and validation sample
    train_preds = train_probs.map(get_class)
    val_preds = val_probs.map(get_class)
    
    # Get the confusion matrix for the training and validation samples
    train_matrix = train_preds.errorMatrix('class', 'classification')
    val_matrix = val_preds.errorMatrix('class', 'classification')

    # # Try to optimise the probability threshold using the validation samples
    # try:

    #     # Get a range of confidence thresholds from 50-100%
    #     thresholds = ee.List.sequence(0.5, 1, 0.01)
    
    #     # Classify the model on just the validation samples
    #     val_probabilities = val_samples.classify(trained_model)

    #     # Loop through each threshold
    #     def get_f1_scores(thresh):

    #         # Loop over each feature
    #         def get_class(feat):
    #             feat = ee.Feature(feat)
    #             return ee.Feature(feat.geometry()).copyProperties(feat, ['class']).set('classification', ee.Number(feat.get('classification')).gte(thresh))
            
    #         # Get the classification of each validation sample
    #         val_classifications = val_probabilities.map(get_class)

    #         # Get the confusion matrix for the validation samples
    #         val_matrix = val_classifications.errorMatrix('class', 'classification').array()

    #         # TPs = [1, 1], FPs = [0, 1], TNs = [0, 0], FNs = [1, 0]
    #         precision = val_matrix.get([1, 1]).divide(val_matrix.get([1, 1]).add(val_matrix.get([0, 1])))
    #         recall = val_matrix.get([1, 1]).divide(val_matrix.get([1, 1]).add(val_matrix.get([1, 0])))

    #         return ee.Number(2).multiply((precision.multiply(recall)).divide(precision.add(recall)))

    #     # Get the F1 score for each threshold
    #     f1_scores = thresholds.map(get_f1_scores)

    #     # Find where the F1 score is maximum
    #     max_f1_ind = ee.Array(f1_scores).argmax()

    #     # Find the confidence score that maximises the validation F1 score
    #     thresh = ee.Number(thresholds.get(max_f1_ind.get(0)))
        
    # # Otherwise, just use a threshold of 50%
    # except:
    #     raise ValueError("Optimal threshold could not be found")

    return probabilities, model_info, train_matrix, val_matrix

def get_dissimilarity_index(year: int, roi_geom: ee.Geometry, collection: ee.ImageCollection, ecosystem: Optional[dict], background: Optional[dict], samples: Optional[dict], scale: int, model_name: str, aoa: bool, tile_scale: int = 1, n_predictors: Optional[int] = None, n_folds: int = 3, seed: int = 42) -> ee.Image:
    
    # If using MODIS as the training data
    if int(year) >= 2000 and scale >= 500:

        # Get a composite of MODIS data
        training_data = get_modis_composite(roi_geom=roi_geom,
                                            collection=collection,
                                            tile_scale=tile_scale)

    # If using Landsat as the training data
    elif int(year) < 2017:

        # Get the Landsat collection
        training_data = get_landsat_composite(roi_geom=roi_geom,
                                            collection=collection, 
                                            tile_scale=tile_scale)

    # If using AlphaEarth satellite embeddings as the training data
    elif int(year) >= 2017:

        # Collect the AlphaEarth satellite embeddings and filter by year
        training_data = ee.ImageCollection("GOOGLE/SATELLITE_EMBEDDING/V1/ANNUAL").filterBounds(roi_geom).filterDate(int(year), int(year) + 1).median()

    # Reproject to the chosen scale
    training_data = training_data.reproject(crs='EPSG:4326', scale=scale)

    # Define a function for creating a fixed grid of points within a polygon
    def fixed_grid(feat):
        geom = ee.Feature(feat).geometry()
        grids = geom.coveringGrid(proj=geom.projection(), scale=2 * scale)
        return grids.map(lambda grid: ee.Feature(ee.Feature(grid).centroid(maxError=0.1))).filter(ee.Filter.contains(leftValue=geom, rightField='.geo'))

    # If training samples have not been provided, but point/polygon labels have
    if (ecosystem is not None and background is not None):

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

        # Split the classes equally between training and validation sets
        ecosystem_samples = ecosystem_samples.randomColumn(columnName='split', seed=seed)
        background_samples = background_samples.randomColumn(columnName='split', seed=seed)

        # Get the training samples
        train_ecosystem_samples = ecosystem_samples.filter('split <= 0.8')
        train_background_samples = background_samples.filter('split <= 0.8')
        train_samples = train_ecosystem_samples.merge(train_background_samples)

        # If the user has also provided training samples, merge them
        if samples is not None:

            # Convert the samples to a GEE FeatureCollection and then separate by class
            samples = ee.FeatureCollection(samples)
            user_ecosystem_samples = samples.filter(ee.Filter.eq('class', 1))
            user_background_samples = samples.filter(ee.Filter.eq('class', 0))

            # Split the classes equally between training and validation sets
            user_ecosystem_samples = user_ecosystem_samples.randomColumn(columnName='split', seed=seed)
            user_background_samples = user_background_samples.randomColumn(columnName='split', seed=seed)

            # Get the training samples
            user_train_ecosystem_samples = user_ecosystem_samples.filter('split <= 0.8')
            user_train_background_samples = user_background_samples.filter('split <= 0.8')
            user_train_samples = user_train_ecosystem_samples.merge(user_train_background_samples)

            # Merge with the existing training samples
            train_samples = train_samples.merge(user_train_samples)

    # If training samples have been provided
    elif samples is not None:

        # Convert the samples to a GEE FeatureCollection and then separate by class
        samples = ee.FeatureCollection(samples)
        ecosystem_samples = samples.filter(ee.Filter.eq('class', 1))
        background_samples = samples.filter(ee.Filter.eq('class', 0))

        # Split the classes equally between training and validation sets
        ecosystem_samples = ecosystem_samples.randomColumn(columnName='split', seed=seed)
        background_samples = background_samples.randomColumn(columnName='split', seed=seed)

        # Get the training samples
        train_ecosystem_samples = ecosystem_samples.filter('split <= 0.8')
        train_background_samples = background_samples.filter('split <= 0.8')
        train_samples = train_ecosystem_samples.merge(train_background_samples)

    else:
        raise ValueError(f"Neither ecosystem/background labels, or sampled pixel values, have been provided for {year}")

    # Get the predictors from the training data
    predictors = training_data.bandNames()

    # Randomly shuffle the training data
    train_samples = train_samples.randomColumn('shuffle', seed=seed).sort('shuffle')

    # Remove all null samples
    train_samples = train_samples.select(predictors.add('class')).filter(ee.Filter.notNull(predictors.add('class'))).limit(1000)

    # Define the parameters for a random forest classifier
    if model_name == 'RF':
        sqrt_features = ee.Number(predictors.length()).pow(0.5).round().int()
        model = ee.Classifier.smileRandomForest(numberOfTrees=500,                  # Number of trees in the entire forest [Recommended value: 100-500]
                                                variablesPerSplit=sqrt_features,    # Max. features to consider for a node split [Recommended value: sqrt(no. features)]
                                                minLeafPopulation=3,                # Min. samples in a leaf to create a node [Recommended value: 1-5]
                                                bagFraction=0.5,                    # Fraction of the training data to be randomly selected per tree [Recommended value: 0.5]
                                                maxNodes=20,                        # Max. nodes in a single tree [Recommended value: 10-30]
                                                seed=seed)                          # Set the random seed for reproducability
    
    # Define the parameters for a k-NN classifier
    elif model_name == 'kNN':
        model = ee.Classifier.smileKNN(k=5,                                         # Number of neighbours for classification
                                    searchMethod='AUTO',                            # Automatically choose search method
                                    metric='EUCLIDEAN')                             # Distance metric to use
        
    # Define the parameters for a support vector machine classifier
    elif model_name == 'SVM':
        model = ee.Classifier.libsvm(decisionProcedure='Voting',                    # Decision procedure to use for classification (Voting or Margin)
                                    svmType='C_SVC',                                # SVM type (only C_SVC and NU_SVC work with probability mode)
                                    kernelType='RBF',                               # Kernel type (LINEAR, POLY, RBF or SIGMOID)
                                    shrinking=True,                                 # Whether to use shrinking heuristics
                                    degree=None,                                    # Degree of polynomial if using POLY for kernelType
                                    gamma=None,                                     # Gamma value in kernel function, defaults to 1/N_features (POLY, RBF and SIGMOID only)
                                    coef0=None,                                     # Coefficient value in POLY and SIGMOID functions, defaults to 0
                                    cost=10,                                        # Cost parameter for C-SVC, defaults to 1
                                    nu=None)                                        # Nu parameter for NU-SVC, defaults to 0.5

    # Define the parameters for a CART classifier
    elif model_name == 'CART':
        model = ee.Classifier.smileCart(maxNodes=10,                                # Max number of leaf nodes in each tree
                                        minLeafPopulation=1)                        # Only create nodes whose training set contains at least this many points

    else:
        raise NotImplementedError("Only random forest ('RF'), k-NN ('kNN') and support vector machine ('SVM') classifiers are implemented.")

    # Train the model
    trained_model = model.train(features=train_samples, classProperty="class", inputProperties=predictors)

    # Retrieve the three most important variables
    importances = ee.Dictionary(trained_model.explain().get('importance'))
    important_vars = importances.keys().sort(importances.values()).reverse()
    if n_predictors:
        important_vars = important_vars.slice(0, n_predictors)

    # Work out the relative importance of each variable to use as weights
    weights = importances.values().sort().reverse()
    if n_predictors:
        weights = weights.slice(0, n_predictors)
    weights = ee.Array(weights).divide(ee.Number(weights.reduce(ee.Reducer.sum())))

    # Weight the pixel values according to the variable importances
    weighted_image = training_data.select(important_vars).multiply(ee.Image.constant(weights.toList()))

    # Cast the predictor values to a single list containing all values
    def collate_values(feat):
        values = feat.toArray(important_vars)
        return ee.Feature(None, {'values': values.multiply(weights).toList()})
    weighted_samples = train_samples.map(collate_values)

    # Shuffle the samples
    weighted_samples = weighted_samples.randomColumn('shuffle', seed=seed).sort('shuffle')

    # Convert the collection of lists into a single 2D array ([n_samples, n_predictors])
    samples_list = weighted_samples.aggregate_array('values')
    samples_2d = ee.Array(samples_list)

    # Calculate the Euclidean distances from each pixel to a given training sample in predictor-space
    def get_dist_image(feat):

        # Create a constant multi-band image from this training sample's predictor values
        sample_img = ee.Image.constant(feat.get('values')).rename(important_vars)
        
        # Calculate Euclidean distance
        dist_image = weighted_image.select(important_vars).subtract(sample_img).pow(2).reduce(ee.Reducer.sum()).sqrt()

        return dist_image
    
    # Map over the all training samples and reduce each pixel in the ImageCollection to find the nearest-neighbour
    min_distances = ee.ImageCollection(weighted_samples.map(get_dist_image)).reduce(ee.Reducer.min())#.rename('min_dist')

    # Reshape the training samples array and subtract from itself to get the pairwise distances in predictor-space
    a = samples_2d.reshape([1, weighted_samples.size(), important_vars.length()]).repeat(0, weighted_samples.size())
    b = samples_2d.reshape([weighted_samples.size(), 1, important_vars.length()]).repeat(1, weighted_samples.size())
    nn_distances = a.subtract(b).pow(2).reduce(ee.Reducer.sum(), [2]).sqrt()

    # Convert to a list and flatten in order to remove duplicate distances and zeroes before finding the mean
    nn_distances = nn_distances.toList().flatten().distinct().remove(0)

    # Calculate the mean of the nearest-neighbor distances for all training samples
    d_mean = ee.Number(nn_distances.reduce(ee.Reducer.mean()))

    # Calculate the Dissimilarity Index (DI)
    dissimilarity = min_distances.divide(d_mean).rename('DI')

    # If the Area of Applicability is being plotted
    if aoa:

        # Loop through each fold
        def get_all_outfold_dist(fold):

            # Define the inside-fold filter
            fold_filter = ee.Filter.And(ee.Filter.gte('shuffle', ee.Number(fold).multiply(1 / n_folds)), ee.Filter.lte('shuffle', (ee.Number(fold).add(1)).multiply(1 / n_folds)))

            # Select the fold to calculate distances for
            infold_samples = weighted_samples.filter(fold_filter)
            infold_samples_list = infold_samples.aggregate_array('values')

            # Extract the outside-fold training samples to calculate the distances to
            outfold_samples = weighted_samples.filter(ee.Filter.Not(fold_filter))
            outfold_samples_2d = ee.Array(outfold_samples.aggregate_array('values'))

            # Calculate the outside-fold nearest-neighbour Euclidean distance of a training sample
            def get_outfold_nn_dist(infold_sample):
                infold_sample = ee.Array(infold_sample)
                infold_sample_2d = infold_sample.reshape([1, important_vars.length()]).repeat(0, outfold_samples.size())
                outfold_dist = outfold_samples_2d.subtract(infold_sample_2d).pow(2).reduce(ee.Reducer.sum(), [1]).sqrt()
                return ee.Number(outfold_dist.toList().flatten().sort().get(1)).divide(d_mean)

            # Map over the inside-fold training samples and calculate the distances
            outfold_distances = ee.List(infold_samples_list.map(get_outfold_nn_dist))
            
            return outfold_distances

        # Get the outside-fold nearest neighbour distances for n CV folds
        all_outfold_distances = ee.List.sequence(0, n_folds - 1).map(get_all_outfold_dist).flatten()

        # Sort the distances smallest to largest, and slice between Q1 and Q3 to get the IQR
        distances_Q1_to_Q3 = all_outfold_distances.sort().slice(ee.Number(all_outfold_distances.length()).multiply(0.25).toInt(), ee.Number(all_outfold_distances.length()).multiply(0.75).toInt())
        distances_IQR = ee.Number(distances_Q1_to_Q3.get(-1)).subtract(ee.Number(distances_Q1_to_Q3.get(0)))

        # Get the threshold for the Area of Applicability (AoA)
        aoa_thresh = ee.Number(ee.Number(distances_Q1_to_Q3.get(-1)).add(distances_IQR.multiply(1.5)))

        return dissimilarity.lte(aoa_thresh)

    # If the Dissimilarity Index over the RoI is being plotted
    else:

        return dissimilarity

def get_landsat_collection(year: str, window: int, roi_geom: ee.Geometry, cloud_filter: bool = False) -> ee.ImageCollection:
    """
    Get a Landsat ImageCollection for a given year.
    """

    # Get the start and end years based on the window of assessment (in years either side of the chosen assessment year)
    start_year = int(year) - window if int(year) - window >= 1982 else 1982
    end_year = int(year) + window if int(year) + window <= 2025 else 2025
    
    # Get the start and end date to use for filtering
    start_date = ee.Date.fromYMD(start_year, 1, 1)
    end_date = ee.Date.fromYMD(1 + end_year, 1, 1)

    # Get a binary mask of the RoI
    roi_mask = ee.Image(1).clip(roi_geom)

    # Perform the same steps for all Landsat sensors: spatio-temporal filtering, band renaming, RoI and cloud masking and scaling
    if cloud_filter:
        def collect_landsat(name, bands, mask_fn):
            return ee.ImageCollection(name).filterBounds(roi_geom
                                        ).filterDate(start_date, end_date
                                        ).filter(ee.Filter.And(ee.Filter.gte('CLOUD_COVER_LAND', 0), ee.Filter.lt('CLOUD_COVER_LAND', float(10)))
                                        ).map(lambda img: img.select(bands).rename(['QA', 'SWIR2', 'SWIR1', 'NIR', 'R', 'G', 'B'])
                                        ).map(lambda img: img.updateMask(roi_mask)
                                        ).map(mask_fn
                                        ).map(apply_scale_factors)
    else:
        def collect_landsat(name, bands, mask_fn):
            return ee.ImageCollection(name).filterBounds(roi_geom
                                        ).filterDate(start_date, end_date
                                        ).map(lambda img: img.select(bands).rename(['QA', 'SWIR2', 'SWIR1', 'NIR', 'R', 'G', 'B'])
                                        ).map(lambda img: img.updateMask(roi_mask)
                                        ).map(mask_fn
                                        ).map(apply_scale_factors)

    # Landsat 4 TM (see https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LT04_C02_T1_L2)
    L4_collection = collect_landsat('LANDSAT/LT04/C02/T1_L2', ['QA_PIXEL', 'SR_B7', 'SR_B5', 'SR_B4', 'SR_B3', 'SR_B2', 'SR_B1'], L4to7_mask)

    # Landsat 5 TM (see https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LT05_C02_T1_L2)
    L5_collection = collect_landsat('LANDSAT/LT05/C02/T1_L2', ['QA_PIXEL', 'SR_B7', 'SR_B5', 'SR_B4', 'SR_B3', 'SR_B2', 'SR_B1'], L4to7_mask)

    # Landsat 7 ETM+ without scanline error (see https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LE07_C02_T1_L2)
    L7_collection = collect_landsat('LANDSAT/LE07/C02/T1_L2', ['QA_PIXEL', 'SR_B7', 'SR_B5', 'SR_B4', 'SR_B3', 'SR_B2', 'SR_B1'], L4to7_mask).filterDate(ee.Date('1999-05-28'), ee.Date('2003-05-31'))

    # Landsat 8 OLI (see https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC08_C02_T1_L2)
    L8_collection = collect_landsat('LANDSAT/LC08/C02/T1_L2', ['QA_PIXEL', 'SR_B7', 'SR_B6', 'SR_B5', 'SR_B4', 'SR_B3', 'SR_B2'], L8to9_mask)

    # Landsat 9 OLI-2 (see https://developers.google.com/earth-engine/datasets/catalog/LANDSAT_LC09_C02_T1_L2)
    L9_collection = collect_landsat('LANDSAT/LC09/C02/T1_L2', ['QA_PIXEL', 'SR_B7', 'SR_B6', 'SR_B5', 'SR_B4', 'SR_B3', 'SR_B2'], L8to9_mask)

    # Merge all of the Landsat collections together
    landsat_collection = L4_collection.merge(L5_collection.merge(L7_collection.merge(L8_collection.merge(L9_collection))))
    
    return landsat_collection

def get_landsat_composite(roi_geom: ee.Geometry, tile_scale: int = 1, year: Optional[str] = None, window: Optional[int] = None, collection: Optional[ee.ImageCollection] = None) -> ee.Image:
    """
    Generate a composite of Landsat or Landsat-derived data for a given assessment period and RoI
    """

    # Get the Landsat collection
    if collection is None and (year is not None and window is not None):
        collection = get_landsat_collection(year=year, window=window, roi_geom=roi_geom)
    elif collection is None:
        raise ValueError("ImageCollection or the assessment year and window must be provided")
        
    # Spectral indices
    NDVI_collection = collection.map(lambda image: image.normalizedDifference(['NIR', 'R']))
    EVI_collection = collection.map(lambda image: calculate_evi(image))
    SAVI_collection = collection.map(lambda image: calculate_savi(image))
    NDMI_collection = collection.map(lambda image: image.normalizedDifference(['NIR', 'SWIR1']))
    NDWI_collection = collection.map(lambda image: image.normalizedDifference(['G', 'SWIR1']))
    NDBI_collection = collection.map(lambda image: image.normalizedDifference(['SWIR1', 'NIR']))

    # Take the median over the whole year
    R = collection.select('R').median()
    G = collection.select('G').median()
    B = collection.select('B').median()
    NDVI_med = NDVI_collection.median()
    EVI_med = EVI_collection.median()
    SAVI_med = SAVI_collection.median()
    NDMI_med = NDMI_collection.median()
    NDWI_med = NDWI_collection.median()
    NDBI_med = NDBI_collection.median()

    # Get the standard deviation over the assessment period
    NDVI_std = NDVI_collection.reduce(ee.Reducer.stdDev(), parallelScale=tile_scale)
    EVI_std = EVI_collection.reduce(ee.Reducer.stdDev(), parallelScale=tile_scale)
    SAVI_std = SAVI_collection.reduce(ee.Reducer.stdDev(), parallelScale=tile_scale)
    NDMI_std = NDMI_collection.reduce(ee.Reducer.stdDev(), parallelScale=tile_scale)

    # Digital Elevation Model elevation and slope
    elevation = ee.ImageCollection('projects/sat-io/open-datasets/FABDEM').filterBounds(roi_geom).mosaic().setDefaultProjection('EPSG:3857', None, 30)
    slope = ee.Terrain.slope(elevation)

    # Normalise the images
    R = standardise(R, roi_geom)
    G = standardise(G, roi_geom)
    B = standardise(B, roi_geom)
    NDVI_med = standardise(NDVI_med, roi_geom).rename('NDVI_med')
    NDVI_std = standardise(NDVI_std, roi_geom).rename('NDVI_std')
    EVI_med = standardise(EVI_med, roi_geom).rename('EVI_med')
    EVI_std = standardise(EVI_std, roi_geom).rename('EVI_std')
    SAVI_med = standardise(SAVI_med, roi_geom).rename('SAVI_med')
    SAVI_std = standardise(SAVI_std, roi_geom).rename('SAVI_std')
    NDMI_med = standardise(NDMI_med, roi_geom).rename('NDMI_med')
    NDMI_std = standardise(NDMI_std, roi_geom).rename('NDMI_std')
    NDWI_med = standardise(NDWI_med, roi_geom).rename('NDWI_med')
    NDBI_med = standardise(NDBI_med, roi_geom).rename('NDBI_med')
    elevation = standardise(elevation, roi_geom).rename('elevation')
    slope = standardise(slope, roi_geom).rename('slope')
    
    # Combine the bands to form a composite of different modalities
    composite = ee.Image([R, G, B, 
                        NDVI_med, NDVI_std, 
                        EVI_med, EVI_std, 
                        SAVI_med, SAVI_std, 
                        NDMI_med, NDMI_std, 
                        NDWI_med, NDBI_med, 
                        elevation, slope])

    return composite

def get_modis_collection(year: str, roi_geom: ee.Geometry) -> ee.ImageCollection:

    # Get the start and end dates for filtering the collection
    start_date = ee.Date.fromYMD(int(year), 1, 1)
    end_date = start_date.advance(1, 'year')

    # Collect all MODIS Terra surface reflectance images (daily 500m)
    terra_collection = ee.ImageCollection('MODIS/061/MOD09A1').filterBounds(roi_geom).filterDate(start_date, end_date)

    # Collect all MODIS Aqua surface reflectance images (daily 500m)
    aqua_collection = ee.ImageCollection('MODIS/061/MYD09A1').filterBounds(roi_geom).filterDate(start_date, end_date)

    # Merge the two collections
    modis_collection = terra_collection.merge(aqua_collection)

    # Rename the MODIS bands
    bands = ['sur_refl_b01', 'sur_refl_b02', 'sur_refl_b03', 'sur_refl_b04', 'sur_refl_b06', 'sur_refl_b07']
    modis_collection = modis_collection.map(lambda img: img.select(bands).rename(['R', 'NIR', 'B', 'G', 'SWIR1', 'SWIR2']))

    # Get a binary mask of the RoI
    roi_mask = ee.Image(1).clip(roi_geom)

    # Mask for only pixels within the RoI
    modis_collection = modis_collection.map(lambda img: img.updateMask(roi_mask))

    # Remove any null pixels
    modis_collection = modis_collection.map(lambda img: img.updateMask(img.mask().reduce(ee.Reducer.min())))

    return modis_collection

def get_modis_composite(roi_geom: ee.Geometry, tile_scale: int = 1, year: Optional[str] = None, collection: Optional[ee.ImageCollection] = None) -> ee.Image:

    # Collect all MODIS Terra and Aqua surface reflectance images
    if collection is None and year is not None:
        collection = get_modis_collection(year=year, roi_geom=roi_geom)
    elif collection is None:
        raise ValueError("ImageCollection or the assessment year must be provided")

    # Spectral indices
    NDVI_collection = collection.map(lambda image: image.normalizedDifference(['NIR', 'R']))
    EVI_collection = collection.map(lambda image: calculate_evi(image))
    SAVI_collection = collection.map(lambda image: calculate_savi(image))
    NDMI_collection = collection.map(lambda image: image.normalizedDifference(['NIR', 'SWIR1']))
    NDWI_collection = collection.map(lambda image: image.normalizedDifference(['G', 'SWIR1']))
    NDBI_collection = collection.map(lambda image: image.normalizedDifference(['SWIR1', 'NIR']))

    # Take the median over the whole year
    R_med = collection.select('R').median()
    G_med = collection.select('G').median()
    B_med = collection.select('B').median()
    NDVI_med = NDVI_collection.median()
    EVI_med = EVI_collection.median()
    SAVI_med = SAVI_collection.median()
    NDMI_med = NDMI_collection.median()
    NDWI_med = NDWI_collection.median()
    NDBI_med = NDBI_collection.median()

    # Get the standard deviation over the assessment period
    NDVI_std = NDVI_collection.reduce(ee.Reducer.stdDev(), parallelScale=tile_scale)
    EVI_std = EVI_collection.reduce(ee.Reducer.stdDev(), parallelScale=tile_scale)
    SAVI_std = SAVI_collection.reduce(ee.Reducer.stdDev(), parallelScale=tile_scale)
    NDMI_std = NDMI_collection.reduce(ee.Reducer.stdDev(), parallelScale=tile_scale)

    # Digital Elevation Model elevation and slope
    elevation = ee.ImageCollection('projects/sat-io/open-datasets/FABDEM').filterBounds(roi_geom).mosaic().setDefaultProjection('EPSG:3857', None, 30)
    slope = ee.Terrain.slope(elevation)

    # Normalise the images
    R_med = standardise(R_med, roi_geom)
    G_med = standardise(G_med, roi_geom)
    B_med = standardise(B_med, roi_geom)
    NDVI_med = standardise(NDVI_med, roi_geom).rename('NDVI_med')
    NDVI_std = standardise(NDVI_std, roi_geom).rename('NDVI_std')
    EVI_med = standardise(EVI_med, roi_geom).rename('EVI_med')
    EVI_std = standardise(EVI_std, roi_geom).rename('EVI_std')
    SAVI_med = standardise(SAVI_med, roi_geom).rename('SAVI_med')
    SAVI_std = standardise(SAVI_std, roi_geom).rename('SAVI_std')
    NDMI_med = standardise(NDMI_med, roi_geom).rename('NDMI_med')
    NDMI_std = standardise(NDMI_std, roi_geom).rename('NDMI_std')
    NDWI_med = standardise(NDWI_med, roi_geom).rename('NDWI_med')
    NDBI_med = standardise(NDBI_med, roi_geom).rename('NDBI_med')
    elevation = standardise(elevation, roi_geom).rename('elevation')
    slope = standardise(slope, roi_geom).rename('slope')

    # Combine the bands to form a composite of different modalities
    composite = ee.Image([R_med, G_med, B_med, 
                        NDVI_med, NDVI_std, 
                        EVI_med, EVI_std, 
                        SAVI_med, SAVI_std, 
                        NDMI_med, NDMI_std, 
                        NDWI_med, NDBI_med,
                        elevation, slope])

    return composite

def get_region_of_interest(asset: str, level1: str, level2: Optional[str] = None) -> dict:
    """
    Get a Region of Interest (RoI) from a filtered GEE asset.
    """

    # Depending on which asset was selected, point to it with the right ID and filter by different properties
    asset_id = ROI_ASSETS[asset]['asset_id']
    level1_prop = ROI_ASSETS[asset]['level1_name']
    level2_prop = ROI_ASSETS[asset]['level2_name']
    if "WGSRPD" in asset:
        level1 = int(level1)
            
    # Retrieve the GEE asset as a FeatureCollection
    try:
        asset_collection = ee.FeatureCollection(asset_id)
    except:
        raise EEException("Could not find this GEE asset, please choose a different catalogue, or draw/upload your own RoI")

    # Filter the asset by the selected country or biome
    roi_collection = asset_collection.filter(ee.Filter.eq(level1_prop, level1))
    
    # If a second level has been selected, filter by region or ecoregion
    if level2 and level2_prop:
        roi_collection = roi_collection.filter(ee.Filter.inList(level2_prop, level2))
    
    # Remove any duplicate geometries
    roi_collection = roi_collection.distinct('.geo')

    # Convert the FeatureCollection to a single geometry
    roi_geom = roi_collection.geometry()

    return roi_geom.getInfo()

def get_sentinel_collection(year: str, window: int, roi_geom: ee.Geometry, cloud_filter: bool = False) -> ee.ImageCollection:
    """
    Get a Sentinel-2 ImageCollection for a given year.
    """

    # Get the start and end years based on the window of assessment (in years either side of the chosen assessment year)
    start_year = int(year) - window if int(year) - window >= 2017 else 2017
    end_year = int(year) + window if int(year) + window <= 2025 else 2025
    
    # Get the start and end date to use for filtering
    start_date = ee.Date.fromYMD(start_year, 1, 1)
    end_date = ee.Date.fromYMD(1 + end_year, 1, 1)

    # Get the Sentinel-2 collection and filter by location and date
    s2_collection = ee.ImageCollection('COPERNICUS/S2_SR_HARMONIZED').filterBounds(roi_geom).filterDate(start_date, end_date)

    # If required, apply a stronger cloud cover filter
    if cloud_filter:
        s2_collection = s2_collection.filter(ee.Filter.And(ee.Filter.gte('CLOUDY_PIXEL_PERCENTAGE', 0), ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', float(5))))
    else:
        s2_collection = s2_collection.filter(ee.Filter.And(ee.Filter.gte('CLOUDY_PIXEL_PERCENTAGE', 0), ee.Filter.lt('CLOUDY_PIXEL_PERCENTAGE', float(25))))

    # Get a binary mask of the RoI
    roi_mask = ee.Image(1).clip(roi_geom)

    # Rename bands, and perform RoI and cloud masking
    new_bands = ['SCL', 'SWIR2', 'SWIR1', 'NIR', 'R', 'G', 'B']
    s2_collection = s2_collection.map(lambda im: im.select(['SCL', 'B12', 'B11', 'B8', 'B4', 'B3', 'B2']).rename(new_bands)
                                    ).map(lambda img: img.updateMask(roi_mask)
                                    ).map(S2_mask)
    
    return s2_collection

def get_overlay(asset: str, level1: str, roi: dict, level2: Optional[str] = None) -> dict:
    """
    Get an overlay from a filtered GEE asset.
    """
    
    # Get the RoI as a GEE geometry
    roi_collection = ee.FeatureCollection(roi)
    roi_geom = roi_collection.geometry()
    roi_bounds = roi_geom.bounds()

    # Depending on which asset was selected, point to it with the right ID and filter by different properties
    asset_id = OVERLAY_ASSETS[asset]['asset_id']
    level1_prop = OVERLAY_ASSETS[asset]['level1_name']
    level2_prop = OVERLAY_ASSETS[asset]['level2_name']
    
    # Retrieve the GEE asset as a FeatureCollection
    asset_collection = ee.FeatureCollection(asset_id).filterBounds(roi_bounds)

    # Only get major occurrences for IUCN functional groups
    if asset == 'IUCN':
        asset_collection = asset_collection.filter(ee.Filter.eq('occurrence', 1))

    # Filter the asset by the selected country or biome
    if level1_prop == level2_prop:
        overlay_collection = asset_collection.filter(ee.Filter.stringStartsWith(level2_prop, level1))
    else:
        overlay_collection = asset_collection.filter(ee.Filter.eq(level1_prop, level1))
    
    # If a second level has been selected, filter by region or ecoregion
    if level2 and level2_prop:
        overlay_collection = overlay_collection.filter(ee.Filter.eq(level2_prop, level2))
    
    # Remove any duplicate geometries
    overlay_collection = overlay_collection.distinct('.geo')

    # Clip the overlay to the RoI
    overlay_collection = ee.FeatureCollection(overlay_collection.map(lambda feat: ee.Feature(feat).geometry().simplify(maxError=10).intersection(roi_geom)))

    # Convert the FeatureCollection to a single geometry
    overlay_geom = overlay_collection.geometry()

    return overlay_geom.getInfo()

def L8to9_mask(image: ee.Image) -> ee.Image:
    """
    Landsat 8 and 9 Optical Land Imager (OLI/OLI-2) (Bit 1: dilated cloud, Bit 2: cirrus, Bit 3: cloud, Bit 4: cloud shadow).
    """

    qa_image = image.select('QA')
    dilated_mask = qa_image.bitwiseAnd(1 << 1)
    cirrus_mask = qa_image.bitwiseAnd(1 << 2)
    cloud_mask = qa_image.bitwiseAnd(1 << 3)
    cloud_shadow_mask = qa_image.bitwiseAnd(1 << 4)
    mask = dilated_mask.Or(cirrus_mask).Or(cloud_mask).Or(cloud_shadow_mask)
    null_mask = image.mask().reduce(ee.Reducer.min())

    return image.updateMask(mask.Not()).updateMask(null_mask).copyProperties(image, ['system:time_start', 'CLOUD_COVER_LAND'])

def L4to7_mask(image: ee.Image) -> ee.Image:
    """
    Landsat 4 to 7 Thematic/Enhanced Thematic Mapper (TM/ETM+) (Bit 1: dilated cloud, Bit 3: cloud, Bit 4: cloud shadow).
    """

    qa_image = image.select('QA')
    dilated_mask = qa_image.bitwiseAnd(1 << 1)
    cloud_mask = qa_image.bitwiseAnd(1 << 3)
    shadow_mask = qa_image.bitwiseAnd(1 << 4)
    mask = dilated_mask.Or(cloud_mask).Or(shadow_mask)
    null_mask = image.mask().reduce(ee.Reducer.min())

    return image.updateMask(mask.Not()).updateMask(null_mask).copyProperties(image, ['system:time_start', 'CLOUD_COVER_LAND'])

def L1to5_mask(image: ee.Image) -> ee.Image:
    """
    Landsat 1 to 5 Multispectral Scanner (MSS) cloud mask (Bit 3: cloud).
    """

    qa_image = image.select('QA')
    cloud_mask = qa_image.bitwiseAnd(1 << 3)
    null_mask = image.mask().reduce(ee.Reducer.min())

    return image.updateMask(cloud_mask.Not()).updateMask(null_mask).copyProperties(image, ['system:time_start', 'CLOUD_COVER_LAND'])

def normalise(image: ee.Image, roi_geom: ee.Geometry) -> ee.Image:
    """
    Normalise a image/band to its own minimum and maximum values.
    """
    
    min_max = ee.Dictionary(image.reduceRegion(geometry=roi_geom, reducer=ee.Reducer.minMax(), maxPixels=1e13)).values()
    min_val = min_max.get(1)
    max_val = min_max.get(0)
    
    return image.unitScale(min_val, max_val).toFloat()

def order_by_median(image: ee.Image) -> ee.Image:

    # Calculate the median value for each band of the image
    median_dict = image.reduceRegion(reducer=ee.Reducer.median(), geometry=image.geometry(), maxPixels=1e13)

    # Get a list of the band names in the image
    band_names = ee.List(image.bandNames())

    # Loop over each band name and retrieve the median value
    median_values = ee.List(band_names.map(lambda band: ee.Number(median_dict.get(band))))

    # Construct an image with a single constant value per band (i.e. the median)
    median_image = ee.Image.constant(median_values).rename(band_names)

    # Centre the image on the median value
    centred_image = image.subtract(median_image).abs().multiply(-1)

    return centred_image.copyProperties(image, ['system:time_start', 'CLOUD_COVER_LAND'])

def S2_mask(image: ee.Image) -> ee.Image:
    """
    Sentinel-2 cloud mask.
    """

    SCL_image = image.select('SCL')
    saturated_mask = SCL_image.eq(2)
    cloud_shadow_mask = SCL_image.eq(3)
    cloud_mask = SCL_image.eq(7).Or(SCL_image.eq(8)).Or(SCL_image.eq(9))
    cirrus_mask = SCL_image.eq(10)
    mask = saturated_mask.Or(cloud_shadow_mask).Or(cloud_mask).Or(cirrus_mask)
    null_mask = image.mask().reduce(ee.Reducer.min())

    return image.updateMask(mask.Not()).updateMask(null_mask).divide(10000).copyProperties(image, ['system:time_start', 'CLOUDY_PIXEL_PERCENTAGE'])

def standardise(image: ee.Image, roi_geom: ee.Geometry):
    """
    Standardise an image by it's mean and standard deviation.
    """

    mean = image.reduceRegion(geometry=roi_geom, reducer=ee.Reducer.mean(), maxPixels=1e13).values().get(0)
    std = image.reduceRegion(geometry=roi_geom, reducer=ee.Reducer.stdDev(), maxPixels=1e13).values().get(0)

    return image.subtract(ee.Image.constant(mean)).divide(ee.Image.constant(std))
// Wrap the library in a package function
var LABELLING = (function() {

    // And enable strict mode for this library
    "use strict";

    /************************************************************************
    *                      MODULE LEVEL / GLOBAL VARIABLES
    *************************************************************************/
    
    // Not sure what this is for yet
    var public_interface;

    // Selector variables
    var m_year, m_class_name, m_layer, m_min_val, m_max_val;

    // Map variables
    var m_map, m_vis_layer;

    /************************************************************************
    *                    PRIVATE FUNCTION DECLARATIONS
    *************************************************************************/
    
    // Dataset select methods
    var bind_controls, download_labels, download_samples, collect_data;

    // Map methods
    var update_vis_map, update_vis_layer, create_vis_layer, clear_vis_map, geojsonify;


    /************************************************************************
    *                    PRIVATE FUNCTION IMPLEMENTATIONS
    *************************************************************************/

    // Update the controls based on user interaction
    bind_controls = function() {

        // If the year has been changed
        $('#year').on('change', function() {

            // Get the new year value
            let year = $('#year').val();

            // If the year is now different to the previous one
            if (year !== m_year) {

                // Reassign the year variable
                m_year = year;

                // Log the change to the console
                console.log(`Year changed to: ${m_year}`);

                // Submit the form
                $('#label-form').submit()
            }
        });

        // If the class has been changed
        $('#class').on('change', function() {

            // Get the new class value
            let class_name = $('#class').val();

            // If the class is now different to the previous one
            if (class_name !== m_class_name) {

                // Reassign the class variable
                m_class_name = class_name;

                // Log the change to the console
                console.log(`Class changed to: ${m_class_name}`);

                // Submit the form
                $('#label-form').submit()
            }
        });

        // If the layer has been changed
        $('#layer').on('change', function() {

            // Get the new layer method
            let layer = $('#layer').val();

            // If the layer is now different to the previous one
            if (layer !== m_layer) {

                document.getElementById('min').placeholder = "(Optional) Minimum value"
                document.getElementById('max').placeholder = "(Optional) Maximum value"
                document.getElementById('min').value = ""
                document.getElementById('max').value = ""
                $('#min').trigger('change');
                $('#max').trigger('change');

                // Reassign the layer variable
                m_layer = layer;

                // Log the change to the console
                console.log(`Layer changed to: ${m_layer}`);
            }
        });

        // If the min value has been changed
        $('#min').on('change', function() {

            // Get the new min value method
            let min_val = $('#min').val();

            // If the min value is now different to the previous one
            if (min_val !== m_min_val) {

                // Reassign the min value variable
                m_min_val = min_val;

                // Log the change to the console
                console.log(`Min value changed to: ${m_min_val}`);
            }
        });

        // If the max value has been changed
        $('#max').on('change', function() {

            // Get the new max value method
            let max_val = $('#max').val();

            // If the max value is now different to the previous one
            if (max_val !== m_max_val) {

                // Reassign the max value variable
                m_max_val = max_val;

                // Log the change to the console
                console.log(`Max value changed to: ${m_max_val}`);
            }
        });

        // Clear and load the new layer
        $('#load').on('click', function() {
            
            // Check that the year has been provided
            if (m_year !== ''){

                // Clear the map
                clear_vis_map();

                // Update the map
                update_vis_map();

            } else {
                alert("Please select a year before loading an image")
            };

        });

        // If the download GeoJSON labels button is clicked
        $('#labels').on('click', function() {

            // Check that the year and class are both provided
            if (m_year !== '' && m_class_name !== ''){
            
                // Download the labels currently on-screen
                download_labels();

            } else {
                alert("Please select a year and class before downloading the ecosystem/background labels for this year")
            };

        });

        // If the button for generating the training samples is clicked
        $('#samples').on('click', function() {

            // Check that the year has been provided
            if (m_year !== ''){
                
                // Download the training data
                download_samples();

            } else {
                alert("Please select a year before downloading the training data for this year")
            };

        });

        // If the form is submitted
        window.onload = function() {

            // Check that the year and class are both provided
            if (m_year !== '' && m_class_name !== ''){

                // Clear the map
                clear_vis_map();

                // Update the map
                update_vis_map();

            };

        };
    };

    // Download the current labels on screen
    download_labels = function() {

        // Show the loading icon
        $('#down-loader').addClass('show');

        // Make the AJAX call
        let xhr = $.ajax({
            type: 'POST',
            url: 'get-labels/',
            dataType: 'json',
            data: {geom: JSON.stringify(geojsonify())}
        });

        // Abort the AJAX call if another button is clicked
        $('#load').on('click', function() {
            xhr.abort();
        });
        $('#year').on('change', function() {
            xhr.abort();
        });
        $('#class').on('change', function() {
            xhr.abort();
        });
        $('#labels').on('click', function() {
            xhr.abort();
        });
        $('#samples').on('click', function() {
            xhr.abort();
        });
        window.onload = function() {
            xhr.abort();
        };

        // Check if the AJAX request was aborted
        xhr.fail(function(jqXHR, textStatus) {
            alert("Please wait for the tool to finish loading before clicking other buttons");
            $('#down-loader').removeClass('show');
        });

        // Check the resonse from the AJAX call
        xhr.done(function(response) {

            // If the response was successful
            if (response.success) {

                // Log the response to the console
                console.log(response.labels);

                // Download the output
                var dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(response.labels));
                var downloadAnchorNode = document.createElement('a');
                downloadAnchorNode.setAttribute("href",     dataStr);
                downloadAnchorNode.setAttribute("download", `${m_class_name}_labels_${m_year}.geojson`);
                document.body.appendChild(downloadAnchorNode); // required for firefox
                downloadAnchorNode.click();
                downloadAnchorNode.remove();
            
            // Otherwise, show an error message
            } else {
            
                console.log(response.error)
            
                // Otherwise, show an error message
                alert(response.error);
            
            };

            // Remove the loading icon
            $('#down-loader').removeClass('show');

        });

    };

    // Retrieve and download the training data for a given year
    download_samples = function() {

        // Show the loading icon
        $('#down-loader').addClass('show');

        // Make the AJAX call
        let xhr = $.ajax({
            type: 'POST',
            url: 'get-samples/',
            dataType: 'json',
            data: {year: m_year}
        });

        // Abort the AJAX call if another button is clicked
        $('#load').on('click', function() {
            xhr.abort();
        });
        $('#year').on('change', function() {
            xhr.abort();
        });
        $('#class').on('change', function() {
            xhr.abort();
        });
        $('#labels').on('click', function() {
            xhr.abort();
        });
        $('#samples').on('click', function() {
            xhr.abort();
        });
        window.onload = function() {
            xhr.abort();
        };

        // Check if the AJAX request was aborted
        xhr.fail(function(jqXHR, textStatus) {
            alert("Please wait for the tool to finish loading before clicking other buttons");
            $('#down-loader').removeClass('show');
        });

        // Check the resonse from the AJAX call
        xhr.done(function(response) {

            // If the response was successful
            if (response.success) {

                // Log the response to the console
                console.log(response.samples);

                // Download the output
                var dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(response.samples));
                var downloadAnchorNode = document.createElement('a');
                downloadAnchorNode.setAttribute("href",     dataStr);
                downloadAnchorNode.setAttribute("download", `samples_${m_year}.geojson`);
                document.body.appendChild(downloadAnchorNode); // required for firefox
                downloadAnchorNode.click();
                downloadAnchorNode.remove();
            
            // Otherwise, show an error message
            } else {
            
                console.log(response.error)
            
                // Otherwise, show an error message
                alert(response.error);
            
            };

            // Remove the loading icon
            $('#down-loader').removeClass('show');

        });

    };

    // Collect the current user inputs for the selectors
    collect_data = function() {

        let data = {
            year: m_year,
            class: m_class_name,
            layer: m_layer,
            min: m_min_val,
            max: m_max_val
        };
        return data;

    };

    // Map Methods

    // Update the map using the new user inputs
    update_vis_map = function() {

        // Show the loading icon
        $('#img-loader').addClass('show')

        // Collect the user inputted values
        let data = collect_data();

        // Make the AJAX call
        let xhr = $.ajax({
            type: 'POST',
            url: 'get-labelling-image/',
            dataType: 'json',
            data: data
        });

        // Abort the AJAX call if another button is clicked
        $('#load').on('click', function() {
            xhr.abort();
        });
        $('#year').on('change', function() {
            xhr.abort();
        });
        $('#class').on('change', function() {
            xhr.abort();
        });
        $('#labels').on('click', function() {
            xhr.abort();
        });
        $('#samples').on('click', function() {
            xhr.abort();
        });
        window.onload = function() {
            xhr.abort();
        };

        // Check if the AJAX request was aborted
        xhr.fail(function(jqXHR, textStatus) {
            alert("Please wait for the tool to finish loading before clicking other buttons");
            $('#img-loader').removeClass('show');
        });

        // Check the resonse from the AJAX call
        xhr.done(function(response) {

            // If the response was successful
            if (response.success) {

                // If a warning was raised
                if (response.warning) {
                    
                    console.log(response.warning);

                    // Show the warning on screen
                    alert(response.warning);

                };

                // Log the response to the console
                console.log(response.url);

                // Update the layer on the map
                if (response.url){
                    update_vis_layer(response.url)
                };

                // Reset the min/max values
                if (response.min){
                    document.getElementById('min').placeholder = response.min
                    document.getElementById('min').value = ""
                };
                if (response.max){
                    document.getElementById('max').placeholder = response.max
                    document.getElementById('max').value = ""
                };
            
            } else {
                
                console.log(response.error)
                
                // Otherwise, show an error message
                alert(response.error);

            };

            // Remove the loading icon
            $('#img-loader').removeClass('show');

        });

    };

    // Update the layer on the map
    update_vis_layer = function(url) {

        // If the map layer does not already exist
        if (!m_vis_layer) {

            // Create the data layer
            create_vis_layer(url);
        
        // Otherwise, just reset the URL for the existing layer
        } else {
            m_vis_layer.getSource().setUrl(url);
        }

    };

    // Create the data layer on the map
    create_vis_layer = function(url) {

        // Create the tile source
        let source = new ol.source.XYZ({
            url: url,
            attributions: '<a href="https://earthengine.google.com" target="_">Google Earth Engine</a>'
        });

        // Show a loading icon in the corner of the map to show if tiles are still loading
        source.on('tileloadstart', function(){
            $('#map-loader').addClass('show')
        });
        source.on('tileloadend', function(){
            $('#map-loader').removeClass('show')
        });
        source.on('tileloaderror', function(){
            $('#map-loader').removeClass('show')
        });

        // Create the map layer with a given opacity
        m_vis_layer = new ol.layer.Tile({
            source: source,
            opacity: 1.0
        });

        // Insert below the draw layer (so drawn polygons and points render on top of the data layer).
        m_map.getLayers().insertAt(2, m_vis_layer);

        // Set the legend title for the layer
        if (m_layer === 'visible') {
            m_vis_layer.tethys_legend_title = "Visible Bands";
        } else if (m_layer === 'ndvi') {
            m_vis_layer.tethys_legend_title = 'NDVI - median';
        } else if (m_layer === 'ndvi-std') {
            m_vis_layer.tethys_legend_title = 'NDVI - st. dev.';
        } else if (m_layer === 'evi') {
            m_vis_layer.tethys_legend_title = 'EVI - median';
        } else if (m_layer === 'evi-std') {
            m_vis_layer.tethys_legend_title = 'EVI - st. dev.';
        } else if (m_layer === 'savi') {
            m_vis_layer.tethys_legend_title = 'SAVI - median';
        } else if (m_layer === 'savi-std') {
            m_vis_layer.tethys_legend_title = 'SAVI - st. dev.';
        } else if (m_layer === 'ndmi') {
            m_vis_layer.tethys_legend_title = 'NDMI - median';
        } else if (m_layer === 'ndmi-std') {
            m_vis_layer.tethys_legend_title = 'NDMI - st. dev.';
        } else if (m_layer === 'ndgi') {
            m_vis_layer.tethys_legend_title = 'NDGI - median';
        } else if (m_layer === 'ndgi-std') {
            m_vis_layer.tethys_legend_title = 'NDGI - st. dev.';
        } else if (m_layer === 'ndpi') {
            m_vis_layer.tethys_legend_title = 'NDPI - median';
        } else if (m_layer === 'ndpi-std') {
            m_vis_layer.tethys_legend_title = 'NDPI - st. dev.';
        } else if (m_layer === 'ndwi') {
            m_vis_layer.tethys_legend_title = 'NDWI - median';
        } else if (m_layer === 'ndbi') {
            m_vis_layer.tethys_legend_title = 'NDBI - median';
        } else if (m_layer === 'dem') {
            m_vis_layer.tethys_legend_title = 'Elevation';
        } else if (m_layer === 'slope') {
            m_vis_layer.tethys_legend_title = 'Slope';
        } else if (m_layer === 'chm') {
            m_vis_layer.tethys_legend_title = 'Canopy Height';
        } else if (m_layer === 'npp') {
            m_vis_layer.tethys_legend_title = 'MODIS NPP';
        } else if (m_layer === 'lai') {
            m_vis_layer.tethys_legend_title = 'MODIS LAI';
        } else if (m_layer === 'count') {
            m_vis_layer.tethys_legend_title = 'Coverage';
        } else if (m_layer === 'di') {
            m_vis_layer.tethys_legend_title = 'Dissimilarity';
        } else if (m_layer === 'aoa') {
            m_vis_layer.tethys_legend_title = 'AOA';
        };

        // Update the legend
        TETHYS_MAP_VIEW.updateLegend();

    };

    // Clear the data layer from the map
    clear_vis_map = function() {

        // Only remove if the layer exists
        if (m_vis_layer) {
            m_map.removeLayer(m_vis_layer);
            m_vis_layer = null;
        };

    };

    // Convert the features from the MapView into a GeoJSON GeometryCollection
    geojsonify = function(){

        // Declare variables
        var layers, source, features, geometry_collection;

        // Get the layers from the 
        layers = m_map.getAllLayers()

        // Get the draw layer source
        source = layers[layers.length - 1].getSource()

        // Get the features
        features = source.getFeatures();

        // Check for zero length
        if (features.length == 0){
            return "";
        }

        // Setup a GeometryCollection
        geometry_collection = {'type': 'GeometryCollection',
                                'geometries': []};

        // Loop through the list of features
        features.forEach(function(feature){

            // Declare variables
            var geojson, crs, coordinates, properties,
                geometry, map_crs, geom_type;

            // Clone geometry so transformation doesn't affect features on the map
            geometry = feature.getGeometry().clone();

            // Get the geometry type
            geom_type = geometry.getType();

            // Transform the CRS to standard Lat-Long: EPSG-4326
            map_crs = m_map.getView().getProjection();
            geometry = geometry.transform(map_crs, 'EPSG:4326');

            // Get coordinates
            coordinates = geometry.getCoordinates();

            // Create CRS
            crs = {
                type: 'link',
                properties: {
                    href: 'http://spatialreference.org/ref/epsg/4326/proj4/',
                    type: 'proj4'
                }
            };

            // Formulate GeoJSON
            geojson = {
                type: geom_type,
                coordinates: coordinates,
                properties: {},
                crs: crs
            };

            // Add the geometry to the list in the GeometryCollection
            geometry_collection.geometries.push(geojson);

        });

        return geometry_collection;
        
    };

    /************************************************************************
    *                            PUBLIC INTERFACE
    *************************************************************************/
    
    public_interface = {};

    /************************************************************************
    *                  INITIALISATION / CONSTRUCTOR
    *************************************************************************/
    
    $(function() {
        
        // Initialise Global Variables
        bind_controls();

        // Initialise the year
        m_year = $('#year').val();

        // Initialise the class
        m_class_name = $('#class').val();

        // Initialise the layer
        m_layer = $('#layer').val();

        // Initialise the min value
        m_min_val = $('#min').val();

        // Initialise the max value
        m_max_val = $('#max').val();

        // Initialise the map
        m_map = TETHYS_MAP_VIEW.getMap();

    });

    return public_interface;

// End of package wrapper
}()); 
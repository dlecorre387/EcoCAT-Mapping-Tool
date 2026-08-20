// Wrap the library in a package function
var INPUT = (function() {

    // And enable strict mode for this library
    "use strict";

    /************************************************************************
    *                      MODULE LEVEL / GLOBAL VARIABLES
    *************************************************************************/
    
    // Constants
    var ASSETS;

    // Not sure what this is for yet
    var public_interface;

    // Selector Variables
    var m_asset, m_level1, m_level2, m_map;

    /************************************************************************
    *                    PRIVATE FUNCTION DECLARATIONS
    *************************************************************************/
    
    // Dataset Select Methods
    var bind_controls, update_level1_options, update_level2_options, download_roi, geojsonify;

    /************************************************************************
    *                    PRIVATE FUNCTION IMPLEMENTATIONS
    *************************************************************************/
    
    // Update the controls based on user interaction
    bind_controls = function() {

        // If the asset has been changed
        $('#asset').on('change', function() {

            // Get the new asset value
            let asset = $('#asset').val();

            // If the new asset value is different from the previous one
            if (asset !== m_asset) {

                // Reassign the asset variable
                m_asset = asset;

                // Log the change to the console
                console.log(`GEE asset choice changed to: ${m_asset}`);

                // Update the level 1 options when asset changes
                update_level1_options();
            }
        });

        // If the level 1 has been changed
        $('#level1').on('change', function() {

            // Get the new level 1 value
            let level1 = $('#level1').val();

            // If the new level 1 value is different from the previous one
            if (level1 !== m_level1) {

                // Reassign the level 1 variable
                m_level1 = level1;

                // Log the change to the console
                console.log(`Level 1 choice changed to: ${m_level1}`);

                // Update the level 2 options when level 1 changes
                update_level2_options();
            }
        });

        // If the level 2 has been changed
        $('#level2').on('change', function() {

            // Get the new level 2 value
            let level2 = $('#level2').val();

            // If the new level 2 value is different from the previous one
            if (level2 !== m_level2) {

                // Reassign the level 2 variable
                m_level2 = level2;

                // Log the change to the console
                console.log(`Level 2 choice changed to: ${m_level2}`);

            }
        });

        // If the 'Dowload RoI' button is clicked
        $('#generate').on('click', function() {

            // Download the Region of Interest
            download_roi();

        });

        // If the 'Save Inputs' button is clicked
        $('#submit').on('click', function() {

            // Show the loading icon
            $('#loader').addClass('show');
        });

    };

    // Update the level 1 options if the asset changes
    update_level1_options = function() {

        // Make sure the level 1 box is enabled
        $('#level1').prop("disabled", false);

        // If the asset is not in the list of known assets
        if (!m_asset in ASSETS) {
            alert('Unknown platform selected.');
        };
        
        // Clear level 1 options and set the placeholder
        if (m_asset == "FAO_GAUL_adm0") {
            $('#level1').data('select2-options', {
                placeholder: "Select a country"
            }).empty();
            $('#level2').data('select2-options', {
                placeholder: ""
            }).empty();
        } else if (m_asset == "FAO_GAUL_adm1") {
            $('#level1').data('select2-options', {
                placeholder: "Filter regions by country"
            }).empty();
            $('#level2').data('select2-options', {
                placeholder: "Select a region"
            }).empty();
        } else if (m_asset == "FAO_GAUL_adm2") {
            $('#level1').data('select2-options', {
                placeholder: "Filter regions by country"
            }).empty();
            $('#level2').data('select2-options', {
                placeholder: "Select a region"
            }).empty();
        } else if (m_asset == "ecoregions") {
            $('#level1').data('select2-options', {
                placeholder: "Filter ecoregions by biome"
            }).empty();
            $('#level2').data('select2-options', {
                placeholder: "Select an ecoregion"
            }).empty();
        } else if (m_asset == "WGSRPD_level3") {
            $('#level1').data('select2-options', {
                placeholder: "Filter countries by continent"
            }).empty();
            $('#level2').data('select2-options', {
                placeholder: "Select a botanical country"
            }).empty();
        } else if (m_asset == "WGSRPD_level4") {
            $('#level1').data('select2-options', {
                placeholder: "Filter countries by continent"
            }).empty();
            $('#level2').data('select2-options', {
                placeholder: "Select a botanical country"
            }).empty();
        };

        // Add an empty option to get the placeholder to appear
        let empty_option = new Option();
        $('#level1').append(empty_option);

        // Loop through each available level 1 boundary for the selected asset
        for (var level1 in ASSETS[m_asset]['level1']) {

            // Get the level 1 display name
            var level1name = ASSETS[m_asset]['level1'][level1]['name'];
            
            // Create a new level 1 option
            let new_option = new Option(level1name, level1);

            // Add the boundary to the list of options
            $('#level1').append(new_option);
        }

        // Sort the options alphabetically
        var options = $('#level1 option').toArray();
        options.sort(function(a, b) {
            let aa = a.textContent;
            let bb = b.textContent;
            if (aa.toUpperCase() > bb.toUpperCase()) return 1;
            else if (aa.toUpperCase() < bb.toUpperCase()) return -1;
            else return 0;
        });

        // Clear the options again and readd the sorted options
        $('#level1').select2($('#level1').data('select2-options')).empty().append(options);

        // Trigger a level 2 change event to update the options
        $('#level1').trigger('change');
        update_level2_options();
    };

    // Update the level 2 options if the level 1 changes
    update_level2_options = function() {

        // Make sure the level 2 box is enabled
        if (m_asset != "FAO_GAUL_adm0" && m_level1 != "") {
            $('#level2').prop("disabled", false) 

            // If the asset is not in the list of known assets
            if (!m_asset in ASSETS) {
                alert('Unknown platform selected.');
            };

            // Clear level 2 options
            $('#level2').select2($('#level2').data('select2-options')).empty();

            // Add an empty option to get the placeholder to appear
            let empty_option = new Option();
            $('#level2').append(empty_option);

            // Loop through each available level 2 boundary for the selected asset
            for (var level2 in ASSETS[m_asset]['level1'][m_level1]['level2']) {

                // Get the level 2 display name
                var level2name = ASSETS[m_asset]['level1'][m_level1]['level2'][level2]['name'];

                // Create a new level 2 option
                let new_option = new Option(level2name, level2);

                // Add the boundary to the list of options
                $('#level2').append(new_option);
            }

            // Sort the options alphabetically
            var options = $('#level2 option').toArray();
            options.sort(function(a, b) {
                let aa = a.textContent;
                let bb = b.textContent;
                if (aa.toUpperCase() > bb.toUpperCase()) return 1;
                else if (aa.toUpperCase() < bb.toUpperCase()) return -1;
                else return 0;
            });
            
            // Clear the options again and readd the sorted options
            $('#level2').select2($('#level2').data('select2-options')).empty().append(options);
        } else {
            $('#level2').select2($('#level2').data('select2-options')).empty();
            $('#level2').prop("disabled", true) 
        };
    };

    // Download the Region of Interest on-screen as a GeoJSON
    download_roi = function(){

        // Show the loading icon
        $('#down-loader').addClass('show');

        // Make the AJAX call
        let xhr = $.ajax({
            type: 'POST',
            url: 'get-roi/',
            dataType: 'json',
            data: {geom: JSON.stringify(geojsonify())}
        });

        // Abort the AJAX call if another button is clicked
        $('#generate').on('click', function() {
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
                console.log(response.roi);

                // Download the output
                var dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(response.roi));
                var downloadAnchorNode = document.createElement('a');
                downloadAnchorNode.setAttribute("href",     dataStr);
                downloadAnchorNode.setAttribute("download", "region_of_interest.geojson");
                document.body.appendChild(downloadAnchorNode); // required for firefox
                downloadAnchorNode.click();
                downloadAnchorNode.remove();
            
            // Otherwise, show an error message
            } else {
                
                console.log(response.error)
            
                // Otherwise, show an error message
                alert(response.error);

            }

            // Remove the loading icon
            $('#down-loader').removeClass('show');

        });
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
        if (features.length == 0)
        {
            return "";
        }

        // Setup a GeometryCollection
        geometry_collection = {'type': 'GeometryCollection',
                                'geometries': []};

        // Loop through the list of features
        features.forEach(function(feature){

            // Declare variables
            var geojson, crs, coordinates, geometry, map_crs, geom_type;

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

        // GEE asset info
        ASSETS = $('#assets').data('assets');

        // Initialise the asset choice
        m_asset = $('#asset').val();

        // Initialise the level 1 choice
        m_level1 = $('#level1').val();

        // Initialise the level 2 choice
        m_level2 = $('#level2').val();

        // Get the map
        m_map = TETHYS_MAP_VIEW.getMap()

    });

    return public_interface;

// End of package wrapper
}()); 
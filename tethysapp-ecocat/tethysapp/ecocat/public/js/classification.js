// Wrap the library in a package function
var MAPPING = (function() {

    // And enable strict mode for this library
    "use strict";

    /************************************************************************
    *                      MODULE LEVEL / GLOBAL VARIABLES
    *************************************************************************/
    
    // Constants
    var ASSETS;

    // Not sure what this is for yet
    var public_interface;

    // Selector variables
    var m_year, m_layer, m_asset, m_level1, m_level2, m_min_val, m_max_val;

    // Map variables
    var m_map, m_vis_layer, m_pr_layer, m_cl_layer;

    /************************************************************************
    *                    PRIVATE FUNCTION DECLARATIONS
    *************************************************************************/
    
    // Dataset select methods
    var bind_controls, update_level1_options, update_level2_options, get_metrics, download_export, collect_data;

    // Layer methods
    var update_vis_map, update_vis_layer, create_vis_layer, clear_vis_layer;
    
    // Probability map and classification methods
    var update_cl_map, update_pr_layer, update_cl_layer, create_pr_layer, create_cl_layer, clear_pr_layer, clear_cl_layer;

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
                $('#overlay-form').submit()

            };
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
                console.log(`Layer Changed to: ${m_layer}`);

            };
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
                console.log(`Layer Changed to: ${m_min_val}`);

            };
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
                console.log(`Layer Changed to: ${m_max_val}`);

            };
        });

        // Clear and load the new layer
        $('#load').on('click', function() {

            // Check that the year has been provided
            if (m_year !== ''){
        
                // Clear the layer from the map
                clear_vis_layer();

                // Update the map
                update_vis_map();

            } else {
                alert("Please select a year before loading an image")
            };
        });

        // Display the accuracy of the classification
        $('#metrics').on('click', function() {

            // Check that the year has been provided
            if (m_year !== ''){

                // Get the metrics and show them on screen
                get_metrics();
    
            } else {
                alert("Please select a year before calculating the performance metrics of the classification")
            };
        });

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

            };
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

            };
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

            };
        });

        // If the overlay button has been clicked
        $('#overlay').on('click', function() {

            // Show the loading icon
            $('#loader').addClass('show');

        });

        // If the classify button has been clicked
        $('#classify').on('click', function() {

            // Check that the year has been provided
            if (m_year !== '') {

                // Update the map
                clear_pr_layer();
                clear_cl_layer();
                update_cl_map();

            } else {
                alert("Please select a year before classifying the ecosystem")
            };

        });

        // If the export classification button is clicked
        $('#export').on('click', function() {

            // Check that the year has been provided
            if (m_year !== ''){

                // Check the status of the export, or download if it has finished
                download_export();

            } else {
                alert("Please select a year before exporting the ecosystem map")
            };

        });

        // If the form is submitted
        window.onload = function() {

            // Check that the year has been provided
            if (m_year !== ''){
                
                // Clear the map
                clear_vis_layer();

                // Update the layer
                update_vis_map();

            };
        };
    };

    // Update the level 1 options if the asset changes
    update_level1_options = function() {

        // Make sure the level 1 box is enabled
        $('#level1').prop("disabled", false);

        // If the asset is not in the list of known assets
        if (!m_asset in ASSETS) {
            alert('Unknown platform selected.');
        }

        // Clear level 1 options and set the placeholder
        if (m_asset == "IUCN") {
            $('#level1').data('select2-options', {
                placeholder: "Select a biome"
            }).empty();
        } else if (m_asset == "WDPA") {
            $('#level1').data('select2-options', {
                placeholder: "Filter regions by country"
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

        };

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
        if (m_level1 != "") {

            $('#level2').prop("disabled", false);

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

            };

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
            $('#level2').prop("disabled", true);

        };
    };

    // Display the metrics on screen
    get_metrics = function() {

        // Show the loading icon
        $('#metric-loader').addClass('show');

        // Collect the user inputted values
        let data = collect_data();

        // Make the AJAX call
        let xhr = $.ajax({
            type: 'POST',
            url: 'get-metrics/',
            dataType: 'json',
            data: data
        });

        // Abort the AJAX call if another button is clicked
        $('#year').on('change', function() {
            xhr.abort();
        });
        $('#classify').on('click', function() {
            xhr.abort();
        });
        $('#metrics').on('click', function() {
            xhr.abort();
        });
        $('#load').on('click', function() {
            xhr.abort();
        });
        $('#overlay').on('click', function() {
            xhr.abort();
        });
        $('#export').on('click', function() {
            xhr.abort();
        });
        window.onload = function() {
            xhr.abort();
        };

        // Check if the AJAX request was aborted
        xhr.fail(function(jqXHR, textStatus) {
            alert("Please wait for the tool to finish loading before clicking other buttons");
            $('#metric-loader').removeClass('show');
        });

        // Check the resonse from the AJAX call
        xhr.done(function(response) {
            
            // If the response was successful
            if (response.success) {

                // Log the response to the console
                console.log(response.vars);
                console.log(response.train_P);
                console.log(response.train_R);
                console.log(response.train_F1);
                console.log(response.train_Acc);
                console.log(response.val_P);
                console.log(response.val_R);
                console.log(response.val_F1);
                console.log(response.val_Acc);

                // Show the metrics on screen
                alert(`Most important variables: ${response.vars}\n\nPerformance on Training Samples:\nPrecision: ${response.train_P}\nRecall: ${response.train_R}\nF1: ${response.train_F1}\nAccuracy: ${response.train_Acc}\n\nPerformance on Validation Samples:\nPrecision: ${response.val_P}\nRecall: ${response.val_R}\nF1: ${response.val_F1}\nAccuracy: ${response.val_Acc}`)
            
            // Otherwise, show an error message
            } else {

                console.log(response.error)
                
                // Otherwise, show an error message
                alert(response.error);

            };

            // Remove the loading icon
            $('#metric-loader').removeClass('show');

        });

    };

    // Submit, check the status, or download the exported classification
    download_export = function() {

        // Show the loading icon
        $('#export-loader').addClass('show');

        // Collect the user inputted values
        let data = collect_data();
        
        // Make the AJAX call
        let xhr = $.ajax({
            type: 'POST',
            url: 'get-download/',
            dataType: 'json',
            data: data
        });

        // Abort the AJAX call if another button is clicked
        $('#year').on('change', function() {
            xhr.abort();
        });
        $('#classify').on('click', function() {
            xhr.abort();
        });
        $('#metrics').on('click', function() {
            xhr.abort();
        });
        $('#load').on('click', function() {
            xhr.abort();
        });
        $('#overlay').on('click', function() {
            xhr.abort();
        });
        $('#export').on('click', function() {
            xhr.abort();
        });
        window.onload = function() {
            xhr.abort();
        };

        // Check if the AJAX request was aborted
        xhr.fail(function(jqXHR, textStatus) {
            alert("Please wait for the tool to finish loading before clicking other buttons");
            $('#export-loader').removeClass('show');
        });

        // Check the resonse from the AJAX call
        xhr.done(function(response) {

            // If the response was successful
            if (response.success) {

                // Log the response to the console
                console.log(response.warning);
                console.log(response.url);

                // Show the message on the screen
                alert(response.warning)

                // If the URL has been returned
                if (response.url){

                    // Download the output
                    var downloadAnchorNode = document.createElement('a');
                    downloadAnchorNode.setAttribute("href",     response.url);
                    downloadAnchorNode.setAttribute("download", "classification.tif");
                    document.body.appendChild(downloadAnchorNode); // required for firefox
                    downloadAnchorNode.click();
                    downloadAnchorNode.remove();
                
                }
            
            // Otherwise, show an error message
            } else {

                console.log(response.error)
            
                // Otherwise, show an error message
                alert(response.error);

            };

            // Remove the loading icon
            $('#export-loader').removeClass('show');

        });

    };

    // Collect the current user inputs for the selectors
    collect_data = function() {

        let data = {
            year: m_year,
            layer: m_layer,
            min: m_min_val,
            max: m_max_val
        };

        return data;

    };

    // Map Methods

    // Update the map for visualization
    update_vis_map = function() {

        // Show the loading icon
        $('#img-loader').addClass('show');

        // Collect the user inputted values
        let data = collect_data();

        // Make the AJAX call
        let xhr = $.ajax({
            type: 'POST',
            url: 'get-classification-image/',
            dataType: 'json',
            data: data
        });

        // Abort the AJAX call if another button is clicked
        $('#year').on('change', function() {
            xhr.abort();
        });
        $('#classify').on('click', function() {
            xhr.abort();
        });
        $('#metrics').on('click', function() {
            xhr.abort();
        });
        $('#load').on('click', function() {
            xhr.abort();
        });
        $('#overlay').on('click', function() {
            xhr.abort();
        });
        $('#export').on('click', function() {
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
                console.log(response.min);
                console.log(response.max);

                // Update the data layer on the map
                if (response.url){
                    update_vis_layer(response.url);
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
            
            // Otherwise, show an error message
            } else {

                console.log(response.error)
                
                // Otherwise, show an error message
                alert(response.error);

            };

            // Remove the loading icon
            $('#img-loader').removeClass('show');

        });
    };

    // Update the map using the new user inputs
    update_cl_map = function() {

        // Show the loading icon
        $('#classify-loader').addClass('show');

        // Collect the user inputted values
        let data = collect_data();

        // Make the AJAX call
        let xhr = $.ajax({
            type: 'POST',
            url: 'get-classification/',
            dataType: 'json',
            data: data
        });

        // Abort the AJAX call if another button is clicked
        $('#year').on('change', function() {
            xhr.abort();
        });
        $('#classify').on('click', function() {
            xhr.abort();
        });
        $('#metrics').on('click', function() {
            xhr.abort();
        });
        $('#load').on('click', function() {
            xhr.abort();
        });
        $('#overlay').on('click', function() {
            xhr.abort();
        });
        $('#export').on('click', function() {
            xhr.abort();
        });
        window.onload = function() {
            xhr.abort();
        };

        // Check if the AJAX request was aborted
        xhr.fail(function(jqXHR, textStatus) {
            alert("Please wait for the tool to finish loading before clicking other buttons");
            $('#classify-loader').removeClass('show');
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
                console.log(response.prob_url);
                console.log(response.class_url);

                // Update the layers on the map
                update_pr_layer(response.prob_url);
                update_cl_layer(response.class_url);
            
            // Otherwise, show an error message
            } else {

                console.log(response.error)
                
                // Otherwise, show an error message
                alert(response.error);

            };

            // Remove the loading icon
            $('#classify-loader').removeClass('show');

        });
    };

    // Update the data layer on the map
    update_vis_layer = function(url) {

        // If the map layer does not already exist
        if (!m_vis_layer) {

            // Create the data layer
            create_vis_layer(url);
        
        // Otherwise, just reset the URL for the existing layer
        } else {
            
            m_vis_layer.getSource().setUrl(url);

        };
    };

    // Update the probability layer on the map
    update_pr_layer = function(url) {

        // If the map layer does not already exist
        if (!m_pr_layer) {

            // Create the data layer
            create_pr_layer(url);
        
        // Otherwise, just reset the URL for the existing layer
        } else {

            m_pr_layer.getSource().setUrl(url);

        };
    };

    // Update the data layer on the map
    update_cl_layer = function(url) {

        // If the map layer does not already exist
        if (!m_cl_layer) {

            // Create the data layer
            create_cl_layer(url);
        
        // Otherwise, just reset the URL for the existing layer
        } else {

            m_cl_layer.getSource().setUrl(url);

        };
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
            m_gee_layer.tethys_legend_title = 'Dissimilarity';
        } else if (m_layer === 'aoa') {
            m_gee_layer.tethys_legend_title = 'AOA';
        };

        // Update the legend
        TETHYS_MAP_VIEW.updateLegend();

    };

    // Create the data layer on the map
    create_pr_layer = function(url) {

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
        m_pr_layer = new ol.layer.Tile({
            source: source,
            opacity: 1.0,
            visible: false
        });

        // Insert below the draw layer (so drawn polygons and points render on top of the data layer).
        m_map.getLayers().insertAt(m_map.getAllLayers().length - 1, m_pr_layer);
        m_pr_layer.tethys_legend_title = 'Ecosystem Prob.';
        TETHYS_MAP_VIEW.updateLegend();

    };

    // Create the data layer on the map
    create_cl_layer = function(url) {

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
        m_cl_layer = new ol.layer.Tile({
            source: source,
            opacity: 0.7
        });

        // Insert below the draw layer (so drawn polygons and points render on top of the data layer).
        m_map.getLayers().insertAt(m_map.getAllLayers().length - 1, m_cl_layer);
        m_cl_layer.tethys_legend_title = 'Ecosystem Map';
        TETHYS_MAP_VIEW.updateLegend();

    };

    // Clear the visualisation layer from the map
    clear_vis_layer = function() {

        // Only remove if the layer exists
        if (m_vis_layer) {
            m_map.removeLayer(m_vis_layer);
            m_vis_layer = null;
        };

    };

    // Clear the visualisation layer from the map
    clear_pr_layer = function() {
        
        // Only remove if the layer exists
        if (m_pr_layer) {
            m_map.removeLayer(m_pr_layer);
            m_pr_layer = null;
        };

    };

    // Clear the visualisation layer from the map
    clear_cl_layer = function() {

        // Only remove if the layer exists
        if (m_cl_layer) {
            m_map.removeLayer(m_cl_layer);
            m_cl_layer = null;
        };

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

        // Initialise the year
        m_year = $('#year').val();

        // Initialise the layer
        m_layer = $('#layer').val();

        // Initialise the min value
        m_min_val = $('#min').val();

        // Initialise the max value
        m_max_val = $('#max').val();

        // Initialise the asset choice
        m_asset = $('#asset').val();

        // Initialise the level 1 choice
        m_level1 = $('#level1').val();

        // Initialise the level 2 choice
        m_level2 = $('#level2').val();

        // Initialise the map
        m_map = TETHYS_MAP_VIEW.getMap();
        
    });

    return public_interface;

// End of package wrapper
}()); 
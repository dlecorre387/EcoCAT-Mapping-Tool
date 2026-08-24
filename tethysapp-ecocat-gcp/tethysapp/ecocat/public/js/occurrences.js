// Wrap the library in a package function
var OCCURRENCES = (function() {

    // And enable strict mode for this library
    "use strict";

    /************************************************************************
    *                      MODULE LEVEL / GLOBAL VARIABLES
    *************************************************************************/
    
    // Not sure what this is for yet
    var public_interface;

    // Selector Variables
    var m_year;

    // Map Variables
    var m_map, m_vis_layer, m_cl_layer;

    /************************************************************************
    *                    PRIVATE FUNCTION DECLARATIONS
    *************************************************************************/
    
    // Dataset Select Methods
    var collect_data, bind_controls;

    // Map Methods
    var update_vis_map, update_cl_map, update_vis_layer, update_cl_layer, create_vis_layer, create_cl_layer, clear_vis_layer, clear_cl_layer;

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

                // Clear the map to reset the classification
                clear_cl_layer();
                clear_vis_layer();

                $('#loader').addClass('show');

                // Update the image layer
                update_vis_map();
                update_cl_map();
            };
        });

        // If the classify button has been clicked
        $('#display').on('click', function() {

            $('#loader').addClass('show');
            
            // Update the map
            clear_cl_layer();
            update_cl_map();

        });

        // If the form is submitted
        window.onload = function() {

            if (m_year !== ''){

                $('#loader').addClass('show');
                
                // Clear the map
                clear_cl_layer();
                clear_vis_layer();

                // Update the map
                update_cl_map();
                update_vis_map();

            };
        };
        
    };

    // Collect the current user inputs for the selectors
    collect_data = function() {

        let data = {
            year: m_year
        };

        return data;

    };

    // Map Methods

    // Update the map for visualization
    update_vis_map = function() {

        // Collect the user inputted values
        let data = collect_data();

        // Make the AJAX call to get the image collection URL
        let xhr = $.ajax({
            type: 'POST',
            url: 'get-occurrences-image/',
            dataType: 'json',
            data: data
        });

        // Check the resonse from the AJAX call
        xhr.done(function(response) {

            // If the response was successful
            if (response.success) {

                $('#loader').removeClass('show');

                // Log the response to the console
                console.log(response.url);

                // Update the data layer on the map
                if (response.url){
                    update_vis_layer(response.url);
                };
            
            // Otherwise, show an error message
            } else {

                console.log(response.error)
                
                // Otherwise, show an error message
                alert(response.error);

                // Remove the loading icon
                $('#loader').removeClass('show');

            };
        });
    };

    // Update the map for visualization
    update_cl_map = function() {

        // Collect the user inputted values
        let data = collect_data();

        // Make the AJAX call to get the image collection URL
        let xhr = $.ajax({
            type: 'POST',
            url: 'display-classification/',
            dataType: 'json',
            data: data
        });

        // Check the resonse from the AJAX call
        xhr.done(function(response) {

            // If the response was successful
            if (response.success) {

                $('#loader').removeClass('show');

                // Log the response to the console
                console.log(response.url);

                // Update the data layer on the map
                if (response.url) {
                    update_cl_layer(response.url)
                };
            
            // Otherwise, show an error message
            } else {
                
                console.log(response.error)
                
                // Otherwise, show an error message
                alert(response.error);

                // Remove the loading icon
                $('#loader').removeClass('show');
            }
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

    // Update the data layer on the map
    update_cl_layer = function(url, thresh) {

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

        // Create the map layer with a given opacity
        m_vis_layer = new ol.layer.Tile({
            source: source
        });

        // Insert below the draw layer (so drawn polygons and points render on top of the data layer).
        m_map.getLayers().insertAt(2, m_vis_layer);
        
        // Set the legend title for the layer
        m_vis_layer.tethys_legend_title = "Visible Bands";

        TETHYS_MAP_VIEW.updateLegend();

    };

    // Create the data layer on the map
    create_cl_layer = function(url) {

        // Create the tile source
        let source = new ol.source.XYZ({
            url: url,
            attributions: '<a href="https://earthengine.google.com" target="_">Google Earth Engine</a>'
        });

        // Create the map layer with a given opacity
        m_cl_layer = new ol.layer.Tile({
            source: source
        });

        // Insert below the draw layer (so drawn polygons and points render on top of the data layer).
        m_map.getLayers().insertAt(m_map.getAllLayers().length - 1, m_cl_layer);
        
        // Set the legend title for the layer
        m_cl_layer.tethys_legend_title = "Classif.";

        TETHYS_MAP_VIEW.updateLegend();

    };

    // Clear the visualisation layer from the map
    clear_vis_layer = function() {

        if (m_vis_layer) {

            m_map.removeLayer(m_vis_layer);
            m_vis_layer = null;

        };
    };

    // Clear the visualisation layer from the map
    clear_cl_layer = function() {

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

        // Initialise the year
        m_year = $('#year').val();

        // Initialise the map
        m_map = TETHYS_MAP_VIEW.getMap();

    });

    return public_interface;

// End of package wrapper
}()); 
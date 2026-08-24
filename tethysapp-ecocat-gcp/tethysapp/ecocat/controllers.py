import os
import rasterio
from django.contrib import messages
from django.http import JsonResponse, HttpResponseNotAllowed
from tethys_sdk.gizmos import Button, MapView, MVDraw, MVView, RangeSlider, SelectInput, TextInput, MVLayer, MVLegendClass
from tethys_sdk.routing import controller
from .app import App
from .gee.methods import *
from .gee.overlay_assets import ASSETS as OVERLAY_ASSETS
from .gee.roi_assets import ASSETS as ROI_ASSETS
from .helpers import *
from .model import *

@controller(name='home')
def home(request):
    """
    Controller for the 'Home' page.
    """

    # If the user is going to the next page
    if request.POST:
        if 'next' in request.POST:
            return App.redirect(App.reverse('input'))

    # Button to move onto the next page
    next_button = Button(name='next',
                        display_text="Go To First Step - User Input",
                        icon='chevron-double-right',
                        style='primary',
                        attributes={'form': 'next-form',
                                    'title': "Go to the first step ('User Input')"},
                        submit=True)

    context = {'next_button': next_button}
    
    return App.render(request, 'home.html', context)

@controller(name='input', user_workspace=True, app_workspace=True)
def input(request, app_workspace, user_workspace):
    """
    Controller for the 'User Input' page.
    """

    # Initialise the default values for the years, RoI and RoI selections
    default_years = None
    default_roi = ''
    default_asset = default_level1 = default_level2 = None
    default_buffer = 0

    # Initialise the options
    years_options = [(str(i), str(i)) for i in range(2025, 1982, -1)]
    interval_options = [("Every 10 years", '10'), ("Every 15 years", '15'), ("Every 20 years", '20')]
    asset_options = []
    level1_options = []
    level2_options = []
    
    # Initialise the errors for displaying above the selector
    years_error = ""
    interval_error = ""
    asset_error = ""
    level1_error = ""
    level2_error = ""

    # Make sure to catch any errors to keep the tool running
    try:

        # Define the initial GEE asset options
        asset_options = [(ROI_ASSETS[k]['display'], k) for k in ROI_ASSETS.keys()]

        # Get the user input as a dictionary if it exists
        user_dict = get_user_input(user_workspace.path, 'input')

        # If the user input exists
        if user_dict:

            # Reset the selected year and class
            if user_dict.get('selection', None) is not None:
                user_dict.pop('selection')
                add_user_input(user_workspace.path, user_dict, 'input')

            # Get the assessment years
            years = user_dict.get('years', None)
            if years:
                default_years = years
            else:
                years_error = "Select one or more assessment years"
                interval_error = "OR choose an assessment interval"

            # Get the previous asset, level 1 and level 2 filter choices
            asset = user_dict.get('asset', None)
            level1 = user_dict.get('level1', None)
            level2 = user_dict.get('level2', None)
            buffer = user_dict.get('buffer', None)
            if all([asset, level1]):
                if (level2 is not None and level2 != []) and asset == 'FAO_GAUL_adm0':
                    level2_error = "This box cannot be selected if 'Country Boundaries' has been selected"
                elif (level2 is None or level2 == []) and asset != 'FAO_GAUL_adm0':
                    level2_error = "Please select a region"
                else:
                    default_asset = asset
                    default_level1 = level1
                    default_level2 = level2 if level2 else None
                    default_buffer = buffer
                    level1_options = [(ROI_ASSETS[asset]['level1'][k]['name'], k) for k in ROI_ASSETS[asset]['level1'].keys()]
                    level2_options = [(ROI_ASSETS[asset]['level1'][level1]['level2'][k]['name'], k) for k in ROI_ASSETS[asset]['level1'][level1]['level2'].keys()] if level2 else []
            elif asset:
                level1_error = "Please select a filter or a country"
            elif level1:
                asset_error = "Please select a catalogue"

            # Update the custom settings
            update_settings(user_workspace=user_workspace)
                                                
        # Get the RoI as a GeoJSON if it exists
        roi = get_user_input(user_workspace.path, 'roi')           

        # If RoI is present
        if roi:
            default_roi = roi

        # Check if there has been an error
        if years_error or interval_error or asset_error or level1_error or level2_error:
            raise ValueError("Please fix errors")
        
        # Handle form submission
        if request.POST:

            # If the example user input is to be used
            if 'example' in request.POST:

                # Get the user input as a dictionary if it exists
                user_dict = get_user_input(app_workspace.path, 'input')

                # Get the assessment years and the previous asset, level 1 and level 2 filter choices
                default_years = user_dict['years']
                default_asset = user_dict['asset']
                default_level1 = user_dict['level1']
                default_level2 = user_dict['level2']
                default_buffer = user_dict['buffer']

                # Get the new level 1 and level 2 options
                level1_options = [(ROI_ASSETS[default_asset]['level1'][k]['name'], k) for k in ROI_ASSETS[default_asset]['level1'].keys()]
                level2_options = [(ROI_ASSETS[default_asset]['level1'][default_level1]['level2'][k]['name'], k) for k in ROI_ASSETS[default_asset]['level1'][default_level1]['level2'].keys()] if default_level2 else []
            
                # Get the RoI as a GeoJSON if it exists
                default_roi = get_user_input(app_workspace.path, 'roi')
        
                # Save the user input to the user's workspace
                add_user_input(user_workspace.path, user_dict, 'input')
                add_user_input(user_workspace.path, default_roi, 'roi')

                # Get the ecosystem and background labels for all years
                for y in default_years:
                    add_user_input(user_workspace.path, get_user_input(app_workspace.path, 'ecosystem', y), 'ecosystem', y)
                    add_user_input(user_workspace.path, get_user_input(app_workspace.path, 'background', y), 'background', y)

            # If the user input has been submitted
            elif 'submit' in request.POST:

                # Make sure the buffering is performed by default
                skip_buffer = False
                
                # Retrieve the user input
                years = request.POST.getlist('years', None)
                interval = request.POST.get('interval', None)
                roi = request.POST.get('geometry', None)
                buffer = int(request.POST.get('buffer', None))
                
                # Check whether a RoI has been selected from the list of assets
                asset = request.POST.get('asset', None)
                level1 = request.POST.get('level1', None)
                level2 = request.POST.getlist('level2', None)

                # If a RoI has been selected
                if all([asset, level1]):

                    # Check that the level 2 option has not been selected if using 'Country Boundaries'
                    if (level2 is not None and level2 != []) and asset == 'FAO_GAUL_adm0':
                        level2_error = "This box cannot be selected if 'Country Boundaries' has been selected"

                    # Check that the level 2 option is not missing
                    elif (level2 is None or level2 == []) and asset != 'FAO_GAUL_adm0':
                        level2_error = "Please select a region"

                    else:

                        # Check that the RoI options have been changed since the last user input
                        if (asset != default_asset or level1 != default_level1 or level2 != default_level2) or buffer != default_buffer or roi == '':
                            
                            # Get the RoI from GEE
                            roi = get_region_of_interest(asset=asset, level1=level1, level2=level2)

                            # Reset the default values
                            default_asset = asset
                            default_level1 = level1
                            default_level2 = level2 if level2 else None
                            level1_options = [(ROI_ASSETS[asset]['level1'][k]['name'], k) for k in ROI_ASSETS[asset]['level1'].keys()]
                            level2_options = [(ROI_ASSETS[asset]['level1'][level1]['level2'][k]['name'], k) for k in ROI_ASSETS[asset]['level1'][level1]['level2'].keys()] if level2 else []

                            # Make sure the buffering is performed
                            skip_buffer = False

                        # Otherwise, skip the buffering
                        else:
                            skip_buffer = True

                # Check if not all of the options were properly selected
                elif asset:
                    level1_error = "Please select a filter or a country"
                elif level1:
                    asset_error = "Please select a catalogue"
                
                # Check whether an RoI file was uploaded
                if request.FILES and 'roi-file' in request.FILES:

                    # Handle the upload
                    roi = handle_upload(request, id='roi-file')

                    # Reset the default values
                    default_asset = default_level1 = default_level2 = None

                    # Make sure the buffering is performed
                    skip_buffer = False

                # Validate the assessment year input
                if all([years, interval]) or not any([years, interval]):
                    years_error = "Select one or more assessment years"
                    interval_error = "OR choose an assessment interval"
                else:
                    if years:
                        years = sorted(years, reverse=True)
                    if interval:
                        years = [str(year) for year in range(2025, 1983, -int(interval))]
                    default_years = years

                # Validate the RoI input
                if roi:

                    # Convert the RoI into a FeatureCollection
                    roi, asset_error = check_geom(roi)
                    if len(roi['features']) == 0:
                        roi = ''
                    
                    # If a non-zero buffer is specified
                    if buffer and not skip_buffer:

                        # Buffer the RoI
                        roi, asset_error = check_geom(buffer_collection(roi, buffer))
                        if len(roi['features']) == 0:
                            roi = ''

                    # Check the size of the RoI
                    n_pixels = check_area(roi, int(App.get_custom_setting('scale')))
                    if n_pixels > 5e7:
                        raise ValueError("There are too many pixels within the chosen Region of Interest (RoI). Please use a smaller RoI, or increase the map scale in the settings page.")

                elif not (asset_error or level1_error or level2_error):
                    asset_error = "The Region of Interest (RoI) is required"

                # Reassign the default value for the RoI and buffer
                default_buffer = buffer
                if roi and asset_error == "":
                    default_roi = roi

                # Check if there has been an error
                if years_error or interval_error or asset_error or level1_error or level2_error:
                    raise ValueError("Please fix errors")
                
                # Persist user inputs
                user_dict = {'years': default_years}
                if all([default_asset, default_level1]):
                    user_dict.update({'asset': default_asset, 'level1': default_level1, 'buffer': default_buffer})
                    if default_level2:
                        user_dict['level2'] = default_level2
                add_user_input(user_workspace.path, user_dict, 'input')
                add_user_input(user_workspace.path, roi, 'roi')

                # Remove the ecosystem and background labels
                for file in os.listdir(user_workspace.path):
                    if file.startswith('ecosystem') or file.startswith('background') or file.startswith('samples'):
                        os.remove(os.path.join(user_workspace.path, file))

            # If the user input is to be deleted
            elif 'reset' in request.POST:

                # Reset the default values
                default_years = None
                default_roi = ''
                default_asset = default_level1 = default_level2 = None
                default_buffer = 0

                # Remove the user input
                input_path = os.path.join(user_workspace.path, 'user_input.json')
                if os.path.exists(input_path):
                    os.remove(input_path)

                # Remove the RoI
                roi_path = os.path.join(user_workspace.path, 'region_of_interest.geojson')
                if os.path.exists(roi_path):
                    os.remove(roi_path)

                # Remove the ecosystem and background labels if they exist
                for file in os.listdir(user_workspace.path):
                    if file.startswith('ecosystem') or file.startswith('background') or file.startswith('samples'):
                        os.remove(os.path.join(user_workspace.path, file))

            # If the user is going to the next page
            elif 'next' in request.POST:

                # Check the user input and RoI files exists
                input_path = os.path.join(user_workspace.path, 'user_input.json')
                roi_path = os.path.join(user_workspace.path, 'region_of_interest.geojson')
                if os.path.exists(input_path) and os.path.exists(roi_path):
                    return App.redirect(App.reverse('labelling'))
                else:
                    raise OSError("Not all user input has been submitted yet")

    # Raise any errors as a message
    except Exception as e:
        messages.error(request, f"Error: '{type(e).__name__}: {e}'")

    # Set the drawing options for the map
    drawing_options = MVDraw(controls=['Pan', 'Modify', 'Delete', 'Move', 'Polygon', 'Box'],
                            initial='Pan',
                            initial_features=default_roi,
                            output_format='GeoJSON',
                            line_color='rgba(0, 0, 255, 1.0)',
                            fill_color="rgba(0, 0, 255, 0.1)",
                            legend_title="Region of Interest")
    
    # Centre the initial view of the map on the RoI if it exists
    if default_roi:
        initial_view = MVView(projection='EPSG:4326', extent=calculate_extent(default_roi), maxZoom=18, minZoom=2)

    # Otherwise, centre on RBG Kew
    else:
        initial_view = MVView(projection='EPSG:4326', center=[-0.295, 51.478], zoom=15, maxZoom=18, minZoom=2)

    # Map view for drawing and displaying the chosen RoI
    map_view = MapView(height='100%',
                        width='100%',
                        controls=['ZoomSlider', 'FullScreen'],
                        draw=drawing_options,
                        view=initial_view,
                        basemap=[{'OpenStreetMap': {'control_label': 'Default'}},
                                {'ESRI': {'layer': 'World_Imagery', 'control_label': 'Satellite'}}],
                        legend=True)
    
    # Select options for the GEE asset to use as a RoI
    asset_input = SelectInput(name='asset',
                            display_text="",
                            options=asset_options,
                            initial=default_asset,
                            error=asset_error,
                            select2_options={'placeholder': "e.g. Country Boundaries"},
                            attributes={'form': 'input-form'})

    # Select options for the category of the GEE asset
    level1_input = SelectInput(name='level1',
                            display_text="",
                            options=level1_options,
                            initial=default_level1,
                            error=level1_error,
                            select2_options={'placeholder': ""},
                            disabled=False if default_level1 else True,
                            attributes={'form': 'input-form'})
    
    # Select options for the boundary within the filtered GEE asset
    level2_input = SelectInput(name='level2',
                            display_text="",
                            options=level2_options,
                            initial=default_level2,
                            error=level2_error,
                            select2_options={'placeholder': ""},
                            disabled=False if default_level2 else True,
                            multiple=True,
                            attributes={'form': 'input-form'})
    
    # Range slider for buffer selection
    buffer_input = RangeSlider(name='buffer',
                            display_text="",
                            min=0,
                            max=50,
                            initial=default_buffer,
                            step=1,
                            attributes={'form': 'input-form'})

    # Select options for the assessment year(s)
    years_input = SelectInput(name='years',
                            display_text='',
                            options=years_options,
                            initial=default_years,
                            error=years_error,
                            multiple=True,
                            select2_options={'placeholder': "e.g. 2025, 2005, 1985"},
                            attributes={'form': 'input-form'})

    # Select options for the assessment interval
    interval_input = SelectInput(name='interval',
                            display_text='',
                            options=interval_options,
                            error=interval_error,
                            select2_options={'placeholder': "e.g. Every 20 years"},
                            attributes={'form': 'input-form'})
    
    # Button to delete all current user inputs
    reset_button = Button(name='reset',
                        display_text="Delete Inputs",
                        icon='trash-fill',
                        style='danger',
                        attributes={'form': 'input-form',
                                    'title': "Delete the chosen assessment year(s) and RoI. This will also delete any labelling or ecosystem maps that have been created so far."},
                        submit=True)
    
    # Button to use the example user inputs
    example_button = Button(name='example',
                        display_text="Use Example",
                        icon='box-fill',
                        style='secondary',
                        attributes={'form': 'input-form',
                                    'title': "Use the assessment years, RoI and labels already created for an example ecosystem (the Itigi-Sumbu thicket found in Tanzania)."},
                        submit=True)
    
    # Button to download the RoI as a GeoJSON
    generate_button = Button(name='generate',
                        display_text="Download RoI",
                        icon='cloud-download-fill',
                        style='secondary',
                        attributes={'id': 'generate',
                                    'title': "Download the current RoI shown on screen as a GeoJSON. This can be used to re-upload to the tool in future."})
        
    # Button to save the user inputs
    submit_button = Button(name='submit',
                        display_text="Save Inputs",
                        icon='chevron-right',
                        style='success',
                        attributes={'id': 'submit',
                                    'form': 'input-form',
                                    'title': "Save your chosen Region of Interest (RoI) and assessment year(s) to be able to progress to the next step ('Labelling')."},
                        submit=True)
    
    # Button to move onto the next page
    next_button = Button(name='next',
                        display_text="Go To Next Step - Labelling",
                        icon='chevron-double-right',
                        style='primary',
                        attributes={'form': 'next-form',
                                    'title': "Go to the 'Labelling' page, provided that all user inputs have been saved."},
                        submit=True)

    context = {'map_view': map_view,
            'years_input': years_input,
            'interval_input': interval_input,
            'asset_input': asset_input,
            'level1_input': level1_input,
            'level2_input': level2_input,
            'buffer_input': buffer_input,
            'reset_button': reset_button,
            'example_button': example_button,
            'generate_button': generate_button,
            'submit_button': submit_button,
            'next_button': next_button,
            'assets': ROI_ASSETS}
    
    return App.render(request, 'input.html', context)

@controller(name='labelling', user_workspace=True)
def labelling(request, user_workspace):
    """
    Controller for the 'Labelling' page.
    """

    # Initialise the default year, class, layer and RoI
    default_year = default_class_name = None
    layer = 'visible'
    roi = ''

    # Initialise the year and layer options
    year_options = []
    layer_ids = ['visible', 'ndvi', 'evi', 'savi', 'ndmi', 'ndwi', 'ndbi', 'dem', 'slope', 'count']
    layer_names = ["Visible Image", "NDVI (Vegetation)", "EVI (Enhanced Veg.)","SAVI (Soil-adj. Veg.)", "NDMI (Moisture)", "NDWI (Water)", "NDBI (Urban)", "Elevation (in metres)", "Slope (in degrees)", "Coverage (in images/pixel)"]
    layer_options = list(zip(layer_names, layer_ids))

    # Initialise the error messages
    year_error = ""
    class_error = ""

    # Initialise the drawing options and map layers
    drawing_options = None
    map_layers = []

    # Set the default values of the training samples and ecosystem/background labels
    samples = None
    ecosystem = None
    background = None

    # Make sure to catch any errors to keep the tool running
    try:

        # Get the user input as a dictionary if it exists
        user_dict = get_user_input(user_workspace.path, 'input')

        # Get the RoI as a GeoJSON if it exists
        roi = get_user_input(user_workspace.path, 'roi')

        # Check that all user input has been created
        if user_dict and roi:

            # Create the layer options based on the selected assessment years
            year_options = [(year, year) for year in user_dict['years']]

            # Get the previously selected year and class
            if user_dict.get('selection', None) is not None:
                default_year = user_dict['selection'].get('year', None)
                default_class_name = user_dict['selection'].get('class', None)

            # Otherwise, set the default year if only one year chosen
            elif len(year_options) == 1:
                default_year = user_dict['years'][0]
                if default_class_name is None:
                    default_class_name = 'ecosystem'

            # Update the custom settings
            update_settings(user_workspace=user_workspace)

        else:
            raise OSError("Please complete the 'User Input' page before labelling")

        # Add the RoI to the map
        roi_layer = MVLayer(source='GeoJSON',
                            options=roi,
                            layer_options={'style': {'ol.style.Style': {'stroke': {'ol.style.Stroke': {'color': 'rgba(0, 0, 255, 1.0)', 'width': 2}}}}},
                            legend_title="Region of Interest",
                            legend_extent=calculate_extent(roi),
                            legend_classes=[])
        map_layers.append(roi_layer)

        # Get the ecosystem labels and background labels as GeoJSONs if they exist
        if default_year:
            ecosystem = get_user_input(user_workspace.path, 'ecosystem', default_year)
            background = get_user_input(user_workspace.path, 'background', default_year)

        # Handle form submission
        if request.POST:

            # Retrieve the the year, class, layer and current geometries
            year = request.POST.get('year', None)
            class_name = request.POST.get('class', None)
            layer = request.POST.get('layer', None)
            geoms = request.POST.get('geometry', None)

            # Set the class to ecosystem as long as the year is provided
            if year and not class_name:
                class_name = 'ecosystem'

            # If the labels are to be saved/uploaded
            if 'save' in request.POST:

                # Check that the year has been provided
                if year:

                    # Record the window for collecting images for each assessment year
                    if user_dict.get(str(year), None) is None:
                        user_dict[str(year)] = {}

                    # Retrieve uploaded training samples
                    if request.FILES and 'samples-file' in request.FILES:
                        samples = handle_upload(request, id='samples-file')
                    
                    # If there are training samples
                    if samples is not None:

                        # Remove the classification info from the user input if it exists
                        for key in ['prob_url', 'class_url', 'task']:
                            if user_dict[str(year)].get(key, None) is not None:
                                user_dict[str(year)].pop(key)
                        
                        # Check that the training samples are correct for the given year
                        features = json.loads(f'{samples}')['features']
                        if 'A00' not in features[0]['properties'].keys() and int(year) >= 2017:
                            samples = None
                            raise KeyError("Please only re-use training data that was generated for 2017 or later")
                        elif 'R' not in features[0]['properties'].keys() and int(year) < 2017:
                            samples = None
                            raise KeyError("Please only re-use training data that was generated prior to 2017")

                        # Check the samples are valid
                        samples, samples_error = check_geom(samples)
                        if not samples_error:
                            add_user_input(user_workspace.path, user_dict, 'input')
                            add_user_input(user_workspace.path, samples, 'samples', year)
                        else:
                            raise ValueError(samples_error)

                    # If no samples have been uploaded, check that the class has been provided
                    elif class_name:
                    
                        # Retrieve uploaded labels
                        if request.FILES and 'label-file' in request.FILES:
                            geoms = handle_upload(request, id='label-file')
                        
                        # If there are labels
                        if geoms:

                            # Remove the classification info from the user input if it exists
                            for key in ['prob_url', 'class_url', 'task']:
                                if user_dict[str(year)].get(key, None) is not None:
                                    user_dict[str(year)].pop(key)

                            # Check that the labels are valid
                            geoms, geoms_error = check_geom(geoms)
                            if not geoms_error:
                                add_user_input(user_workspace.path, user_dict, 'input')
                                add_user_input(user_workspace.path, geoms, class_name, year)
                            else:
                                raise ValueError(geoms_error)

                        elif not samples:
                            raise ValueError(f"Please create {class_name} labels or upload training data for both classes")
                        
                    # Show error if the class is missing
                    else:
                        class_error = "Please select a class"
                        raise ValueError("Please fix errors")

                # Show error if the year is missing
                else:
                    year_error = "Please select an assessment period"
                    raise ValueError("Please fix errors")

            # If the labels are to be deleted
            if 'delete' in request.POST:

                # Check that the year has been provided
                if year:

                    # Check that there are labels to delete
                    if user_dict.get(str(year), None) is None:
                        raise OSError(f"No labels have been saved yet for {year}, so none could be deleted")

                    # Remove the training samples if they exist
                    if samples:
                        samples = None
                        samples_path = os.path.join(user_workspace.path, f'samples_{year}.json')
                        if os.path.exists(samples_path):
                            os.remove(samples_path)
                    
                    # Check that the class has been provided
                    elif class_name:
                        
                        # Reset the default geometries
                        if class_name == 'ecosystem':
                            ecosystem = None
                        elif class_name == 'background':
                            background = None

                        # Remove the ecosystem/background labels if they exist
                        labels_path = os.path.join(user_workspace.path, f'{class_name}_labels_{year}.geojson')
                        if os.path.exists(labels_path):
                            os.remove(labels_path)

                    # Show error if the class is missing
                    else:
                        class_error = "Please select a class"
                        raise ValueError("Please fix errors")

                    # Remove the classification info from the user input if it exists
                    for key in ['prob_url', 'class_url', 'task']:
                        if user_dict[str(year)].get(key, None) is not None:
                            user_dict[str(year)].pop(key)

                    # Update the user input
                    add_user_input(user_workspace.path, user_dict, 'input')          
                
                # Show error if the year is missing
                else:
                    year_error = "Please select an assessment period"
                    raise ValueError("Please fix errors")

            # If the year or class have been changed
            if 'year' in request.POST or 'class' in request.POST:

                # Check that the year has been provided
                if year:

                    # Check that the class has been provided
                    if class_name:

                        # If the current year or class have been changed
                        if default_year != year or default_class_name != class_name:

                            # Save the current geometries on screen so that any changes made between saving are not lost
                            if geoms and default_year is not None and default_class_name is not None:

                                # Check that the geometries are valid
                                geoms, geoms_error = check_geom(geoms)
                                if not geoms_error:

                                    # Remove the classification info from the user input if it exists
                                    for key in ['prob_url', 'class_url', 'task']:
                                        if user_dict[str(default_year)].get(key, None) is not None:
                                            user_dict[str(default_year)].pop(key)

                                    # Save the labels for the previous combination of year and class
                                    add_user_input(user_workspace.path, geoms, default_class_name, default_year)

                                else:
                                    raise ValueError(geoms_error)

                            # Update the selected year and class
                            user_dict['selection'] = {'class': class_name, 'year': year}
                            add_user_input(user_workspace.path, user_dict, 'input')

                    # Get the samples as a GeoJSON if they exist
                    samples = get_user_input(user_workspace.path, 'samples', year)

                    # Get the ecosystem labels and background labels as GeoJSONs if they exist
                    ecosystem = get_user_input(user_workspace.path, 'ecosystem', year)
                    background = get_user_input(user_workspace.path, 'background', year)

            # If the user is going to the next page
            if 'next' in request.POST:

                # Check that the ecosystem and background labels or training samples exist
                missing_years = []
                user_files = os.listdir(user_workspace.path)
                for y in user_dict['years']:
                    if not ((f'ecosystem_labels_{y}.geojson' in user_files and f'background_labels_{y}.geojson' in user_files) or f'samples_{y}.geojson' in user_files):
                        missing_years.append(str(y))
                if len(missing_years) > 0:
                    raise KeyError(f"Missing ecosystem and background labels (or re-used training data) for {', '.join(sorted(missing_years))}")

                # Reset the selected year and class
                if user_dict.get('selection', None) is not None:
                    user_dict.pop('selection')
                    add_user_input(user_workspace.path, user_dict, 'input')

                # Otherwise, redirect to the 'Classification' page
                return App.redirect(App.reverse('classification'))

            # Reset the default values
            default_year = year
            default_class_name = class_name

    # Raise any errors
    except Exception as e:
        messages.error(request, f"{type(e).__name__}: {e}")

    # Centre the initial view of the map on the RoI if it exists
    if roi:
        initial_view = MVView(projection='EPSG:4326', extent=calculate_extent(roi), maxZoom=18, minZoom=2)

    # Otherwise, centre on RBG Kew
    else:
        initial_view = MVView(projection='EPSG:4326', center=[-0.295, 51.478], zoom=15, maxZoom=18, minZoom=2)

    # If the ecosystem is being labelled
    if default_class_name == 'ecosystem':
        
        # Set the drawing options
        drawing_options = MVDraw(controls=['Pan', 'Modify', 'Delete', 'Move', 'Point', 'Polygon'],
                                initial='Pan',
                                initial_features=ecosystem,
                                output_format='GeoJSON',
                                line_color='rgba(0, 255, 0, 1.0)',
                                fill_color='rgba(0, 255, 0, 0.1)',
                                point_color='rgba(0, 255, 0, 1.0)',
                                legend_title="Ecosystem")
        
        # Add the background labels as a MapView layer (not editable)
        if background is not None:
            background_layer = MVLayer(source='GeoJSON',
                                    options=background,
                                    layer_options={'style': {'ol.style.Style': {'image': {'ol.style.Circle': {'fill': {'ol.style.Fill': {'color': 'rgba(255, 0, 0, 0.5)'}}, 'radius': 3}},
                                                                                'stroke': {'ol.style.Stroke': {'color': 'rgba(255, 0, 0, 1.0)', 'width': 2}},
                                                                                'fill': {'ol.style.Fill': {'color': 'rgba(255, 0, 0, 0.1)'}}}}},
                                    legend_title="Background",
                                    legend_extent=calculate_extent(background),
                                    legend_classes=[],
                                    editable=False,
                                    feature_selection=False)
            map_layers.insert(0, background_layer)

    # If the background is being labelled
    elif default_class_name == 'background':

        # Set the drawing options
        drawing_options = MVDraw(controls=['Pan', 'Modify', 'Delete', 'Move', 'Point', 'Polygon'],
                                initial='Pan',
                                initial_features=background,
                                output_format='GeoJSON',
                                line_color='rgba(255, 0, 0, 1.0)',
                                fill_color='rgba(255, 0, 0, 0.1)',
                                point_color='rgba(255, 0, 0, 1.0)',
                                legend_title="Background")

        # Add the ecosystem labels as a MapView layer (not editable)
        if ecosystem is not None:
            ecosystem_layer = MVLayer(source='GeoJSON',
                                    options=ecosystem,
                                    layer_options={'style': {'ol.style.Style': {'image': {'ol.style.Circle': {'fill': {'ol.style.Fill': {'color': 'rgba(0, 255, 0, 0.5)'}}, 'radius': 3}},
                                                                                'stroke': {'ol.style.Stroke': {'color': 'rgba(0, 255, 0, 0.5)', 'width': 2}},
                                                                                'fill': {'ol.style.Fill': {'color': 'rgba(0, 255, 0, 0.05)'}}}}},
                                    legend_title="Ecosystem",
                                    legend_extent=calculate_extent(ecosystem),
                                    legend_classes=[],
                                    editable=False,
                                    feature_selection=False)
            map_layers.insert(0, ecosystem_layer)
        
    # Map view for drawing and displaying ecosystem and background labels for each assessment year
    map_view = MapView(height='100%',
                    width='100%',
                    view=initial_view,
                    layers=map_layers,
                    draw=drawing_options,
                    controls=['ZoomSlider', 'FullScreen'],
                    basemap=[{'OpenStreetMap': {'control_label': 'Default'}},
                            {'ESRI': {'layer': 'World_Imagery', 'control_label': 'Satellite'}}],
                    legend=True,
                    attributes={'id': 'map_view'})
    
    # Select options for the assessment year
    year_input = SelectInput(name='year',
                            display_text="",
                            options=year_options,
                            initial=default_year,
                            error=year_error,
                            select2_options={'placeholder': 'Select a year'},
                            attributes={'form': 'label-form',
                                        'id': 'year'})

    # Add some other layer options
    if default_year:

        # Add MODIS Leaf Area Index
        if int(default_year) >= 2000 and ("MODIS Leaf Area Index", 'lai') not in layer_options:
            layer_options.append(("MODIS Leaf Area Index", 'lai'))
        elif ("MODIS Leaf Area Index", 'lai') in layer_ids:
            layer_options.remove(("MODIS Leaf Area Index", 'lai'))

        # Add MODIS Net Primary Production
        if int(default_year) >= 2000 and ("MODIS NPP (in kg/m2)", 'npp') not in layer_options:
            layer_options.append(("MODIS NPP (in kg/m2)", 'npp'))
        elif ("MODIS NPP (in kg/m2)", 'npp') in layer_options:
            layer_options.remove(("MODIS NPP (in kg/m2)", 'npp'))

        # Add the canopy height model for 2019
        if int(default_year) == 2019 and ("Canopy Height (in metres)", 'chm') not in layer_options:
            layer_options.append(("Canopy Height (in metres)", 'chm'))
        elif ("Canopy Height (in metres)", 'chm') in layer_options:
            layer_options.remove(("Canopy Height (in metres)", 'chm'))
    
    # Select options for the remote-sensing layer to be shown on the map
    layer_input = SelectInput(name='layer',
                            display_text="",
                            options=layer_options,
                            initial=layer,
                            attributes={'id': 'layer',
                                        'form': 'label-form'})
    
    # Text input for the minimum value for the visualisation parameters
    min_input = TextInput(name='min',
                        display_text="",
                        initial=None,
                        placeholder="Min value (e.g. -1 for NDVI)",
                        attributes={'id': 'min',
                                    'title': "Some typical minimum values are visible image = 0, spectral indices = -1, slope = 0"})

    # Text input for the maximum value for the visualisation parameters
    max_input = TextInput(name='max',
                        display_text="",
                        initial=None,
                        placeholder="Max value (e.g. 1 for NDVI)",
                        attributes={'id': 'max',
                                    'title': "Some typical maximum values are visible image = 0.3, spectral indices = 1, slope = 90"})
    
    # Select options for the target class being labelled
    class_input = SelectInput(name='class',
                            display_text="",
                            options=[("1: Ecosystem", 'ecosystem'), ("0: Background", 'background')],
                            initial=default_class_name,
                            error=class_error,
                            select2_options={'placeholder': 'Select a target class'},
                            attributes={'form': 'label-form',
                                        'id': 'class'})
    
    # Display how many labels have been made so far
    if ecosystem is not None:
        if ecosystem['features'][0]['geometry']['type'] == 'Polygon':
            ecosystem_str = f"1: {calculate_area(ecosystem)/1e6:0.0f} km^2"
        elif ecosystem['features'][0]['geometry']['type'] == 'Point':
            ecosystem_str = f"1: {len(ecosystem['features'])} pts"
    else:
        ecosystem_str = "1: none saved"
    if background is not None:
        if background['features'][0]['geometry']['type'] == 'Polygon':
            background_str = f" / 0: {calculate_area(background)/1e6:0.0f} km^2"
        elif background['features'][0]['geometry']['type'] == 'Point':
            background_str = f" / 0: {len(background['features'])} pts"
    else:
        background_str = " / 0: none saved"

    # Text input to display the amount of labelling completed for this assessment year
    n_labels = TextInput(name='n_labels',
                        display_text="",
                        initial=None,
                        placeholder=ecosystem_str + background_str if ecosystem is not None or background is not None else "No labels saved yet",
                        disabled=True)
    
    # Text input to display how many training samples have been reused from a previous assessment year
    n_samples = TextInput(name='n_samples',
                        display_text="",
                        initial=None,
                        placeholder=f"{len(samples['features'])} samples" if samples is not None else "No training data uploaded",
                        disabled=True)
    
    # Button to load the map
    load_button = Button(name='load',
                        display_text="Load Image",
                        icon='image-fill',
                        style='secondary',
                        attributes={'id': 'load'})
    
    # Button to delete the labels of the selected class, or any training samples that have been uploaded
    delete_button = Button(name='delete',
                        display_text=f"Delete Labels",
                        icon='trash-fill',
                        style='danger',
                        attributes={'form': 'label-form',
                                    'title': "Delete the labels for your selected assessment year and target class, and any training samples that have been uploaded."},
                        submit=True)
    
    # Button to download the current labels of the selected class
    labels_button = Button(name='labels',
                        display_text=f"Download Labels",
                        icon='cloud-download-fill',
                        style='secondary',
                        attributes={'id': 'labels',
                                    'title': "Download the labels for your selected assessment year and target class as a GeoJSON."})
    
    # Button to download the training data (i.e. the sampled pixel values) from the current assessment year
    samples_button = Button(name='samples',
                        display_text=f"Download Training Data",
                        icon='braces',
                        style='secondary',
                        attributes={'id': 'samples',
                                    'title': "Download the training data used to train this assessment year's model."})
    
    # Button to save the current drawn or uploaded labels or training samples
    save_button = Button(name='save',
                        display_text=f"Save Labels",
                        icon='chevron-right',
                        style='success',
                        attributes={'form': 'label-form',
                                    'title': "Save your uploaded or drawn labels for this particular assessment year and target class."},
                        submit=True)

    # Button to move to the next page
    next_button = Button(name='next',
                        display_text="Go To Next Step - Mapping",
                        icon='chevron-double-right',
                        style='primary',
                        attributes={'form': 'next-form',
                                    'title': "Go to the 'Mapping' page, provided ecosystem and background labels have been created for all assessment years."},
                        submit=True)
    
    context = {'map_view': map_view,
            'year_input': year_input,
            'class_input': class_input,
            'layer_input': layer_input,
            'min_input': min_input,
            'max_input': max_input,
            'n_labels': n_labels,
            'n_samples': n_samples,
            'load_button': load_button,
            'samples_button': samples_button,
            'labels_button': labels_button,
            'delete_button': delete_button,
            'save_button': save_button,
            'next_button': next_button}

    return App.render(request, 'labelling.html', context)

@controller(name='classification', user_workspace=True)
def classification(request, user_workspace):
    """
    Controller for the ecosystem classification results page.
    """

    # Initialise the default year and layer
    year = None
    layer = 'visible'

    # Initialise the error messages
    year_error = ''

    # Initialise the view of the map and the overlay GeoJSON
    overlay = None
    map_layers = []

    # Initialise the year and layer options
    year_options = []
    layer_ids = ['visible', 'ndvi', 'evi', 'savi', 'ndmi', 'ndwi', 'ndbi', 'dem', 'slope', 'count']
    layer_names = ["Visible Image", "NDVI (Vegetation)","EVI (Enhanced Veg.)",  "SAVI (Soil-adj. Veg.)", "NDMI (Moisture)", "NDWI (Water)", "NDBI (Urban)", "Elevation (in metres)", "Slope (in degrees)", "Coverage (in images/pixel)"]
    layer_options = list(zip(layer_names, layer_ids))

    # Make sure to catch any errors to keep the tool running
    try:

        # Define the default and initial GEE asset options
        asset_options = [(OVERLAY_ASSETS[k]['display'], k) for k in OVERLAY_ASSETS.keys()]

        # Get the user input as a dictionary if it exists
        user_dict = get_user_input(user_workspace.path, 'input')

        # Get the RoI as a GeoJSON if it exists
        roi = get_user_input(user_workspace.path, 'roi')

        # Check that all user input has been created
        if user_dict and roi:
            
            # Check that the ecosystem and background labels or training samples exist
            missing_years = []
            user_files = os.listdir(user_workspace.path)
            for y in user_dict['years']:
                if not ((f'ecosystem_labels_{y}.geojson' in user_files and f'background_labels_{y}.geojson' in user_files) or f'samples_{y}.geojson' in user_files):
                    missing_years.append(str(y))
            if len(missing_years) > 0:
                raise KeyError(f"Please complete the 'Labelling' page before attempting mapping")

            # Create the layer options based on the selected assessment years
            year_options = [(year, year) for year in user_dict['years']]

            # Set the default year if only one year chosen
            if len(year_options) == 1:
                year = user_dict['years'][0]

            # Reset the selected year and class
            if user_dict.get('selection', None) is not None:
                user_dict.pop('selection')
                add_user_input(user_workspace.path, user_dict, 'input')

            # Update the custom settings
            update_settings(user_workspace=user_workspace)

        else:
            raise OSError("Please complete the 'User Input' and 'Labelling' pages before attempting mapping")
    
        # Add the RoI to the map
        roi_layer = MVLayer(source='GeoJSON',
                            options=roi,
                            layer_options={'style': {'ol.style.Style': {'stroke': {'ol.style.Stroke': {'color': 'rgba(0, 0, 255, 1.0)', 'width': 2}}}}},
                            legend_title="Region of Interest",
                            legend_extent=calculate_extent(roi))
        map_layers.append(roi_layer)
    
        # Check if labels have been uploaded
        if request.POST:

            # Get the layer and year choices
            layer = request.POST.get('layer', None)
            year = request.POST.get('year', None)

            # If an overlay has been selected
            if 'overlay' in request.POST:

                # Check whether an overlay has been selected from a list of assets
                asset = request.POST.get('asset', None)
                level1 = request.POST.get('level1', None)
                level2 = request.POST.get('level2', None)
                if all([asset, level1, level2]):
                    overlay = get_overlay(asset=asset, 
                                        level1=level1, 
                                        level2=level2,
                                        roi=roi)
                    overlay_name = OVERLAY_ASSETS[asset]['level1'][level1]['level2'][level2]['name']

                # Check whether an overlay file was uploaded
                if request.FILES and 'overlay-file' in request.FILES:
                    overlay = handle_upload(request, id='overlay-file')
                    overlay_name = "Custom Overlay"
                
                # Raise an error if no overlay geometry was received
                if not overlay:
                    raise ValueError("Please select or upload an overlay")
                
                # Check that the overaly geometry is valid
                overlay, overlay_error = check_geom(overlay)
                if len(overlay['features']) == 0:
                    raise ValueError(overlay_error)

                # Add the overlay as an uneditable MVLayer
                overlay_layer = MVLayer(source='GeoJSON',
                                    options=overlay,
                                    layer_options={'style': {'ol.style.Style': {'image': {'ol.style.Circle': {'fill': {'ol.style.Fill': {'color': 'rgba(255, 0, 255, 1.0)'}}, 'radius': 5}},
                                                                                'stroke': {'ol.style.Stroke': {'color': 'rgba(255, 0, 255, 1.0)', 'width': 3}},
                                                                                'fill': {'ol.style.Fill': {'color': 'rgba(255, 0, 255, 0.5)'}}}}},
                                    legend_title=overlay_name,
                                    legend_extent=calculate_extent(overlay),
                                    legend_classes=[],
                                    editable=False,
                                    feature_selection=False)
                map_layers.insert(0, overlay_layer)

    # Raise any errors
    except Exception as e:
        messages.error(request, f"Error: '{type(e).__name__}: {e}'")

    # Centre the initial view of the map on the RoI if it exists
    if roi:
        initial_view = MVView(projection='EPSG:4326', extent=calculate_extent(roi), maxZoom=18, minZoom=2)

    # Otherwise, centre on RBG Kew
    else:
        initial_view = MVView(projection='EPSG:4326', center=[-0.295, 51.478], zoom=15, maxZoom=18, minZoom=2)

    # Map view for displaying the classification results and overlays
    map_view = MapView(height='100%',
                    width='100%',
                    layers=map_layers,
                    controls=['ZoomSlider', 'FullScreen'],
                    basemap=[{'OpenStreetMap': {'control_label': 'Default'}},
                            {'ESRI': {'layer': 'World_Imagery', 'control_label': 'Satellite'}}],
                    view=initial_view,
                    legend=True)
    
    # Select options for the assessment year
    year_input = SelectInput(name='year',
                            display_text="",
                            options=year_options,
                            initial=year,
                            error=year_error,
                            select2_options={'placeholder': 'Select a year'},
                            attributes={'id': 'year',
                                    'form': 'overlay-form'})

    # Add some other layer options
    if year:

        # Add MODIS Leaf Area Index
        if int(year) >= 2000 and ("MODIS Leaf Area Index", 'lai') not in layer_options:
            layer_options.append(("MODIS Leaf Area Index", 'lai'))
        elif ("MODIS Leaf Area Index", 'lai') in layer_ids:
            layer_options.remove(("MODIS Leaf Area Index", 'lai'))

        # Add MODIS Net Primary Production
        if int(year) >= 2000 and ("MODIS NPP (in kg/m2)", 'npp') not in layer_options:
            layer_options.append(("MODIS NPP (in kg/m2)", 'npp'))
        elif ("MODIS NPP (in kg/m2)", 'npp') in layer_options:
            layer_options.remove(("MODIS NPP (in kg/m2)", 'npp'))

        # Add the canopy height model for 2019
        if int(year) == 2019 and ("Canopy Height (in metres)", 'chm') not in layer_options:
            layer_options.append(("Canopy Height (in metres)", 'chm'))
        elif ("Canopy Height (in metres)", 'chm') in layer_options:
            layer_options.remove(("Canopy Height (in metres)", 'chm'))
    
    # Select options for the remote-sensing layer to be shown on the map
    layer_input = SelectInput(name='layer',
                            display_text="",
                            options=layer_options,
                            initial=layer,
                            attributes={'id': 'layer',
                                    'form': 'overlay-form'})
    
    # Text input for the minimum value for the visualisation parameters
    min_input = TextInput(name='min',
                        display_text="",
                        initial=None,
                        placeholder="Min value (e.g. -1 for NDVI)",
                        attributes={'id': 'min',
                                    'title': "Some typical minimum values are visible image = 0, spectral indices = -1, slope = 0"})

    # Text input for the maximum value for the visualisation parameters
    max_input = TextInput(name='max',
                        display_text="",
                        initial=None,
                        placeholder="Max value (e.g. 1 for NDVI)",
                        attributes={'id': 'max',
                                    'title': "Some typical maximum values are visible image = 0.3, spectral indices = 1, slope = 90"})

    # Button to load the image on the map
    load_button = Button(name='load',
                        display_text="Load Image",
                        icon='image-fill',
                        style='secondary',
                        attributes={'id': 'load'})
    
    # Select options for the GEE asset to use as an overlay
    asset_input = SelectInput(name='asset',
                            display_text="",
                            options=asset_options,
                            select2_options={'placeholder': 'Select an Earth Engine asset'},)

    # Select options for the level 1 filter (e.g. country or biome)
    level1_input = SelectInput(name='level1',
                            display_text="",
                            options=[],
                            select2_options={'placeholder': ''},
                            disabled=True)
    
    # Select options for the level 2 option (e.g. protected area or IUCN typology category)
    level2_input = SelectInput(name='level2',
                            display_text="",
                            options=[],
                            select2_options={'placeholder': ''},
                            disabled=True)
    
    # Button to display an overlay on the map
    overlay_button = Button(name='overlay',
                        display_text="Load Overlay",
                        icon='stack',
                        style='secondary',
                        attributes={'form': 'overlay-form',
                                    'id':'overlay'},
                        submit=True)
        
    # Button to quickly return to the labelling page
    label_button = Button(name='labelling',
                        display_text='Make More Labels',
                        icon='geo-fill',
                        style='secondary',
                        href=App.reverse('labelling'))

    # Button to classify the RoI and display the result on the map
    classify_button = Button(name='classify',
                        display_text=f"Classify Ecosystem",
                        icon='gear-wide-connected',
                        style='success',
                        attributes={'id': 'classify'})
    
    # Button to display the validation metrics for the classification
    metrics_button = Button(name='metrics',
                        display_text="Show Accuracy",
                        icon='bar-chart-line-fill',
                        style='warning',
                        attributes={'id': 'metrics'})
    
    # Button to export the classification
    export_button = Button(name='export',
                        display_text="Export Map",
                        icon='cloud-upload-fill',
                        style='primary',
                        attributes={'id': 'export'})

    context = {'year_input': year_input,
            'layer_input': layer_input,
            'min_input': min_input,
            'max_input': max_input,
            'load_button': load_button,
            'asset_input': asset_input,
            'level1_input': level1_input,
            'level2_input': level2_input,
            'overlay_button': overlay_button,
            'label_button': label_button,
            'classify_button': classify_button,
            'metrics_button': metrics_button,
            'export_button': export_button,
            'map_view': map_view,
            'assets': OVERLAY_ASSETS}

    return App.render(request, 'classification.html', context)

@controller(name='occurrences', user_workspace=True)
def occurrences(request, user_workspace):
    """
    Controller for the GBIF occurrences page.
    """

    # Initialise the year, occurrences and taxon key
    year = None
    occ_geojson = None
    taxon_key = None
    taxon_name = None
    conf = None

    # Initialise the error messages
    year_error = ""
    taxon_error = ""

    # Update App settings
    update_settings(user_workspace)

    # Make sure to catch any errors to keep the tool running
    try:

        # Check the user input exists
        if not os.path.exists(os.path.join(user_workspace.path, 'user_input.json')):
            year_options = []
            roi_geom = ''
            messages.error(request, "Please complete the user input page before progressing")

        else:

            # Get the user input and RoI
            user_dict = get_user_input(user_workspace.path)
            year_options = [(year, year) for year in user_dict['years']]
            roi_geom = user_dict['roi']

            # Check that there is a RoI to display
            if roi_geom:

                # Calculate the extent of the RoI
                roi_extent = calculate_extent(roi_geom)

                # Construct the default view
                initial_view = MVView(projection='EPSG:4326',
                                    extent=roi_extent,
                                    maxZoom=18,
                                    minZoom=2)
                
                # Add the RoI to the map
                roi_layer = MVLayer(source='GeoJSON',
                                    options=roi_geom,
                                    layer_options={'style': {'ol.style.Style': {'stroke': {'ol.style.Stroke': {'color': 'rgba(0, 0, 255, 1.0)', 'width': 2}}}}},
                                    legend_title="Region of Interest",
                                    legend_extent=roi_extent,
                                    legend_classes=[MVLegendClass('polygon', 'Boundary', fill='rgba(0, 0, 255, 0.0)', stroke='rgba(0, 0, 255, 1.0)')])
                layers = [roi_layer]
            
            # Set the initial features and view of the RoI map (centre on RBG, Kew)
            else:
                layers = []
                initial_view = MVView(projection='EPSG:4326',
                                    center=[-0.295, 51.478],
                                    zoom=15,
                                    maxZoom=18,
                                    minZoom=2)

            # Handle form submission
            if request.POST:

                # Get the year
                year = request.POST.get('year', None)

                # If the user has clicked to look-up the taxon key
                if 'lookup' in request.POST:

                    # Get the user input
                    rank = request.POST.get('rank', None)
                    name = request.POST.get('name', None)
                    
                    # Get the taxon key
                    taxon_key, taxon_name, conf = get_taxon_key(name=name, rank=rank)

                # If the user has clicked to display the occurrences
                elif 'load' in request.POST:

                    # Get the user input
                    taxon_key = request.POST.get('taxon', None)
                    basis = request.POST.get('basis', None)

                    # Validate user inputs
                    if not taxon_key:
                        taxon_error = "Taxon key is required"
                        messages.error(request, "Please fix errors")
                    
                    else:
                        
                        # Get the occurrences
                        occ_geojson = get_gbif_occurrences(user_dict, year, taxon_key, basis)
                        
                        if len(occ_geojson['features']) == 0:
                            messages.error(request, "No occurrences found within the RoI with sufficient coordinate uncertainty and license")
                        else:
                            occ_layer = MVLayer(source='GeoJSON',
                                                options=occ_geojson,
                                                layer_options={'style': {'ol.style.Style': {'image': {'ol.style.Circle': {'fill': {'ol.style.Fill': {'color': 'rgba(255, 0, 0, 1.0)'}}, 'radius': 5}}}}},
                                                legend_title="Occurrences",
                                                legend_extent=calculate_extent(occ_geojson),
                                                legend_classes=[MVLegendClass('point', 'All occurrences', fill='rgba(255, 0, 0, 1.0)')])
                            layers.append(occ_layer)

    # Raise any errors
    except Exception as e:
        messages.error(request, f"Error: '{type(e).__name__}: {e}'")

    # Define the map view for displaying occurrences
    map_view = MapView(height='100%',
                    width='100%',
                    controls=['ZoomSlider', 'FullScreen'],
                    view=initial_view,
                    layers=layers,
                    basemap=[{'OpenStreetMap': {'control_label': 'Default'}},
                            {'ESRI': {'layer': 'World_Imagery', 'control_label': 'Satellite'}}],
                    legend=True)
    
    # Add a dropdown to select the specific assessment period
    year_input = SelectInput(name='year',
                            display_text="",
                            options=year_options,
                            initial=year,
                            error=year_error,
                            select2_options={'placeholder': 'Select a year'},
                            attributes={'form': 'gbif-form',
                                        'id': 'year'})
    
    # Retrieve the input from the taxon key search bar
    name_input = TextInput(name='name',
                        display_text="",
                        initial=None,
                        placeholder="e.g. 'Calluna vulgaris (L.) Hull'",
                        attributes={'form': 'key-form'})
    
    # Retrieve the taxonomic rank
    rank_input = SelectInput(name='rank',
                            display_text="",
                            options=[("Kingdom", 'KINGDOM'),
                                    ("Phylum", 'PHYLUM'),
                                    ("Class", 'CLASS'), 
                                    ("Order", 'ORDER'), 
                                    ("Family", 'FAMILY'), 
                                    ("Genus", 'GENUS'),
                                    ("Species", 'SPECIES'), 
                                    ("Variety", 'VARIETY')],
                            select2_options={'placeholder': 'Select a rank'},
                            attributes={'form': 'key-form'})
    
    # Retrieve the taxon key
    taxon_input = TextInput(name='taxon',
                            display_text=f"{taxon_name} - {conf:0.0f}%" if taxon_name else "",
                            initial=taxon_key if taxon_name else None,
                            placeholder='e.g. 2882482',
                            error=taxon_error,
                            attributes={'form': 'gbif-form'})
    
    # Retrieve the basis of record
    basis_input = SelectInput(name='basis',
                            display_text="",
                            options=[("Fossil specimen", 'FOSSIL_SPECIMEN'), 
                                    ("Human observation", 'HUMAN_OBSERVATION'), 
                                    ("Living specimen", 'LIVING_SPECIMEN'), 
                                    ("Machine observation", 'MACHINE_OBSERVATION'), 
                                    ("Material citation", 'MATERIAL_CITATION'), 
                                    ("Observation", 'OBSERVATION'), 
                                    ("Occurence", 'OCCURRENCE'), 
                                    ("Preserved specimen", 'PRESERVED_SPECIMEN')],
                            select2_options={'placeholder': 'Select an observation type'},
                            attributes={'form': 'gbif-form'})

    # Add a button to look up the taxon key
    key_button = Button(name='lookup',
                        display_text="Look-up Key",
                        icon='key-fill',
                        style='secondary',
                        attributes={'form': 'key-form'},
                        submit=True)

    # Add a button to load the occurrences on the map
    load_button = Button(name='load',
                        display_text="Load Occurrences",
                        icon='binoculars-fill',
                        style='secondary',
                        attributes={'form': 'gbif-form'},
                        submit=True)
    
    # Add a button to display the classification
    display_button = Button(name='display',
                        display_text="Display Classification",
                        icon='map-fill',
                        style='secondary',
                        attributes={'id': 'display',
                                    'form': 'gbif-form'})
    
    # Collate all controls into context
    context = {'year_input': year_input,
            'rank_input': rank_input,
            'name_input': name_input,
            'taxon_input': taxon_input,
            'basis_input': basis_input,
            'map_view': map_view,
            'key_button': key_button,
            'load_button': load_button,
            'display_button': display_button}

    return App.render(request, 'occurrences.html', context)

@controller(name='help')
def help(request):
    """
    Controller for the help page.
    """

    return App.render(request, 'help.html')

@controller(url='input/get-roi/')
def get_roi(request):
    """
    Controller to download the RoI as a GeoJSON.
    """

    # Initialize the response data
    response_data = {'success': False}
    
    # Check for a POST request
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:

        # Try to get the geometries from the user
        geom = request.POST.get('geom', None)

        if not geom or geom == '""':
            raise ValueError("No Region of Interest (RoI) has been created yet")

        # Check the geometry is in the right format
        geom, _ = check_geom(geom)

        # Update the response data
        response_data.update({'success': True, 'roi': geom})

    # Add an error message to the response data if an exception occurs
    except Exception as e:
        response_data['error'] = f"Error ({type(e).__name__}): {e}"

    return JsonResponse(response_data)

@controller(url='labelling/get-labels/')
def get_labels(request):
    """
    Controller to download the labels as a GeoJSON.
    """

    # Initialize the response data
    response_data = {'success': False}
    
    # Check for a POST request
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:

        # Try to get the geometries from the user
        geom = request.POST.get('geom', None)

        if not geom or geom == '""':
            raise ValueError("No labels have been created yet")

        # Check the geometry is in the right format
        geom, _ = check_geom(geom)

        # Update the response data
        response_data.update({'success': True, 'labels': geom})

    # Add an error message to the response data if an exception occurs
    except Exception as e:
        response_data['error'] = f"Error ({type(e).__name__}): {e}"

    return JsonResponse(response_data)

@controller(url='labelling/get-labelling-image/', user_workspace=True)
def get_labelling_image(request, user_workspace):
    """
    Controller to handle image collection requests in the labelling page.
    """

    # Initialize the response data
    response_data = {'success': False}
    
    # Check for a POST request
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:

        # Try to get the year and layer choice from the user
        year = request.POST.get('year', None)
        layer = request.POST.get('layer', None)
        min_val = request.POST.get('min', None)
        max_val = request.POST.get('max', None)

        if year is None or year == '':
            raise ValueError("Please select a year from the drop-down menu to display the correct image for that assessment period")
        
        if layer is None or layer == '':
            raise ValueError("Please select a layer type from the drop-down menu to display the correct image for that assessment period")
        
        if (min_val is not None and min_val != '') and (max_val is not None and max_val != ''):
            try:
                min_val, max_val = float(min_val), float(max_val)
            except:
                raise ValueError("Please input a integer or decimal value for the min/max values")
        elif (min_val is not None and min_val != '') or (max_val is not None and max_val != ''):
            raise ValueError("Please provide a minimum AND a maximum pixel value to clip the data")
            
        # Get the tile URL
        url, min_val, max_val, warning = get_image_url(user_workspace=user_workspace, year=year, layer=layer, min_val=min_val, max_val=max_val, tile_scale=4)

        # Check if there was sufficient data for the chosen assessment year
        if warning:
            response_data['warning'] = warning

        # Update the response data
        response_data.update({'success': True, 'url': url, 'min': min_val, 'max': max_val})

    # Add an error message to the response data if an exception occurs
    except Exception as e:
        response_data['error'] = f"Error ({type(e).__name__}): {e}"

    return JsonResponse(response_data)

@controller(url='labelling/get-samples/', user_workspace=True)
def get_samples(request, user_workspace):
    """
    Controller to download the sampled pixel values as a GeoJSON.
    """

    # Initialize the response data
    response_data = {'success': False}
    
    # Check for a POST request
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:

        # Try to get the year from the user
        year = request.POST.get('year', None)

        if year is None or year == '':
            raise ValueError("Please select a year from the drop-down menu to display the correct image for that assessment period")

        # Get the sampled pixel values
        samples = get_samples_collection(user_workspace=user_workspace, year=year, tile_scale=4)

        # Update the response data
        response_data.update({'success': True, 'samples': samples})

    # Add an error message to the response data if an exception occurs
    except Exception as e:
        response_data['error'] = f"Error ({type(e).__name__}): {e}"

    return JsonResponse(response_data)

@controller(url='classification/get-classification', user_workspace=True)
def get_classification(request, user_workspace):
    """
    Controller to handle classification collection requests.
    """

    # Initialize the response data
    response_data = {'success': False}
    
    # Check for a POST request
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:
        
        # Try to get the year from the user
        year = request.POST.get('year', None)

        # Check that a year has been selected
        if year is None or year == '':
            raise ValueError("Please select a year from the drop-down menu to produce an ecosystem map that is correct as of the chosen assessment period")
        
        # Get the tile URL for the probability map and classification
        prob_url, class_url = get_classification_url(user_workspace, year=year, tile_scale=4)

        # Update the response data
        response_data.update({'success': True, 'prob_url': prob_url, 'class_url': class_url})

    # Add an error message to the response data if an exception occurs
    except Exception as e:
        response_data['error'] = f"Error ({type(e).__name__}): {e}"

    return JsonResponse(response_data)

@controller(url='classification/get-classification-image/', user_workspace=True)
def get_classification_image(request, user_workspace):
    """
    Controller to handle image collection requests in the classification page.
    """

    # Initialize the response data
    response_data = {'success': False}
    
    # Check for a POST request
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:

        # Try to get the layer choice from the user
        year = request.POST.get('year', None)
        layer = request.POST.get('layer', None)
        min_val = request.POST.get('min', None)
        max_val = request.POST.get('max', None)

        if year is None or year == '':
            raise ValueError("Please select a year from the drop-down menu to display the correct image for that assessment period")
        
        if layer is None or layer == '':
            raise ValueError("Please select a layer type from the drop-down menu to display the correct image for that assessment period")

        if (min_val is not None and min_val != '') and (max_val is not None and max_val != ''):
            try:
                min_val, max_val = float(min_val), float(max_val)
            except:
                raise ValueError("Please input a integer or decimal value for the min/max values")
        elif (min_val is not None and min_val != '') or (max_val is not None and max_val != ''):
            raise ValueError("Please provide a minimum AND a maximum pixel value to clip the data")
        
        # Get the tile URL
        url, min_val, max_val, warning = get_image_url(user_workspace=user_workspace, year=year, layer=layer, min_val=min_val, max_val=max_val, tile_scale=4)

        # Check if there was sufficient data for the chosen assessment year
        if warning:
            response_data['warning'] = warning

        # Update the response data
        response_data.update({'success': True, 'url': url, 'min': min_val, 'max': max_val})

    # Add an error message to the response data if an exception occurs
    except Exception as e:
        response_data['error'] = f"Error ({type(e).__name__}): {e}"

    return JsonResponse(response_data)

@controller(url='classification/get-metrics/', user_workspace=True)
def get_metrics(request, user_workspace):
    """
    Controller to display the metrics in the classification page.
    """

    # Initialize the response data
    response_data = {'success': False}
    
    # Check for a POST request
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:

        # Try to get the layer choice from the user
        year = request.POST.get('year', None)

        if year is None or year == '':
            raise ValueError("Please select a year from the drop-down menu to display the correct image for that assessment period")
        
        # Get the tile URL
        max_importances, train_precision, train_recall, train_f1_score, train_accuracy, val_precision, val_recall, val_f1_score, val_accuracy = generate_metrics(user_workspace=user_workspace, year=year, tile_scale=4)

        # Update the response data
        response_data.update({'success': True, 
                            'vars': max_importances, 
                            'train_P': train_precision, 
                            'train_R': train_recall, 
                            'train_F1': train_f1_score, 
                            'train_Acc': train_accuracy, 
                            'val_P': val_precision, 
                            'val_R': val_recall, 
                            'val_F1': val_f1_score, 
                            'val_Acc': val_accuracy})

    # Add an error message to the response data if an exception occurs
    except Exception as e:
        response_data['error'] = f"Error ({type(e).__name__}): {e}"

    return JsonResponse(response_data)

@controller(url='classification/get-download/', user_workspace=True)
def get_download(request, user_workspace):
    """
    Controller to get the download file path to the classification.
    """

    # Initialize the response data
    response_data = {'success': False}
    
    # Check for a POST request
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:

        # Try to get the year choice from the user
        year = request.POST.get('year', None)

        # Check that the year has been provided
        if year:

            # Get the user input back from the user
            user_dict = get_user_input(user_workspace.path, 'input')

            # Get the user input for this year
            if user_dict.get(str(year), None) is None:
                raise OSError("Please complete the 'Labelling' page before attempting to map the ecosystem")
    
            # Check if the ecosystem has been mapped yet
            if user_dict[str(year)].get('prob_url', None) is None or user_dict[str(year)].get('class_url', None) is None:
                raise ValueError("Please click 'Classify RoI' to map the ecosystem and check that it is valid before exporting")

            # Check if an export task has already been submitted
            if user_dict[str(year)].get('task', None) is not None:

                # Get the current status of the task
                export_url = None
                state, error_message = get_task_status(user_dict[str(year)])

                # Inform the user if the export failed, is pending, or is running
                if state == 'FAILED':
                    warning = f"Export for {year} failed. Error: {error_message}"
                elif state == 'PENDING':
                    warning = f"Export for {year} is currently pending. Please wait..."
                elif state == 'RUNNING':
                    warning = f"Export for {year} is currently running. Please wait..."

                # If the export has completed, return the download URL
                elif state == 'SUCCEEDED':

                    # Get the file name from the user input
                    file_name = user_dict[str(year)]['task']['file_name']

                    # Get the image metadata
                    properties = user_dict[str(year)]['task']['properties']

                    # Combine with the URL for the EcoCAT classifications GCP bucket
                    export_url = os.path.join('https://storage.cloud.google.com/ecocat-classifications/', file_name + '.tif')
                    
                    # # Use rasterio to impute the properties to the GeoTIFF's metadata
                    # with rasterio.open(export_url, 'r+') as src:
                    #     src.update_tags(**properties)

                    # Inform the user that the export has finished
                    warning = f"Export for {year} has finished. Downloading...\nCopy this URL to download the ecosystem map in future: {export_url}"

            # Otherwise, submit an export task
            else:
    
                # Export the classification
                task, file_name, properties = export_classification(user_workspace, request.user, year=year, tile_scale=4)
    
                # Get the task operation name
                operation_name = task.status()['name']
    
                # Add the task to the user input
                user_dict[str(year)]['task'] = {'operation_name': operation_name, 'file_name': file_name, 'properties': properties}
                add_user_input(user_workspace.path, user_dict, 'input')

                # Inform the user that the export task has been submitted
                warning = f'''Export for {year} has started. Click the 'Export Map' button again to check the status, or once the export has finished, to download the result as a GeoTiff.
                \nThis process could take between 5-30 mins depending on the size of your RoI, the resolution of the mapping, and the number of concurrent users.
                \nPlease wait for the export to finish/fail before changing any of the input in the 'User Input' or 'Labelling' pages as this will wipe the export information to allow for new ones, meaning you will not be able to access the initial export.'''
                export_url = None

        else:
            raise ValueError("Please select a year before attempting to export the map")
    
        # Update the response data
        response_data.update({'success': True, 'url': export_url, 'warning': warning})

    # Add an error message to the response data if an exception occurs
    except Exception as e:
        response_data['error'] = f"Error ({type(e).__name__}): {e}"

    return JsonResponse(response_data)

@controller(url='occurrences/get-occurrences-image/', user_workspace=True)
def get_occurrences_image(request, user_workspace):
    """
    Controller to handle image collection requests in the occurrences page.
    """

    # Initialize the response data
    response_data = {'success': False}
    
    # Check for a POST request
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:

        # Try to get the year choice from the user
        year = request.POST.get('year', None)

        if year is None or year == '':
            raise ValueError("Please select a year from the drop-down menu to display the correct image for that assessment period")
        
        # Get the tile URL
        url, _, _, _ = get_image_url(user_workspace=user_workspace, year=year, layer='visible', min_val=None, max_val=None)

        # Update the response data
        response_data.update({'success': True, 'url': url})

    # Add an error message to the response data if an exception occurs
    except Exception as e:
        response_data['error'] = f"Error ({type(e).__name__}): {e}"

    return JsonResponse(response_data)

@controller(url='occurrences/display-classification/', user_workspace=True)
def display_classification(request, user_workspace):
    """
    Controller to get the existing classification URL.
    """

    # Initialize the response data
    response_data = {'success': False}
    
    # Check for a POST request
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    try:

        # Try to get the year choice from the user
        year = request.POST.get('year', None)

        if year is None or year == '':
            raise ValueError("Please select a year from the drop-down menu to display the correct classification for that assessment period")

        # Try to get the classification url from the user input
        url = get_user_input(db_directory=user_workspace.path)[str(year)].get('class_url', None)

        # Check that the url exists
        if url is None or url == '':
            raise KeyError("Please generate an ecosystem map for this assessment period in the 'Classification' page before attempting to display it here")

        # Update the response data
        response_data.update({'success': True, 'url': url})

    # Add an error message to the response data if an exception occurs
    except Exception as e:
        response_data['error'] = f"Error ({type(e).__name__}): {e}"

    return JsonResponse(response_data)
import json
import os
from typing import Optional, Union

def add_user_input(db_directory: str, user_dict: dict, input_name: str, year: Optional[Union[int, str]] = None):
    """
    Persist new user inputs
    """

    # Serialize data to json
    user_json = json.dumps(user_dict)

    # Make dir if it doesn't exist
    if not os.path.exists(db_directory):
        os.makedirs(db_directory, exist_ok=True)

    # Define the file name
    if input_name == 'input':
        file_name = 'user_input.json'
    elif input_name == 'roi':
        file_name = 'region_of_interest.geojson'
    elif input_name == 'ecosystem':
        file_name = f'ecosystem_labels_{year}.geojson'
    elif input_name == 'background':
        file_name = f'background_labels_{year}.geojson'
    elif input_name == 'samples':
            file_name = f'samples_{year}.geojson'
    else:
        raise ValueError("Unsupported user input type. Please use one of 'input', 'roi', 'ecosystem' or 'background'")

    # Define the file path
    file_path = os.path.join(db_directory, file_name)

    # Remove the file if it already exists
    if os.path.exists(file_path):
        os.remove(file_path)

    # Write json
    with open(file_path, 'w') as f:
        f.write(user_json)

def get_user_input(db_directory: str, input_name: str, year: Optional[Union[int, str]] = None):
    """
    Get the persisted user inputs.
    """

    # Define the file name
    if input_name == 'input':
        file_name = 'user_input.json'
    elif input_name == 'roi':
        file_name = 'region_of_interest.geojson'
    elif input_name == 'ecosystem':
        file_name = f'ecosystem_labels_{year}.geojson'
    elif input_name == 'background':
        file_name = f'background_labels_{year}.geojson'
    elif input_name == 'samples':
        file_name = f'samples_{year}.geojson'
    else:
        raise ValueError("Unsupported user input type. Please use one of 'input', 'roi', 'ecosystem' or 'background'")

    # Define the file path
    file_path = os.path.join(db_directory, file_name)

    # Check that the file exists
    if os.path.exists(file_path):

        # Open the json file and convert contents to a Python dictionary
        with open(file_path, 'r') as f:
            user_dict = json.load(f)

        return user_dict

    else:
        return None
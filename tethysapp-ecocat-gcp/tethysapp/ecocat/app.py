from tethys_sdk.app_settings import CustomSetting
from tethys_sdk.base import TethysAppBase

class App(TethysAppBase):
    """
    Tethys app class for EcoCAT Ecosystem Mapping and Assessment.
    """
    
    name = 'EcoCAT Mapping Tool'
    description = 'A tool for automatic ecosystem mapping by combining expert knowledge, satellite data and machine learning'
    package = 'ecocat'
    index = 'home'
    icon = f'{package}/images/kew_logo_square_black.png'
    root_url = 'ecocat'
    color = '#669900'
    tags = ''
    enable_feedback = False

    def custom_settings(self):
        """
        Custom settings for various advanced user inputs.
        """

        custom_setting = (
                        CustomSetting(name='scale', 
                                    type=CustomSetting.TYPE_INTEGER, 
                                    description='Map scale (in metres per pixel)',
                                    required=False),
                        CustomSetting(name='model', 
                                    type=CustomSetting.TYPE_STRING, 
                                    description='Model to use for ecosystem classification (Random Forest = RF, k-NN = kNN, Support Vector Machine = SVM, Classification and Regression Trees = CART)',
                                    required=False),
                        CustomSetting(name='method', 
                                    type=CustomSetting.TYPE_STRING, 
                                    description='Method of classification (classify individual pixel values = pixels, or classify aggregated cluster statistics = clusters)',
                                    required=False)
                        )
        
        return custom_setting
from tethys_sdk.app_settings import CustomSetting
from tethys_sdk.base import TethysAppBase
from tethys_sdk.permissions import Permission, PermissionGroup

class App(TethysAppBase):
    """
    Tethys app class for EcoCAT Ecosystem Mapping and Assessment.
    """
    
    name = 'EcoCAT Mapping Tool'
    description = 'A user-friendly tool for mapping terrestrial ecosystems over the past 40+ years using expert knowledge, satellite data and machine learning'
    package = 'ecocat'
    index = 'home'
    icon = f'{package}/images/kew_logo_square_black.png'
    root_url = 'ecocat'
    color = '#669900'
    tags = ''
    enable_feedback = False

    def permissions(self):
        """
        Custom permissions for various app functions
        """

        export_enabled = Permission(name='export_enabled', description='Can export maps to Google Cloud Storage')
        high_res_enabled = Permission(name='high_res_enabled', description='Can set a sub-100m map scale')
        time_series_enabled = Permission(name='time_series_enabled', description='Can do time-series assessments')
        wgsrpd_enabled = Permission(name='wgsrpd_enabled', description='Can use the WGSRPD Botanical Countries dataset as a source of RoI')
        admin = PermissionGroup(name='admins', permissions=(export_enabled, high_res_enabled, time_series_enabled, wgsrpd_enabled))

        return (admin,)

    def custom_settings(self):
        """
        Custom settings for various advanced user inputs.
        """

        custom_setting = (
                        CustomSetting(name='model', 
                                    type=CustomSetting.TYPE_STRING, 
                                    description='Model to use for ecosystem classification (Random Forest = RF, k-NN = kNN, Support Vector Machine = SVM, Classification and Regression Trees = CART)',
                                    default='RF'),
                        CustomSetting(name='method', 
                                    type=CustomSetting.TYPE_STRING, 
                                    description='Method of classification (classify individual pixel values = pixels, or classify aggregated cluster statistics = clusters)',
                                    default='pixels')
                        )
        
        return custom_setting
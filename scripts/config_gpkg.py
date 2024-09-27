import os
import requests

def get_access_token(username: str, password: str) -> str:
    data = {
        "client_id": "cdse-public",
        "username": username,
        "password": password,
        "grant_type": "password",
        }
    try:
        r = requests.post("https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
        data=data,
        )
        r.raise_for_status()
    except Exception as e:
        raise Exception(
            f"Keycloak token creation failed. Reponse from the server was: {r.json()}"
            )
    return r.json()["access_token"]

class Config():

    def __init__(self):

        # [credential_sentinel]

        # Copernicus Data Space Ecosystem (CDSE) username and password
        # UNCOMMENT the 2 lines below, sign up at the CDSE website, and enter your email and password to download raster data
        #self.username_sentinel = "<email>"
        #self.password_sentinel = "<password>"
        self.access_token = get_access_token(self.username_sentinel, self.password_sentinel)

        # [credential_landsat]

        # Landsat username and password
        #self.username_landsat = "<email>"
        #self.password_landsat = "<password>"

        # [params]
        self.max_cloud_cover = 10
        self.delta_days_landsat = 70    # delta_days refers to the number of days to include before and after a fire period
        self.delta_days_sentinel = 40
        self.producttype_sentinel = "S2MSI2A"

        # whether to download the scenes or not
        self.download_scenes = True
        # [directory]
        #self.gpkg_dir = '/home/aramakrishnan/Documents/Firedpy/new_NIFC_fires/'
        self.gpkg_file = '/Bhaltos/ASHWATH/new_NIFC_fires/NIFC_2020_CO_Grizzly_Peak.gpkg' # Fire event data will be read from this input file
        self.data_dir = '/Bhaltos/ASHWATH/DNBR_data/SAFE_files'     # SAFE files will be downloaded into this output directory
# No sentinel scenes for NIFC_2022_NM_Bear_Trap.gpkg, NIFC_2022_NM_Calf_Canyon.gpkg, NIFC_2022_NM_Cerro_Pelado.gpkg, NIFC_2022_NM_Hermits_Peak.gpkg
        if os.name == 'nt':  # Windows
            self.dir_sep = '\\'
        else:  # Linux, macOS, and other platforms
            self.dir_sep = '/'
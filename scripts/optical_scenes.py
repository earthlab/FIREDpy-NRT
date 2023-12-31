import os
import sys
import json
import pandas as pd
from datetime import datetime, timedelta
import pyproj
from landsatxplore.api import API
from sentinelsat import SentinelAPI, geojson_to_wkt, LTATriggered
from config import Config
import glob, time
import geopandas as gpd
from landsatxplore.earthexplorer import EarthExplorer
import shapely
import argparse

config = Config()


def download_product(api, product_id, output_directory, num_retries=10, retry_wait=120):
    """
    Downloads a Sentinel-2 product using the sentinelsat package.

    This function attempts to download a Sentinel-2 product from the API, handling
    situations where the product is not available for direct download and needs to
    be triggered.

    Parameters:
        api (sentinelsat.SentinelAPI): An instance of the SentinelAPI class, which is
            used for downloading the product.
        product_id (str): The ID of the product to download.
        output_directory (str): The directory path where the downloaded product will be saved.
        num_retries (int, optional): The number of times to retry the download in case of failure.
            Default is 10.
        retry_wait (int, optional): The wait time in seconds between retries in case of failure.
            Default is 120 seconds.

    Returns:
        None: The function doesn't return a value, but it prints messages to inform the user
            about the download progress and success/failure.

    Raises:
        LTATriggered: If the product is not available for direct download and needs to be triggered.

    Notes:
        - The function uses the 'download' method of the sentinelsat package to download the product.
        - If the product is not available for direct download, the function waits and retries the download.
    """
    for i in range(num_retries):
        try:
            # Try to download the product
            api.download(product_id, directory_path = output_directory)
            print(f"Download of product {product_id} successful.")
            return
        except LTATriggered:
            # The product is not available for direct download and needs to be triggered
            print(f"Product {product_id} is not available for direct download. Retrying in {retry_wait/60} minutes.")
            time.sleep(retry_wait)
    print(f"Failed to download product {product_id} after {num_retries} retries.")



def get_sentinel(event_id,
                 footprint, 
                 start_date, 
                 end_date, 
                 json_file_name,
                 producttype,
                 platform="Sentinel-2"):
    """
    Queries Sentinel-2 images for a specified fire event within a given time frame.
    
    It can download the images and/or save their footprints.     
    For downloading images, set the download_scenes parameter in the config file to True
    For saving the footprints, set the save_footprints parameter in the config file to True

    This function connects to the Sentinel Hub, searches for available images for the specified event
    within the defined date range, and downloads the images if found.
        
        Notes:
        - The function uses the sentinelsat package to search for and download Sentinel-2 images. Refere to the links below for reference.
        - If the product is not available for direct download, the download_product function can be used to retry the download.
        - The function can optionally update a JSON file with metadata about downloaded scenes.
    Parameters:
        event_id (str): A string identifying the fire event for which to download images.
        footprint (str): The Area of Interest (AOI) for downloading images, as generated by the get_footprint function.
        start_date (str or datetime.datetime): The start date of the time range for which images are sought.
            Can be either a Python datetime object or a string in the format 'YYYY-MM-DD'.
        end_date (str or datetime.datetime): The end date of the time range for which images are sought.
            Can be either a Python datetime object or a string in the format 'YYYY-MM-DD'.
        json_file_name (str): Path to the JSON file where metadata about downloaded scenes will be saved.
        producttype (str): The Sentinel product type to search for. Possible values: {'S2MSI2A', 'S2MSI1C', 'S2MS2Ap'}.
        platform (str, optional): The Sentinel platform to search for images. Default is "Sentinel-2".

    Returns:
        None: This function does not return any values. It downloads images and saves them to disk, and optionally
            downloads their footptint with metadata.

    https://sentinelsat.readthedocs.io/en/stable/api_reference.html?highlight=api.query#sentinelsat.sentinel.SentinelAPI.query
    https://scihub.copernicus.eu/twiki/do/view/SciHubUserGuide/FullTextSearch?redirectedfrom=SciHubUserGuide.3FullTextSearch

    """
    

    print(f"searching for Sentinel images for event ID: {event_id}")
    
    # initialize the API. Update your username and password in the config.py file
    api = SentinelAPI(config.username_sentinel, config.password_sentinel,
                    'https://apihub.copernicus.eu/apihub')
    

    # Search for Sentinel-2 images before the start date
    products = api.query(footprint,
                        date=(start_date, end_date),
                        area_relation='Intersects', # this is the defualt. Possible options {'Intersects', 'Contains', 'IsWithin'},
                        cloudcoverpercentage = (0, config.max_cloud_cover),
                        # processinglevel = 'Level-2A',
                        producttype = producttype,
                        platformname=platform)
    
    
    # if any sentinel product is found
    if products:
        print(f"{len(products)} Sentinel products found for event {event_id}")

        # create directories for saving the images or the footprints
        out_dir = os.path.join(config.data_dir,"Fire_events", event_id)
        if not os.path.exists(out_dir):
                os.mkdir(out_dir)
        output_directory = os.path.join(out_dir, "Sentinel")
        if not os.path.exists(output_directory):
                os.mkdir(output_directory)

        # Save image footprints
        if config.save_footprints:
            print(f"Saving Sentinel product footprints for event{event_id} to {output_directory} ...")    
            gdf = api.to_geodataframe(products)
            fname = f"{output_directory}/Sentinel_footprints.geojson"
            gdf.to_file(fname, driver='GeoJSON') 


        # download products
        if config.download_scenes:
            # create a directory to save downloaded files
            print(f"Downloading Sentinel products for event{event_id} to {output_directory} ...")
            
            #################################
            # Caution:
            # this downloads all the products that are found which might take
            # a long time and a lot of space
            
            
            api.download_all(products, directory_path = output_directory)
            
            #################################
            # NOTE:
            # it is not easy to download individual scenes using the sentinelsat package
            # even though the functionality exists, it does not work all the time
            # To do so, you need to provide the uuids of the images and use the 
            # download_product function to download the images. Below is an example
            
            # p_ids = ["4db34296-b9a1-43b0-a4c4-8d18d88d40d1","cbfd0e7e-8f66-4080-9f04-abed517c0a1b"]

            # for p_id in p_ids:
            #     download_product(api, p_id, output_directory)

        
        # this part of the code was used at the begining of the project 
        # when we used individual json files. I don't think it'll be needed
        # anymore, but I kept it anyway
        if config.update_json:
            # Load the JSON file and append the scene information to it
            with open(json_file_name, 'r') as file:
                data = json.load(file)
                data['features'][0]['sentinel_senes'] = []
                
                for product_id in products:
                    product_info = api.get_product_odata(product_id)
                    
                    element = {
                    'Scene_ID': product_info['title'],
                    'acquisition_date': product_info['date'].strftime('%Y-%m-%d'),
                    'ingestion_date': product_info['Ingestion Date'].strftime('%Y-%m-%d'),
                    'URL': product_info['url'],
                    'Quicklook_URL': product_info['quicklook_url'],
                    'footprint': product_info['footprint']
                    }

                    data['features'][0]['sentinel_senes'].append(element)

            # Write the modified JSON data back to the same file
            json_fname = os.path.join(output_directory, f"{event_id}.json")
            with open(json_file_name, 'w') as file:
                json.dump(data, file)

    else:
        print(f"No Sentinel-2 scenes found for the fire event {event_id}")


def get_landsat(event_id,
                footprint, 
                 start_date, 
                 end_date, 
                 json_file_name, 
                 platform="Landsat-8"):   
    """
    Downloads Landsat images for a specified event within a given time frame.

    This function connects to the landsatxplore API and searches for available images for the specified 
    event within the defined date range.
    
    This function can download the images and/or save their footprints. 
    For downloading images, set the download_scenes parameter in the config file to True
    For saving the footprints, set the save_footprints parameter in the config file to True

    Notes: The function can optionally update a JSON file with metadata about downloaded scenes.

    Parameters:
        event_id (str): A string identifying the fire event for which to download images.
        footprint (tuple): The Area of Interest (AOI) for downloading images in the form of (xmin, ymin, xmax, ymax) of the bounding box.
        start_date (datetime.datetime): The start date of the time range for which images are sought.
        end_date (datetime.datetime): The end date of the time range for which images are sought.
        json_file_name (str): Path to the JSON file where metadata about downloaded scenes will be saved.
        platform (str, optional): The Landsat platform to search for images. Default is "Landsat-8".

    Returns:
        None: This function does not return any values. It downloads images and saves them to disk, and optionally
            downloads their footptint with metadata.

    """

    print(f"searching for Landsat images for event ID: {event_id}")

    # initialize the API
    api = API(config.username_landsat, config.password_landsat)

    # Search for Landsat 8 scenes
    # source: https://github.com/yannforget/landsatxplore/blob/master/landsatxplore/api.py
    # TODO: modify the dataset param in search based on the input platform param
    scenes = api.search(
        dataset='landsat_ot_c2_l1',
        bbox=footprint,
        start_date=start_date.strftime('%Y-%m-%d'),
        end_date=end_date.strftime('%Y-%m-%d'),
        max_cloud_cover=config.max_cloud_cover
    )

    # Process the search results
    if scenes:
        print(f"{len(scenes)} Landsat products found for event {event_id}")

        # create output directories
        out_dir = os.path.join(config.data_dir,"Fire_events", event_id)
        if not os.path.exists(out_dir):
                os.mkdir(out_dir)
        output_directory = os.path.join(out_dir, "Landsat")
        if not os.path.exists(output_directory):
                os.mkdir(output_directory)

        # Save image footprints
        if config.save_footprints:
            print(f"Saving Landsat product footprints for event {event_id} to {output_directory} ...")    

            df = pd.DataFrame.from_dict(scenes)
            # dropping column spatial_bounds as it contains tuples and temporal_coverage as it contains lists
            # Fiona cannot write columns of type tuple or list to a file and
            # keeping this column would result in ValueError: Invalid field type <class 'tuple'>
            df['temporal_coverage_start'] = df.apply (lambda row: row.temporal_coverage[0], axis=1)
            df['temporal_coverage_end'] = df.apply (lambda row: row.temporal_coverage[1], axis=1)
            df.drop('spatial_bounds', axis=1, inplace=True)
            df.drop('temporal_coverage', axis=1, inplace=True)
    
            crs = "EPSG:4326"  # WGS84
            gdf = gpd.GeoDataFrame(df, geometry="spatial_coverage", crs=crs)
            fname = f"{output_directory}/Landsat_footprints.geojson"
            gdf.to_file(fname, driver='GeoJSON') 

        # download products
        if config.download_scenes:
            print(f"Downloading Landsat products for event: {event_id} to {output_directory} ...")
            ee = EarthExplorer(config.username_landsat, config.password_landsat)
            
            #################################
            # Caution:
            # this downloads all the products that are found which might take
            # a long time and a lot of space
            # if you would like to download individual scense, use the example below

            # download_ids = [
            #     "LC08_L1TP_227072_20200624_20200823_02_T1",
            #     "LC08_L1TP_227072_20210219_20210219_02_T1" 
            # ]
            # for scene in scenes:
            #     if scene['display_id'] in download_ids:
            #         ee.download(scene['display_id'], output_dir=output_directory)

            for scene in scenes:
                ee.download(scene['display_id'], output_dir=output_directory)

            ee.logout()

        # this part of the code was used at the begining of the project 
        # when we used individual json files. I don't think it'll be needed
        # anymore, but I kept it anyway
        if config.update_json:
        # Load the JSON file and append the scene information to it
            with open(json_file_name, 'r') as file:
                data = json.load(file)
                data['features'][0]['landsat_senes'] = []

                for scene in scenes:
                        
                        element = {
                        'Scene_ID': scene['display_id'],
                        'acquisition_date': scene['acquisition_date'].strftime('%Y-%m-%d'),
                        'ingestion_date': scene['date_product_generated'].strftime('%Y-%m-%d'),
                        'data_type': scene['data_type'],
                        'footprint': scene['spatial_bounds'],
                        'land_cloud_cover': scene['land_cloud_cover'],
                        'scene_cloud_cover': scene['scene_cloud_cover']
                        }

                        data['features'][0]['landsat_senes'].append(element)

                        # Write scene footprints to disk
                        fname = f"{event_id}_{scene['landsat_product_id']}.geojson"
                        with open(fname, "w") as f:
                            json.dump(scene['spatial_coverage'].__geo_interface__, f)

            # Write the modified JSON data back to the same file
            json_fname = os.path.join(output_directory, f"{event_id}.json")
            with open(json_file_name, 'w') as file:
                json.dump(data, file)

    else:
        print(f"No Landsat scenes found for the fire event {event_id}")

    # Logout from the API
    api.logout()


def get_footprint_point(latitude, longitude,
                        delta_lat=0.1, delta_lon=0.05):
    """
    Generates a bounding box around a specified point, returned as a WKT polygon.

    This function takes a point defined by its latitude and longitude, and generates a bounding box
    (footprint) around that point using specified deltas for latitude and longitude. The bounding box
    is returned as a WKT polygon which can be used in the API to download images.

    Example:
    footprint = get_footprint_point(30.01978, -90.99)

    Parameters:
        latitude (float): The latitude of the point around which the bounding box will be generated.
        longitude (float): The longitude of the point around which the bounding box will be generated.
        delta_lat (float, optional): The amount to add/subtract to/from the latitude to generate the bounding box.
            Default is 0.1.
        delta_lon (float, optional): The amount to add/subtract to/from the longitude to generate the bounding box.
            Default is 0.05.

    Returns:
        str: The bounding box around the specified point, formatted as a WKT polygon.
    """
    footprint = geojson_to_wkt({
        "type": "Polygon",
        "coordinates": [[
            [longitude - delta_lon, latitude - delta_lat],
            [longitude + delta_lon, latitude - delta_lat],
            [longitude + delta_lon, latitude + delta_lat],
            [longitude - delta_lon, latitude + delta_lat],
            [longitude - delta_lon, latitude - delta_lat]
        ]]
    })

    return footprint

def get_footprint_poly(minlon, minlat, maxlon, maxlat):
    """
    Generates a bounding box using specified latitude and longitude coordinates, returned as a WKT polygon.

    This function takes minimum and maximum values for latitude and longitude and generates a bounding box 
    (footprint) using those values. The bounding box is returned as a WKT polygon which can be used in the 
    API to download images.

    Parameters:
        minlon (float): The minimum longitude of the bounding box.
        minlat (float): The minimum latitude of the bounding box.
        maxlon (float): The maximum longitude of the bounding box.
        maxlat (float): The maximum latitude of the bounding box.

    Returns:
        str: The bounding box defined by the specified coordinates, formatted as a WKT polygon.
    """
    footprint = "polygon((" + str(maxlon) + " " + str(maxlat) + "," + str(maxlon) + " " + str(minlat) + ","  \
    + str(minlon) + " " + str(minlat) + "," + str(minlon) + " " + str(maxlat) + "," + str(maxlon) + " " + str(maxlat) + "))"

    return footprint


def get_bbox(minlon, minlat, maxlon, maxlat):
    return (minlon, minlat, maxlon, maxlat)

def parse_jsons(filename):

    """
    Returns:
    
    fid: int 
    start_date: datetime 
    end_date: datetime 
    minlat: float 
    minlon: float 
    maxlat: float 
    maxlon: float
    """
    
    ### Process each JSON file
    ## Code written by Ryan
    with open(filename) as f:
        data = json.load(f)  # load input file (*.json) into dictionary, d
    
        ### key to finding first, last date
        start_date = data['features'][0]['properties']['first_date_7']
        end_date = data['features'][0]['properties']['last_date_7']
        fid = data['features'][0]['properties']['fid']
        climate = data['features'][0]['properties']['main_clim']
    
        ### add buffer to start/end dates
        start_date = datetime.strptime(start_date,"%Y-%m-%d")
        end_date = datetime.strptime(end_date, "%Y-%m-%d")

        ### get coordinates from the dictionary, d.    
        coord_list = data['features'][0]['geometry']['coordinates'][0][0][:]  ## Put coordinates into a single list
    
        ### Parse the list into x,y coordinates
        x_arr = [];     y_arr = []   ## initialize x,y arrays
        for n in range(len(coord_list)):  ### separate into 1 x n arrays for each x,y coordiante
            x_arr.append(coord_list[n][0])
            y_arr.append(coord_list[n][1])
    

        ### Find minimum/maximum extents
        minx = min(x_arr);     
        maxx = max(x_arr);     
        miny = min(y_arr);    
        maxy = max(y_arr)

    
        ### convert EPSG 3395 to 4326
        transformer = pyproj.Transformer.from_crs("epsg:3395", "epsg:4326")
        minlat,minlon = transformer.transform(minx, miny)
        maxlat,maxlon = transformer.transform(maxx, maxy)       

    return fid, start_date, end_date, minlat, minlon, maxlat, maxlon
    

def parse_shp(filename, fid):
    """
    Parses a shapefile of fire events to extract specific fire event information.
    The shapefile is the output of FiredPy package.

    Given the filename of a shapefile and a fire event ID, this function
    extracts the start date, end date, and footprint of the specified fire event.

    Parameters:
        filename (str): The name of the shapefile containing fire event information.
        fid (int or str): The ID of the fire event to extract information from.

    Returns:
        tuple: A tuple containing the fire event ID, start date, end date, and footprint of the specified fire event.
            - fid (str): The ID of the fire event.
            - start_date (datetime.datetime): The start date of the fire event.
            - end_date (datetime.datetime): The end date of the fire event.
            - footprint (shapely.geometry): The footprint (geometry) of the fire event.

    Note:
        footprint is an instance of <class 'shapely.geometry.multipolygon.MultiPolygon'>
        from https://shapely.readthedocs.io/en/stable/manual.html:
        footprint.bounds return the bounding box as a (minx, miny, maxx, maxy) tuple.
        The Sentinel API expects footprint to be formatted as a Well-Known Text string.
        whereas the Landsat API expects footprint as a tuple in the form of (xmin, ymin, xmax, ymax)

    """
    
    fires = gpd.read_file(filename)
    if not str(fid) in fires['id'].values:
         print("invalid fire ID provided! Make sure the ID exists in the fire events shapefile")
         sys.exit()
    fire_event = fires[fires['id'] == str(fid)]
    start_date = datetime.strptime(fire_event['ig_date'].values[0], "%Y-%m-%d")
    end_date = datetime.strptime(fire_event['last_date'].values[0], "%Y-%m-%d")
    footprint = fire_event['geometry'].values[0]

    return fid, start_date, end_date, footprint



def main(event_id, satellite):
    """
    Function to search for and download satellite images (Sentinel or Landsat) for a given fire event.

    Parameters:
        event_id (str): ID of the fire event for which satellite images are to be searched.
        satellite (str): Name of the satellite from which images are to be retrieved. Accepted values are "sentinel" and "landsat".

    Returns:
        None

    Description:
        The function reads the "selected_events.shp" shapefile containing fire event data and extracts the id, footprint, start, and end dates of the fire event.
        Based on the selected satellite, the function searches for satellite images within a specified time window around the fire event and downloads them.
        The satellite images are filtered by the specified bounding box, start and end dates, and other satellite-specific parameters.
        The footprints of the retrieved satellite images can be saved in GeoJSON format if configured.
        For Sentinel, the function retrieves images using the "get_sentinel" function.
        For Landsat, the function retrieves images using the "get_landsat" function.

    Note:
        Make sure the following variables are correctly configured in the "config" module:
        - data_dir
        - download_scenes
        - save_footprints
        - delta_days_sentinel
        - delta_days_landsat
        - producttype_sentinel
    """

    file_dir = os.path.join(config.data_dir, "Fire_events")
    file_name = os.path.join(file_dir, "selected_events.shp")
    # file_dir + "selected_events.shp"
    
    fid, start_date, end_date, footprint = parse_shp(file_name, event_id)
    
    print(f"Searching for {satellite} images for event ID {fid}")
    print(f"downloding images is set to: {config.download_scenes} and saving footprints is set to: {config.save_footprints}")

    # Footprint is an instance of <class 'shapely.geometry.multipolygon.MultiPolygon'>
    # from https://shapely.readthedocs.io/en/stable/manual.html:
    # footprint.bounds return the bounding box as a (minx, miny, maxx, maxy) tuple.
    # The Sentinel API expects footprint to be formatted as a Well-Known Text string.
    # whereas the Landsat API expects footprint as a tuple in the form of (xmin, ymin, xmax, ymax)

    # get the bounding box
    polygon = shapely.geometry.box(*footprint.bounds, ccw=True)

    if satellite == "sentinel":
        time_delta = config.delta_days_sentinel
        adjusted_start_date = start_date - timedelta(days=time_delta) 
        adjusted_end_date = end_date + timedelta(days=time_delta) 
        
        print(f"and with the start date of: {adjusted_start_date} and end date of: {adjusted_end_date}")
        
        get_sentinel(fid,
                polygon.wkt, 
                adjusted_start_date, 
                adjusted_end_date, 
                "json_file_name",
                producttype=config.producttype_sentinel,
                platform="Sentinel-2")

    elif satellite == "landsat":
        time_delta = config.delta_days_landsat
        adjusted_start_date = start_date - timedelta(days=time_delta) 
        adjusted_end_date = end_date + timedelta(days=time_delta)

        print(f"and with the start date of: {adjusted_start_date} and end date of: {adjusted_end_date}")

        get_landsat(fid,
                polygon.bounds, # this is equal to footprint.bounds 
                adjusted_start_date, 
                adjusted_end_date, 
                "json_file_name",
                platform="Landsat-8")

    else: 
        print("Wrong satellite selected. Exiting!")
        sys.exit()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Search for and download satellite images for a given fire event.")
    parser.add_argument("-id", "--event_id", type=str, help="ID of the fire event for which satellite images are to be searched. This comes from the id field of the fire events shapefile.")
    parser.add_argument("-s","--satellite", type=str, choices=["sentinel", "landsat"], help="Name of the satellite from which images are to be retrieved. Accepted values are 'sentinel' and 'landsat'.")
    args = parser.parse_args()
    main(args.event_id, args.satellite)
    


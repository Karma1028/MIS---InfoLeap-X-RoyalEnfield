import os
import requests
import json
import logging
from playwright.sync_api import sync_playwright

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Constants
MIN_IMAGE_SIZE_BYTES = 1000
REQUEST_TIMEOUT = 10
BROWSER_TIMEOUT = 30000
IMAGE_SELECTOR_TIMEOUT = 10000

# Fallback official or reliable URLs for bike images to avoid scraping issues in CI
OFFICIAL_URLS = {
    "Classic 350": "https://www.royalenfield.com/content/dam/royal-enfield/india/motorcycles/classic-350/colors/studio-shots/dual-channel/halcyon-black/01-halcyon-black.png",
    "Bullet 350": "https://www.royalenfield.com/content/dam/royal-enfield/india/motorcycles/bullet-350/colors/studio-shots/standard-black/01-standard-black.png",
    "Hunter 350": "https://www.royalenfield.com/content/dam/royal-enfield/india/motorcycles/hunter-350/colors/studio-shots/dapper-white/01-dapper-white.png",
    "Meteor 350": "https://www.royalenfield.com/content/dam/royal-enfield/india/motorcycles/meteor/colors/studio-shots/fireball-red/01-fireball-red.png",
    "Himalayan 450": "https://www.royalenfield.com/content/dam/royal-enfield/india/motorcycles/new-himalayan/colors/studio-shots/hanle-black/01-hanle-black.png",
    "Continental GT 650": "https://www.royalenfield.com/content/dam/royal-enfield/india/motorcycles/continental-gt/colors/studio-shots/rocker-red/01-rocker-red.png",
    "Interceptor 650": "https://www.royalenfield.com/content/dam/royal-enfield/india/motorcycles/interceptor/colors/studio-shots/canyon-red/01-canyon-red.png",
    "SuperMeteor 650": "https://www.royalenfield.com/content/dam/royal-enfield/india/motorcycles/super-meteor-650/colors/studio-shots/astral-black/01-astral-black.png",
    "Shotgun 650": "https://www.royalenfield.com/content/dam/royal-enfield/india/motorcycles/shotgun-650/colors/studio-shots/stencil-white/01-stencil-white.png",
    "Guerrilla 450": "https://www.royalenfield.com/content/dam/royal-enfield/india/motorcycles/guerrilla-450/colors/studio-shots/brava-blue/01-brava-blue.png",
    "Bear 650": "https://www.royalenfield.com/content/dam/royal-enfield/india/motorcycles/bear-650/colors/studio-shots/wild-honey/01-wild-honey.png",
    "Classic 650": "https://www.royalenfield.com/content/dam/royal-enfield/india/motorcycles/classic-650/colors/studio-shots/teal-master/01-teal-master.png",
    "Goan Classic 350": "https://www.royalenfield.com/content/dam/royal-enfield/india/motorcycles/goan-classic-350/colors/studio-shots/rave-red/01-rave-red.png",
    "Scram 440": "https://www.royalenfield.com/content/dam/royal-enfield/india/motorcycles/scram/colors/studio-shots/white-flame/01-white-flame.png",
}

def download_bike_image(bike_name, target_dir):
    """
    Downloads the image for a given bike name into the target directory.
    
    Args:
        bike_name (str): The name of the motorcycle.
        target_dir (str): The directory where the image should be saved.
        
    Returns:
        str: The path to the downloaded image file.
        
    Raises:
        requests.exceptions.RequestException: If there's an issue with the network request.
        Exception: If the image cannot be found or saved.
    """
    if not os.path.exists(target_dir):
        os.makedirs(target_dir, exist_ok=True)
        
    file_path = os.path.join(target_dir, f"{bike_name.replace(' ', '_')}.jpg")
    if os.path.exists(file_path) and os.path.getsize(file_path) > MIN_IMAGE_SIZE_BYTES:
        logger.info(f"Image for {bike_name} already exists at {file_path}")
        return file_path

    # Check fallback first
    img_url = OFFICIAL_URLS.get(bike_name)
    
    if not img_url:
        logger.info(f"Official URL for {bike_name} not found, attempting to scrape...")
        # Try scraping if not in fallback
        img_url = scrape_image_url(bike_name)

    if not img_url:
        raise Exception(f"Could not find any image URL for {bike_name}")

    try:
        logger.info(f"Downloading image for {bike_name} from {img_url}")
        response = requests.get(img_url, timeout=REQUEST_TIMEOUT)
        response.raise_for_status()
        
        with open(file_path, "wb") as f:
            f.write(response.content)
            
        if os.path.getsize(file_path) < MIN_IMAGE_SIZE_BYTES:
            logger.warning(f"Downloaded image for {bike_name} is too small ({os.path.getsize(file_path)} bytes)")
            
        return file_path
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error while downloading image for {bike_name}: {e}")
        raise

def scrape_image_url(bike_name):
    """
    Scrapes a Google Image Search result for a Royal Enfield bike studio shot.
    
    Args:
        bike_name (str): The name of the motorcycle.
        
    Returns:
        str: The URL of the first valid image found, or None if not found.
    """
    query = f"Royal Enfield {bike_name} studio shot official"
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}&tbm=isch"
    
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context()
            page = context.new_page()
            page.goto(search_url, timeout=BROWSER_TIMEOUT)
            page.wait_for_selector("img", timeout=IMAGE_SELECTOR_TIMEOUT)
            images = page.locator("img").all()
            for img in images:
                src = img.get_attribute("src")
                if src and src.startswith("http"):
                    browser.close()
                    return src
            browser.close()
    except Exception as e:
        logger.error(f"Error during scraping for {bike_name}: {e}")
        
    return None

def scrape_all_bikes(structure_path, target_dir):
    """
    Reads a JSON structure and downloads images for all listed motorcycle models.
    
    Args:
        structure_path (str): Path to the JSON file containing bike model data.
        target_dir (str): Directory where images should be saved.
        
    Returns:
        dict: A mapping of bike names to their local image file paths.
    """
    try:
        with open(structure_path, 'r') as f:
            structure = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Failed to read structure file {structure_path}: {e}")
        return {}
    
    # "models" contains the individual bikes
    bikes = structure.get("models", [])
    results = {}
    for bike in bikes:
        name = bike.get("text")
        if not name or name in ["All", "350CC", "450CC", "650CC"]: # Skip categories
            continue
            
        logger.info(f"Processing {name}...")
        try:
            path = download_bike_image(name, target_dir)
            results[name] = path
        except Exception as e:
            logger.error(f"Failed to process {name}: {e}")
            
    return results

if __name__ == "__main__":
    # Ensure relative paths work if run from project root
    base_dir = os.getcwd()
    structure_file = os.path.join(base_dir, "docs/investigation/dashboard_structure.json")
    assets_dir = os.path.join(base_dir, "assets/bikes")
    
    logger.info(f"Starting batch scraping into {assets_dir}...")
    scrape_all_bikes(structure_file, assets_dir)
    logger.info("Batch processing complete.")

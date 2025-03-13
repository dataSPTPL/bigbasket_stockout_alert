from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from bs4 import BeautifulSoup
import pandas as pd
import time
import re
from webdriver_manager.chrome import ChromeDriverManager
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

# Setup Chrome options
options = Options()
options.add_argument("--headless")
options.add_argument("--disable-gpu")
options.add_argument("--no-sandbox")
options.add_argument("--disable-dev-shm-usage")
options.add_argument("--window-size=1920,1080")
options.add_argument("start-maximized")
options.add_argument(
    "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
)

# Start Chrome WebDriver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

base_url = "https://www.bigbasket.com/ps/?q=rusk&nc=as"
all_data = []

def scroll_and_load(driver, max_attempts=40):
    last_height = driver.execute_script("return document.body.scrollHeight")
    attempts = 0

    while attempts < max_attempts:
        driver.execute_script("window.scrollBy(0, window.innerHeight);")
        time.sleep(2)

        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'div.SKUDeck___StyledDiv-sc-1e5d9gk-0'))
            )
        except TimeoutException:
            print("No new products detected.")
            break

        new_height = driver.execute_script("return document.body.scrollHeight")
        if new_height == last_height:
            attempts += 1
        else:
            attempts = 0
            last_height = new_height

# Google Sheets setup
def save_to_google_sheets(all_data, spreadsheet_name="POLKA"):
    scope = ['https://spreadsheets.google.com/feeds', 
             'https://www.googleapis.com/auth/drive']
    # Load credentials from environment variable
    creds_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    creds = ServiceAccountCredentials.from_json_keyfile_name(creds_path, scope)
    
    df = pd.DataFrame(all_data)
    
    try:
        sheet = client.open(spreadsheet_name)
    except gspread.SpreadsheetNotFound:
        sheet = client.create(spreadsheet_name)
    
    worksheet = sheet.get_worksheet(0)
    worksheet.clear()
    worksheet.update([df.columns.values.tolist()] + df.values.tolist())
    print("Data successfully saved to Google Sheets!")

try:
    driver.get(base_url)
    scroll_and_load(driver)

    selenium_product_count = len(driver.find_elements(By.CSS_SELECTOR, 'div.SKUDeck___StyledDiv-sc-1e5d9gk-0'))
    print(f"Total products found by Selenium: {selenium_product_count}")

    soup = BeautifulSoup(driver.page_source, "html.parser")
    product_containers_0 = soup.find_all('li', class_='PaginateItems___StyledLi-sc-1yrbjdr-0 dDBqny')
    product_containers_1 = soup.find_all('li', class_='PaginateItems___StyledLi2-sc-1yrbjdr-1 kUiNOF')
    product_containers = product_containers_0 + product_containers_1

    print(f"Total products found by BeautifulSoup: {len(product_containers)}")

    for container in product_containers:
        brand = container.find('span', class_='Label-sc-15v1nk5-0 BrandName___StyledLabel2-sc-hssfrl-1 gJxZPQ keQNWn')
        brand = brand.text.strip() if brand else "N/A"

        sponsored = container.find('span', class_='Label-sc-15v1nk5-0 Tags___StyledLabel2-sc-aeruf4-1 gJxZPQ ixttPj')
        sponsored = sponsored.text.strip() if sponsored else "N/A"

        product = container.find('h3', class_='block m-0 line-clamp-2 font-regular text-base leading-sm text-darkOnyx-800 pt-0.5 h-full')
        product = product.text.strip() if product else "N/A"

        rating_count_elem = container.find('span', class_='Label-sc-15v1nk5-0 gJxZPQ')
        rating_count = "N/A"
        if rating_count_elem:
            rating_count_text = rating_count_elem.text.strip()
            rating_count_match = re.search(r'\d+(\.\d+)?', rating_count_text)
            rating_count = rating_count_match.group() if rating_count_match else "N/A"

        price_elem = container.find('span', class_='Label-sc-15v1nk5-0 Pricing___StyledLabel-sc-pldi2d-1 gJxZPQ AypOi')
        discounted_price = re.sub(r"[^\d.]", "", price_elem.text.strip()) if price_elem else "N/A"

        discount = container.find('div', class_='Offers___StyledDiv-sc-118xvhp-0 hlfuqw')
        discount = discount.text.strip() if discount else "N/A"

        availability = container.find('span', class_='Label-sc-15v1nk5-0 Tags___StyledLabel2-sc-aeruf4-1 gJxZPQ gPgOvC')
        stock_availability = availability.text.strip() if availability else "N/A"

        pack_elem = container.find('div', class_='py-1.5 xl:py-1')
        pack = pack_elem.text.strip() if pack_elem else "N/A"
        variant = pack_elem.find('button') is not None if pack_elem else False

        product_url = container.find('a', class_='h-full', href=True)
        product_URL = "https://www.bigbasket.com" + product_url['href'] if product_url else "N/A"

        description = "N/A"

        if product_URL != "N/A":
            print(f"Fetching product details from: {product_URL}")
            driver.execute_script("window.open('');")
            driver.switch_to.window(driver.window_handles[1])
            driver.get(product_URL)
            time.sleep(3)

            product_soup = BeautifulSoup(driver.page_source, "html.parser")
            description_div = product_soup.find('div', class_='bullets pd-4 leading-xss text-md')
            if description_div:
                description_elem = description_div.find('p')
                if description_elem:
                    description = description_elem.get_text(strip=True)
                else:
                    styled_div = description_div.find('div', style=True)
                    if styled_div:
                        description = styled_div.get_text(strip=True)

            driver.close()
            driver.switch_to.window(driver.window_handles[0])

        all_data.append({
            'Brand': brand,
            'Sponsored': sponsored,
            'Product': product,
            'Product Description': description,
            'Rating Count': rating_count,
            'Discounted Price': discounted_price,
            'Discount': discount,
            'Stock Availability': stock_availability,
            'Pack': pack,
            'Variant Available': variant
        })

    save_to_google_sheets(all_data)

except Exception as e:
    print(f"Error: {str(e)}")
finally:
    driver.quit()
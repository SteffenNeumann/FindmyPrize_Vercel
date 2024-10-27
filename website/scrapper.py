from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import os
from geopy.geocoders import Nominatim
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from dataclasses import dataclass
from website.models import ScraperResult, db

geolocator = Nominatim(user_agent="FindmyPrize_Flask")

def run_scraper(city, country, product, target_price, should_send_email, user_id=None):
    loc = geolocator.geocode(f"{city},{country}")
    my_long = loc.longitude
    my_lat = loc.latitude

    load_dotenv()
    EMAIL_ADDRESS = os.getenv("EMAIL_ADDRESS")
    EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")
    RECIPIENT_EMAIL = os.getenv("RECIPIENT_EMAIL")

    def send_email(subject, message, should_send_email):
        
        if should_send_email:
            sender_email = EMAIL_ADDRESS
            sender_password = EMAIL_PASSWORD
            receiver_email = RECIPIENT_EMAIL

            msg = MIMEMultipart()
            msg["From"] = sender_email
            msg["To"] = receiver_email
            msg["Subject"] = subject
            msg.attach(MIMEText(message, "plain"))

            server = smtplib.SMTP("smtp.gmail.com", 587)
            server.starttls()
            server.login(sender_email, sender_password)
            text = msg.as_string()
            server.sendmail(sender_email, receiver_email, text)
            server.quit()

    def log_deal(store, price, product_name, data):
        """
        Logs a deal found during the web scraping process.
        
        Args:
            store (str): The name of the store where the product was found.
            price (float): The price of the product.
            product_name (str): The name of the product.
            target_price (float): The target price for the product.
            city (str): The city where the product was found.
            country (str): The country where the product was found.
            should_send_email (bool): Whether an email notification should be sent.
            user_id (int, optional): The ID of the user who requested the scraping.
            data (dict): Additional data related to the scraping process.
        
        Returns:
            None
        """
        scraper_result = ScraperResult(
            store=store,
            price=price,
            product=product_name,
            target_price=target_price,
            city=city,
            country=country,
            email_notification=should_send_email,
            user_id=user_id,
            data=data
        )
        db.session.add(scraper_result)
        db.session.commit()

    @dataclass
    class Product:
        name: str
        target_price: float

    PRODUCTS_AND_PRICES = [
        Product(product, float(target_price))
    ]
    
    results = []

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        for item in PRODUCTS_AND_PRICES:
            product = item.name
            target_price = item.target_price
            url = f"https://www.meinprospekt.de/webapp/?query={product}&lat={my_lat}&lng={my_long}"

            try:
                page.goto(url)
                page.wait_for_load_state("load", timeout=10000)
                offer_section = page.wait_for_selector(
                    ".search-group-grid-content", timeout=10000
                )
                if not offer_section:
                    output = f"No Product {product} found"
                else:
                    products = offer_section.query_selector_all(
                        ".card.card--offer.slider-preventClick"
                    )
                    output = ""
                    for product_element in products:
                        store_element = product_element.query_selector(".card__subtitle")
                        price_element = product_element.query_selector(
                            ".card__prices-main-price"
                        )
                        if store_element and price_element:
                            store = store_element.inner_text().strip()
                            price_text = price_element.inner_text().strip()
                            try:
                                price_value = float(
                                    price_text.replace("€", "").replace(",", ".").strip()
                                )
                                if price_value <= target_price:
                                    subject = "Deal Alert!"
                                    product_name_element = product_element.query_selector(
                                        ".card__title"
                                    )
                                    product_name = product_name_element.inner_text().strip() if product_name_element else "Unknown Product"

                                    message = f"Deal alert! {store} offers {product_name} for {price_text}! (Target price: €{target_price:.2f})"
                                    send_email(subject, message, should_send_email)
                                    log_deal(store, price_value, product_name, message)
                                    output += message + "\n"
                            except ValueError:
                                print(f"Could not convert price to float: {price_text}")
            except PlaywrightTimeoutError:
                print(f"Timeout exceeded for {product}. Moving to the next item.")
                continue

            print(output)
            results.append(output)
        browser.close()

    return results
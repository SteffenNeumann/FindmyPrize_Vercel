"""
Runs a web scraper to search for products on the meinprospekt.de website and logs any deals found.

Args:
    city (str): The city to search for products in.
    country (str): The country to search for products in.
    product (str): The product to search for.
    target_price (float): The target price for the product.
    should_send_email (bool): Whether to send an email notification for any deals found.
    user_id (int, optional): The ID of the user who requested the scraping.

Returns:
    list: A list of strings representing the output of the scraping process.
"""
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

    class DealFinding:
        def __init__(self, store, price, product_name, original_price=None, discount=None):
            self.store = store
            self.price = price
            self.product_name = product_name
            self.original_price = original_price
            self.discount = discount
            self.timestamp = datetime.now()

    collected_findings = []

    def format_email_content(findings):
        email_content = f"""
        🎯 Deal Alert Summary for {product}
        📍 Location: {city}, {country}
        💰 Target Price: €{target_price:.2f}
        
        Found Deals:
        """
        for finding in findings:
            email_content += f"""
            🏪 {finding.store}
            📦 {finding.product_name}
            💶 Current Price: €{finding.price:.2f}
            ⏰ Found at: {finding.timestamp.strftime('%Y-%m-%d %H:%M:%S')}
            {'=' * 50}
            """
        return email_content

    def log_deal(store, price, product_name, data):
        # Check if this exact deal already exists in collected_findings
        for finding in collected_findings:
            if (finding.store == store and 
                finding.price == price and 
                finding.product_name == product_name):
                return  # Skip if duplicate
            
        # If not duplicate, add to collected_findings
        finding = DealFinding(store, price, product_name)
        collected_findings.append(finding)
    
        # Check if result already exists in database
        existing_result = ScraperResult.query.filter_by(
            store=store,
            price=price,
            product=product_name,
            target_price=target_price,
            city=city,
            country=country,
            user_id=user_id
        ).first()
    
        if not existing_result:
            scraper_result = ScraperResult(
                store=store,
                price=price,
                product=product_name,
                target_price=target_price,
                city=city,
                country=country,
                email_notification=should_send_email,
                user_id=user_id,
                data=data,
                timestamp=finding.timestamp
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
        browser = browser = p.chromium.launch(
                    headless=True,
                    chromium_sandbox=False,
                    args=[
                        '--no-sandbox',
                       '--disable-setuid-sandbox',
                       '--disable-dev-shm-usage'
                             ]
)


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
                                    product_name_element = product_element.query_selector(
                                        ".card__title"
                                    )
                                    product_name = product_name_element.inner_text().strip() if product_name_element else "Unknown Product"

                                    message = f"Deal alert! {store} offers {product_name} for {price_text}! (Target price: €{target_price:.2f})"
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

    # After collecting all findings, send one consolidated email
    if collected_findings and should_send_email:
        email_content = format_email_content(collected_findings)
        subject = f"Deal Alert Summary - {len(collected_findings)} deals found for {product}!"
        send_email(subject, email_content, should_send_email)

    # Format results for web display
    formatted_results = []
    for finding in collected_findings:
        formatted_deal = {
            'store': finding.store,
            'product_name': finding.product_name,
            'price': finding.price,
            'timestamp': finding.timestamp,
            'target_price': target_price
        }
        formatted_results.append(formatted_deal)

    return formatted_results   
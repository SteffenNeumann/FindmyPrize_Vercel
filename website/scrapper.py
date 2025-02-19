from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError
import os
import logging
from geopy.geocoders import Nominatim
from datetime import datetime
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from dotenv import load_dotenv
from dataclasses import dataclass
from website.models import ScraperResult, db

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

geolocator = Nominatim(user_agent="FindmyPrize_Flask")

def run_scraper(city, country, product, target_price, should_send_email, user_id=None):
    logger.info(f"Starting scraper for {product} in {city}, {country}")
    
    # Get location coordinates
    loc = geolocator.geocode(f"{city},{country}")
    my_long = loc.longitude
    my_lat = loc.latitude
    logger.debug(f"Coordinates found - Latitude: {my_lat}, Longitude: {my_long}")

    # Load environment variables
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
        for finding in collected_findings:
            if (finding.store == store and finding.price == price and 
                finding.product_name == product_name):
                return

        finding = DealFinding(store, price, product_name)
        collected_findings.append(finding)

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

    PRODUCTS_AND_PRICES = [Product(product, float(target_price))]
    results = []

    with sync_playwright() as p:
        logger.info("Starting Playwright session")
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', 
                  '--disable-gpu', '--single-process']
        )
        logger.debug("Browser launched successfully")
        
        page = browser.new_page()
        logger.debug("New page created")

        for item in PRODUCTS_AND_PRICES:
            product = item.name
            target_price = item.target_price
            url = f"https://www.meinprospekt.de/webapp/?query={product}&lat={my_lat}&lng={my_long}"
            logger.debug(f"Accessing URL: {url}")

            try:
                page.goto(url)
                page.wait_for_load_state("load", timeout=10000)
                offer_section = page.wait_for_selector(".search-group-grid-content", timeout=10000)
                
                if not offer_section:
                    output = f"No Product {product} found"
                else:
                    products = offer_section.query_selector_all(".card.card--offer.slider-preventClick")
                    output = ""
                    
                    for product_element in products:
                        store_element = product_element.query_selector(".card__subtitle")
                        price_element = product_element.query_selector(".card__prices-main-price")
                        
                        if store_element and price_element:
                            store = store_element.inner_text().strip()
                            price_text = price_element.inner_text().strip()
                            
                            try:
                                price_value = float(price_text.replace("€", "").replace(",", ".").strip())
                                if price_value <= target_price:
                                    product_name_element = product_element.query_selector(".card__title")
                                    product_name = product_name_element.inner_text().strip() if product_name_element else "Unknown Product"
                                    
                                    message = f"Deal alert! {store} offers {product_name} for {price_text}! (Target price: €{target_price:.2f})"
                                    log_deal(store, price_value, product_name, message)
                                    output += message + "\n"
                            except ValueError:
                                logger.error(f"Could not convert price to float: {price_text}")
                
                logger.info(output)
                results.append(output)
                
            except PlaywrightTimeoutError as e:
                logger.error(f"Timeout for {product}: {str(e)}")
                continue
            except Exception as e:
                logger.error(f"Error processing {product}: {str(e)}")
                continue

        browser.close()
        logger.info("Browser closed successfully")

    if collected_findings and should_send_email:
        email_content = format_email_content(collected_findings)
        subject = f"Deal Alert Summary - {len(collected_findings)} deals found for {product}!"
        send_email(subject, email_content, should_send_email)

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

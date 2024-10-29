from flask import Blueprint, render_template, request, flash, jsonify
from flask_login import login_required, current_user
from .models import Note, ScraperResult, SavedSearch
from . import db
from .scrapper import run_scraper
from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim
import time
import json
from flask import redirect, url_for
from io import StringIO
import csv
from flask import make_response
from flask import json

views = Blueprint('views', __name__)

def geocode_with_retry(address, max_attempts=5):
    geolocator = Nominatim(user_agent="FindmyPrize_Flask")
    for attempt in range(max_attempts):
        try:
            location = geolocator.geocode(address, timeout=10)
            if location:
                return location
        except GeocoderTimedOut:
            if attempt < max_attempts - 1:
                time.sleep(2 ** attempt)
    return None

@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    # Load saved searches for the user
    saved_searches = SavedSearch.query.filter_by(user_id=current_user.id).order_by(SavedSearch.date_created.desc()).first()
    saved_deals = ScraperResult.query.filter_by(user_id=current_user.id).order_by(ScraperResult.id.desc()).all()
    
    if request.method == 'POST':
        city = request.form.get('city')
        country = request.form.get('country')
        product = request.form.get('product')
        price = request.form.get('price').replace(',', '.')
        save_search = request.form.get('saveSearch') == 'on'
        email_notification = request.form.get('emailNotification') == 'on'
        
        # Save the search if checkbox is checked
        if save_search:
            saved_search = SavedSearch(
                user_id=current_user.id,
                product=product,
                target_price=float(price),
                city=city,
                country=country,
                email_notification=email_notification
            )
            db.session.add(saved_search)
            db.session.commit()
            
        if city and country and product and price:
            location_string = f"{city}, {country}"
            geolocator = Nominatim(user_agent="FindmyPrize_Flask", timeout=10)
            
            try:
                loc = geolocator.geocode(location_string)
                if loc and hasattr(loc, 'longitude') and hasattr(loc, 'latitude'):
                    results = run_scraper(city, country, product, float(price), email_notification)
                    
                    # Store results in database only if deals were found
                    if results:
                        scraper_result = ScraperResult(
                            data=json.dumps(results),
                            user_id=current_user.id,
                            product=product,
                            target_price=float(price),
                            city=city,
                            country=country,
                            email_notification=email_notification
                            )
                        db.session.add(scraper_result)
                        db.session.commit()
                    else:
                        flash('No deals found matching your criteria', category='error')
                        return redirect(url_for('views.home'))
                    
                    return render_template('home.html', user=current_user, deals=saved_deals, results=results)
                else:
                    flash(f'Invalid location data for {location_string}', category='error')
            except GeocoderTimedOut:
                flash('Geocoding service timed out', category='error')
    
    return render_template('home.html', 
                         user=current_user, 
                         deals=saved_deals, 
                         saved_search=saved_searches)
@views.route('/delete-note', methods=['POST'])
def delete_note():  
     note = json.loads(request.data) # this function expects a JSON from the INDEX.js file 
     noteId = note['noteId']
     note = Note.query.get(noteId)
     if note:
         if note.user_id == current_user.id:
             db.session.delete(note)
             db.session.commit()

@views.route('/geocode', methods=['POST'])
@login_required
def handle_geocoding():
    address = request.form.get('address')
    product = request.form.get('product')
    target_price = request.form.get('target_price')
    email_notification = request.form.get('emailNotification') == 'on'
    
    if not address:
        return jsonify({'error': 'Address is required'}), 400

    location = geocode_with_retry(address)
    if location:
        city = location.address.split(',')[0]  # Extract city from geocoded address
        country = location.address.split(',')[-1]  # Extract country from geocoded address
        
        scraper_results = run_scraper(
            city=city,
            country=country,
            product=product,
            target_price=float(target_price),
            should_send_email=email_notification
        )
        
        scraper_result = ScraperResult(
            data=f"Geocoded: {address} to {location.latitude}, {location.longitude}",
            user_id=current_user.id
        )
        db.session.add(scraper_result)
        db.session.commit()
        
        return jsonify({
            'latitude': location.latitude,
            'longitude': location.longitude,
            'address': location.address,
            'scraper_results': scraper_results
        })
    else:
        return jsonify({'error': 'Geocoding failed'}), 500
# Add other existing view functions here     return jsonify({})

@views.route('/past-results')
def past_results():
    results = ScraperResult.query.order_by(ScraperResult.price.asc()).all()
    return jsonify([{'data': json.loads(result.data), 'date': result.date} for result in results])


@views.app_template_filter('from_json')
def from_json(value):
    try:
        return json.loads(value) if value else {}
    except json.JSONDecodeError:
        return {}

@views.route('/clear-deals', methods=['POST'])
@login_required
def clear_deals():
    ScraperResult.query.filter_by(user_id=current_user.id).delete()
    db.session.commit()
    flash('All deals cleared successfully!', category='success')
    return redirect(url_for('views.home'))
@views.route('/delete-deal', methods=['POST'])
@login_required
def delete_deal():
    deal_id = request.form.get('dea
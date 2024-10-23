from flask import Blueprint, render_template, request, flash, jsonify
from flask_login import login_required, current_user
from .models import Note, ScraperResult
from . import db
from .scrapper import run_scraper
from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim
import time
import json

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
    if request.method == 'POST':
        city = request.form.get('city')
        country = request.form.get('country')
        product = request.form.get('product')
        price = request.form.get('price')
        
        if city and country and product and price:
            location_string = f"{city}, {country}"
            geolocator = Nominatim(user_agent="FindmyPrize_Flask", timeout=10)
            
            try:
                loc = geolocator.geocode(location_string)
                if loc and hasattr(loc, 'longitude') and hasattr(loc, 'latitude'):
                    results = run_scraper(city, country, product, float(price))
                    
                    # Store results in database
                    scraper_result = ScraperResult(data=json.dumps(results))
                    db.session.add(scraper_result)
                    db.session.commit()
                    
                    return jsonify({'results': results})
                else:
                    return jsonify({'error': f'Invalid location data for {location_string}'}), 400
            except GeocoderTimedOut:
                return jsonify({'error': 'Geocoding service timed out'}), 503
            
    return render_template("home.html", user=current_user)
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
    if not address:
        return jsonify({'error': 'Address is required'}), 400

    location = geocode_with_retry(address)
    if location:
        scraper_result = ScraperResult(
            data=f"Geocoded: {address} to {location.latitude}, {location.longitude}",
            user_id=current_user.id
        )
        db.session.add(scraper_result)
        db.session.commit()
        return jsonify({
            'latitude': location.latitude,
            'longitude': location.longitude,
            'address': location.address
        })
    else:
        return jsonify({'error': 'Geocoding failed'}), 500
# Add other existing view functions here     return jsonify({})

@views.route('/past-results')
def past_results():
    results = ScraperResult.query.order_by(ScraperResult.date.desc()).all()
    return jsonify([{'data': json.loads(result.data), 'date': result.date} for result in results])

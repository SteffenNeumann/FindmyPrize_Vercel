from flask import Blueprint, render_template, request, flash, jsonify
from flask_login import login_required, current_user
from .models import Note, ScraperResult, SavedSearch, ScraperSchedule
from . import db
from .scrapper import run_scraper
from geopy.exc import GeocoderTimedOut
from geopy.geocoders import Nominatim
import time
import datetime
import json
from flask import redirect, url_for
from io import StringIO
import csv
from flask import make_response
from flask import json
from . import scheduler

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
        city = current_user.city
        country=current_user.country
        product = request.form.get('product')
        price = request.form.get('price').replace(',', '.')
        save_search = request.form.get('saveSearch') == 'on'
        email_notification = request.form.get('emailNotification') == 'on'
        print(f"Received POST request with product: {product}, price: {price}, city: {city}, country: {country}")
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
    deal_id = request.form.get('deal_id')
    deal = ScraperResult.query.get(deal_id)
    
    if deal and deal.user_id == current_user.id:
        db.session.delete(deal)
        db.session.commit()
        flash('Deal deleted successfully!', 'success')
    
    return redirect(url_for('views.home'))

@views.route('/export-deals')
def export_deals():
    deals = ScraperResult.query.all()
    si = StringIO()
    cw = csv.writer(si)
    cw.writerow(['ID', 'Date', 'Data'])  # Headers
    for deal in deals:
        cw.writerow([deal.id, deal.date_created, deal.data])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=deals_export.csv"
    output.headers["Content-type"] = "text/csv"
    return output



@views.route('/scheduler-status')
@login_required
def scheduler_status():
    schedules = ScraperSchedule.query.filter_by(user_id=current_user.id).all()
    active_jobs = scheduler.get_jobs()
    
    # Add flash message to show counts
    flash(f'Found {len(schedules)} schedules and {len(active_jobs)} active jobs', category='info')
    
    scheduler_info = []
    for schedule in schedules:
        job_info = {
            'id': schedule.id,
            'product': schedule.product,
            'interval': f"Every {schedule.interval} minutes",
            'target_price': schedule.target_price,
            'location': f"{schedule.city}, {schedule.country}",
            'last_run': schedule.last_run,
            'next_run': schedule.next_run,
            'active': schedule.active,
            'notifications': "Enabled" if schedule.email_notification else "Disabled"
        }
        scheduler_info.append(job_info)
    
    return render_template('scheduler_status.html', 
                         user=current_user,
                         scheduler_info=scheduler_info,
                         active_jobs=active_jobs)
@views.route('/cancel-schedule/<int:schedule_id>', methods=['POST'])
@login_required
def cancel_schedule(schedule_id):
                 schedule = ScraperSchedule.query.get_or_404(schedule_id)
    
                 if schedule.user_id != current_user.id:
                     flash('Unauthorized access', category='error')
                     return redirect(url_for('views.scheduler_status'))
    
                 # Deactivate the schedule in database
                 schedule.active = False
                 db.session.commit()
    
                 # Try to remove from scheduler if job exists
                 job_id = f'schedule_{schedule_id}'
                 if job_id in [job.id for job in scheduler.get_jobs()]:
                     scheduler.remove_job(job_id)
    
                 flash('Schedule cancelled successfully', category='success')
                 return redirect(url_for('views.scheduler_status'))

@views.route('/create-schedule', methods=['POST'])
@login_required
def create_schedule():
    product = request.form.get('product')
    interval = int(request.form.get('intervalUnit', '60'))  # Default to 60 if not provided
    target_price = request.form.get('price').replace(',', '.')
    city = current_user.city
    country=current_user.country
    email_notification = request.form.get('email_notification') == 'on'

    
    current_time = datetime.datetime.now()
    next_run_time = current_time + datetime.timedelta(minutes=interval)
    
    new_schedule = ScraperSchedule(
        user_id=current_user.id,
        product=product,
        interval=interval,
        target_price=target_price,
        city = city,
        country=country,
        email_notification=email_notification,
        active=True,
        last_run=current_time,
        next_run=next_run_time
    )
    
    db.session.add(new_schedule)
    db.session.commit()
    
    def scheduled_job():
        current_time = datetime.datetime.now()
        results = run_scraper(city, country, product, target_price, email_notification)
        
        schedule = ScraperSchedule.query.get(new_schedule.id)
        schedule.last_run = current_time
        schedule.next_run = current_time + datetime.timedelta(minutes=interval)
        
        if results:
            scraper_result = ScraperResult(
                data=json.dumps(results),
                user_id=current_user.id,
                product=product,
                target_price=target_price,
                city=city,
                country=country,
                email_notification=email_notification
            )
            db.session.add(scraper_result)
        db.session.commit()
    
    scheduler.add_job(
        func=scheduled_job,
        trigger='interval',
        minutes=interval,
        id=f'schedule_{new_schedule.id}',
        replace_existing=True,
        next_run_time=next_run_time
    )
    
    flash('New schedule created and started successfully', category='success')
    return redirect(url_for('views.scheduler_status'))
    return redirect(url_for('views.scheduler_status'))

@views.route('/cleanup-schedules', methods=['POST'])
@login_required
def cleanup_schedules():
    # Deactivate all schedules for current user
    schedules = ScraperSchedule.query.filter_by(user_id=current_user.id).all()
    for schedule in schedules:
        schedule.active = False
        job_id = f'schedule_{schedule.id}'
        if job_id in [job.id for job in scheduler.get_jobs()]:
            scheduler.remove_job(job_id)
    
    db.session.commit()
    flash('All schedules cleaned up successfully', category='success')
    return redirect(url_for('views.scheduler_status'))
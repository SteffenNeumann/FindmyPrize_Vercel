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
from .models import User

views = Blueprint('views', __name__)
# Global schedule time settings
SCHEDULE_HOUR = 7  # Default 7 AM
SCHEDULE_MINUTE = 0  # Default 0 minutes

def geocode_with_retry(location_string, max_attempts=5, initial_delay=1):
    geolocator = Nominatim(user_agent="FindmyPrize_Flask", timeout=10)
    
    for attempt in range(max_attempts):
        try:
            location = geolocator.geocode(location_string)
            if location:
                return location
        except GeocoderTimedOut:
            delay = initial_delay * (2 ** attempt)  # Exponential backoff
            time.sleep(delay)
            continue
    
    flash(f'Location service temporarily unavailable. Please try again.', category='error')
    return None

@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    # Initialize variables
    city = current_user.city
    country = current_user.country
    
    # Load saved searches for the user
    saved_searches = SavedSearch.query.filter_by(user_id=current_user.id).order_by(SavedSearch.date_created.desc()).first()
    
    # Modify this line to include all necessary fields for the deals cards
    saved_deals = ScraperResult.query.filter_by(user_id=current_user.id).order_by(ScraperResult.id.desc()).all()
    
    if request.method == 'POST':
        product = request.form.get('product')
        price = request.form.get('price').replace(',', '.')
        save_search = request.form.get('saveSearch') == 'on'
        email_notification = request.form.get('emailNotification') == 'on'

        if city and country and product and price:
            print(f"Received POST request with product: {product}, price: {price}, city: {city}, country: {country}")
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
            
            results = run_scraper(city, country, product, float(price), email_notification)
            # Results are now properly structured dictionaries
            if results:
                for result in results:
                    scraper_result = ScraperResult(
                        store=result['store'],
                        price=result['price'],
                        product=result['product_name'],
                        target_price=float(price),
                        city=city,
                        country=country,
                        email_notification=email_notification,
                        user_id=current_user.id,
                        data=json.dumps(result)
                    )
                    db.session.add(scraper_result)
                db.session.commit()
            
            return render_template('home.html',
                user=current_user,
                results=results,
                saved_searches=saved_searches,
                deals=saved_deals,
                is_previous_deal=True)  # Add this flag to differentiate styling

    return render_template('home.html',
        user=current_user,
        deals=saved_deals,
        saved_search=saved_searches,
        is_previous_deal=True)  # Add this flag to differentiate styling
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
            #'interval': f"Every {schedule.interval} minutes",
            'target_price': schedule.target_price,
            'location': f"{schedule.city}, {schedule.country}",
            'last_run': schedule.last_run,
            'next_run': schedule.next_run,
            'active': schedule.active,
            'notifications': "Enabled" if schedule.email_notification else "Disabled"
        }
        scheduler_info.append(job_info)
    
    # Count successful searches from ScraperResult
    successful_searches = ScraperResult.query.filter_by(user_id=current_user.id).count()
    
    # Count deals found (you may want to adjust this query based on your criteria)
    deals_found = ScraperResult.query.filter_by(
        user_id=current_user.id
    ).count()

    return render_template(
        'scheduler_status.html',
        user=current_user,
        successful_searches=successful_searches,
        deals_found=deals_found,
        scheduler_info=scheduler_info,
        active_jobs=active_jobs
    )
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

def scheduled_job(schedule_id, app):
    with app.app_context():
        schedule = ScraperSchedule.query.get(schedule_id)
        current_time = datetime.datetime.now()
        schedule_time = datetime.time(SCHEDULE_HOUR, SCHEDULE_MINUTE)
        next_run = datetime.datetime.combine(current_time.date(), schedule_time)
        if current_time > next_run:
            next_run = next_run + datetime.timedelta(days=1)
        schedule.next_run = next_run
        results = run_scraper(
            city=schedule.city,
            country=schedule.country,
            product=schedule.product,
            target_price=schedule.target_price,
            should_send_email=True,
            user_id=schedule.user_id
        )
        
        schedule.last_run = current_time
        
        # Only create ScraperResult if results contain valid data
        if results and isinstance(results, list) and len(results) > 0:
            for result in results:
                if result.get('store') and result.get('price'):  # Verify required fields exist
                    scraper_result = ScraperResult(
                        data=json.dumps(result),
                        user_id=schedule.user_id,
                        product=schedule.product,
                        target_price=schedule.target_price,
                        city=schedule.city,
                        country=schedule.country,
                        email_notification=True,
                        store=result.get('store'),  # Explicitly set store
                        price=float(result.get('price', 0))  # Explicitly set price
                    )
                    db.session.add(scraper_result)
        db.session.commit()
@views.route('/create-schedule', methods=['POST'])
@login_required
def create_schedule():
    from flask import current_app
    
    product = request.form.get('product')
    target_price = request.form.get('price').replace(',', '.')
    city = current_user.city
    country =  current_user.country
    
    # Default values
    interval = 24*60  # 24 hours in minutes
    schedule_time = datetime.time(SCHEDULE_HOUR, SCHEDULE_MINUTE)
    
    # For development testing
    if current_app.debug:
        custom_interval = request.form.get('customInterval')
        custom_time = request.form.get('customTime')
        if custom_interval:
            interval = int(custom_interval)
        if custom_time:
            hour, minute = map(int, custom_time.split(':'))
            schedule_time = datetime.time(hour, minute)
    
    current_time = datetime.datetime.now()
    next_run_time = current_time + datetime.timedelta(minutes=interval)
    
    new_schedule = ScraperSchedule(
        user_id=current_user.id,
        product=product,
        interval=interval,
        target_price=target_price,
        city=city,
        country=country,
        email_notification=True,
        active=True,
        last_run=current_time,
        next_run=next_run_time
    )
    
    db.session.add(new_schedule)
    db.session.commit()
    schedule_time = datetime.time(SCHEDULE_HOUR, SCHEDULE_MINUTE)

    scheduler.add_job(
            func=scheduled_job,
            args=[new_schedule.id, current_app._get_current_object()],
            trigger='cron',
            hour=schedule_time.hour,
            minute=schedule_time.minute,
            id=f'schedule_{new_schedule.id}',
            replace_existing=True
        )
    flash('Schedule created successfully', category='success')
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

@views.route('/update_location', methods=['POST'])
@login_required
def update_location():
    user = current_user
    user.city = request.form.get('city')
    user.country = request.form.get('country')
    db.session.commit()
    flash('Location updated successfully!', category='success')
    return redirect(url_for('views.scheduler_status'))

@views.route('/update_preferences', methods=['POST'])
@login_required
def update_preferences():
    email_notifications = request.form.get('email_notifications') == 'on'
    browser_notifications = request.form.get('browser_notifications') == 'on'
    
    # Update user preferences
    user = User.query.get(current_user.id)
    user.email_notifications = email_notifications
    user.browser_notifications = browser_notifications
    db.session.commit()
    
    flash('Notification preferences updated successfully', category='success')
    return redirect(url_for('views.scheduler_status'))

@views.route('/resume_schedule/<int:schedule_id>', methods=['POST'])
@login_required
def resume_schedule(schedule_id):
    from flask import current_app
    
    schedule = ScraperSchedule.query.get_or_404(schedule_id)
    if schedule.user_id != current_user.id:
        flash('Unauthorized access', category='error')
        return redirect(url_for('views.scheduler_status'))

    # Reactivate the schedule in database
    schedule.active = True
    current_time = datetime.datetime.now()
    schedule_time = datetime.time(SCHEDULE_HOUR, SCHEDULE_MINUTE)
    
    # Add job back to scheduler using cron trigger for daily execution
    scheduler.add_job(
        func=scheduled_job,
        args=[schedule.id, current_app._get_current_object()],
        trigger='cron',
        hour=schedule_time.hour,
        minute=schedule_time.minute,
        id=f'schedule_{schedule.id}',
        replace_existing=True
    )

    # Update next run time based on schedule time
    next_run = datetime.datetime.combine(current_time.date(), schedule_time)
    if current_time > next_run:
        next_run = next_run + datetime.timedelta(days=1)
    schedule.next_run = next_run
    
    db.session.commit()
    flash('Schedule resumed successfully', category='success')
    return redirect(url_for('views.scheduler_status'))


@views.route('/delete_schedule/<int:schedule_id>', methods=['POST'])
@login_required
def delete_schedule(schedule_id):
    schedule = ScraperSchedule.query.get_or_404(schedule_id)
    
    if schedule.user_id != current_user.id:
        flash('Unauthorized access', category='error')
        return redirect(url_for('views.scheduler_status'))

    # Remove from scheduler if job exists
    job_id = f'schedule_{schedule_id}'
    if job_id in [job.id for job in scheduler.get_jobs()]:
        scheduler.remove_job(job_id)

    # Delete the schedule from database
    db.session.delete(schedule)
    db.session.commit()

    flash('Schedule deleted successfully', category='success')
    return redirect(url_for('views.scheduler_status'))



from datetime import datetime
from . import scheduler, db
from .models import SavedSearch
from .scrapper import run_scraper

@scheduler.task('interval', id='check_scheduled_searches', minutes=1)
def check_scheduled_searches():
    current_time = datetime.now()
    searches = SavedSearch.query.all()
    
    for search in searches:
        # Check if search has exceeded its duration
        if search.duration:
            time_elapsed = (current_time - search.date_created).total_seconds() / 60
            if time_elapsed >= search.duration:
                search.schedule_type = None  # Deactivate schedule
                db.session.commit()
                continue
                
        if search.schedule_type == 'manual':
            interval_value = int(search.interval_value)
            interval_unit = search.interval_unit
            
            if interval_unit == 'minutes':
                minutes_passed = (current_time - search.last_run).total_seconds() / 60
                if minutes_passed >= interval_value:
                    run_scheduled_search(search)
            
            elif interval_unit == 'hours':
                hours_passed = (current_time - search.last_run).total_seconds() / 3600
                if hours_passed >= interval_value:
                    run_scheduled_search(search)
                    
        elif search.schedule_type == 'daily':
            if should_run_daily(search, current_time):
                run_scheduled_search(search)
                
        elif search.schedule_type == 'weekly':
            if should_run_weekly(search, current_time):
                run_scheduled_search(search)

def run_scheduled_search(search):
    run_scraper(
        city=search.city,
        country=search.country,
        product=search.product,
        target_price=search.target_price,
        should_send_email=search.email_notification,
        user_id=search.user_id
    )
    search.last_run = datetime.now()
    db.session.commit()

def should_run_daily(search, current_time):
    scheduled_time = datetime.strptime(search.schedule_time, '%H:%M').time()
    return current_time.time().hour == scheduled_time.hour and current_time.time().minute == scheduled_time.minute

def should_run_weekly(search, current_time):
    scheduled_days = search.schedule_days.split(',')
    current_day = current_time.strftime('%a')
    return current_day in scheduled_days and should_run_daily(search, current_time)
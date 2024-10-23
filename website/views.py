from flask import Blueprint, render_template, request, flash, jsonify
from flask_login import login_required, current_user
from .models import Note, ScraperResult
from . import db
from .scrapper import run_scraper

views = Blueprint('views', __name__)


@views.route('/', methods=['GET', 'POST'])
@login_required
def home():
    if request.method == 'POST':
        if 'note' in request.form:
            # Existing note functionality
            note = request.form.get('note')
            if len(note) < 1:
                flash('Note is too short!', category='error')
            else:
                new_note = Note(data=note, user_id=current_user.id)
                db.session.add(new_note)
                db.session.commit()
                flash('Note added!', category='success')
        elif 'run_scraper' in request.form:
            # Scraper functionality
            city = request.form.get('city')
            country = request.form.get('country')
            results = run_scraper(city, country)
            for result in results:
                new_result = ScraperResult(data=result, user_id=current_user.id)
                db.session.add(new_result)
            db.session.commit()
            flash('Scraper results added!', category='success')

    notes = Note.query.filter_by(user_id=current_user.id).all()
    scraper_results = ScraperResult.query.filter_by(user_id=current_user.id).all()
    return render_template("home.html", user=current_user, notes=notes, scraper_results=scraper_results)

@views.route('/delete-note', methods=['POST'])

def delete_note():  
     note = json.loads(request.data) # this function expects a JSON from the INDEX.js file 
     noteId = note['noteId']
     note = Note.query.get(noteId)
     if note:
         if note.user_id == current_user.id:
             db.session.delete(note)
             db.session.commit()#
     return jsonify({})
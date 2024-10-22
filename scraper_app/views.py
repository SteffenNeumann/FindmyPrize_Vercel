from django.shortcuts import render
from django.http import HttpResponse
import subprocess

def run_scraper(request):
    if request.method == 'POST':
        # Run the scraper script
        result = subprocess.run(['python', 'scraper.py'], capture_output=True, text=True)
        output = result.stdout
        return render(request, 'scraper_result.html', {'output': output})
    return render(request, 'scraper_form.html')

#!/bin/bash
pip install -r requirements.txt
python -m playwright install chromium
python -m playwright install-deps

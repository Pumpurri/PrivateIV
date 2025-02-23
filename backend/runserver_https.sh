#!/bin/bash

echo "Starting Django server with HTTPS..."
source venv/bin/activate
python3 manage.py runserver_plus --cert-file ../certs/localhost+2.pem --key-file ../certs/localhost+2-key.pem


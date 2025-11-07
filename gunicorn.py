import multiprocessing

# Network
bind = "0.0.0.0:5000"

# Workers
workers = max(2, multiprocessing.cpu_count() * 2 + 1)
worker_class = "sync"

# App loading
preload_app = True

# Logging
accesslog = "-"
errorlog = "-"
loglevel = "info"
capture_output = True

# Set your Django WSGI module here if desired, e.g.:
wsgi_app = "myerpv2.wsgi:application"

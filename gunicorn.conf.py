"""gunicorn.conf.py"""
bind = "0.0.0.0:5002"
workers = 2
worker_class = "sync"
timeout = 120
keepalive = 5
max_requests = 1000
max_requests_jitter = 200
accesslog = "-"
errorlog = "-"
loglevel = "info"

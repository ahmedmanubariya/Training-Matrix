import multiprocessing
import os

bind = os.environ.get('BIND', '0.0.0.0:5000')
workers = int(os.environ.get('WEB_CONCURRENCY', max(2, multiprocessing.cpu_count() * 2 + 1)))
threads = int(os.environ.get('WEB_THREADS', '2'))
timeout = int(os.environ.get('WEB_TIMEOUT', '120'))
accesslog = '-'
errorlog = '-'
capture_output = True

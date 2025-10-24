"""
WSGI config for gestores2 project.
"""

import os
import sys
from django.core.wsgi import get_wsgi_application
from pathlib import Path

# Build paths inside the project
BASE_DIR = Path(__file__).resolve().parent.parent

# Add the project directory to the Python path
if str(BASE_DIR) not in sys.path:
    sys.path.append(str(BASE_DIR))

# Configure Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'gestores2.settings')

try:
    application = get_wsgi_application()
except Exception as e:
    print(f"Error loading WSGI application: {e}")
    raise

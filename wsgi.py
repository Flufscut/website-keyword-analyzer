import os
import sys

# Add your project directory to the sys.path
project_home = os.path.expanduser('~/website-keyword-analyzer')
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Import your Flask app
from app import app as application

# Create upload directory if it doesn't exist
upload_dir = os.path.join(project_home, 'uploads')
os.makedirs(upload_dir, exist_ok=True) 
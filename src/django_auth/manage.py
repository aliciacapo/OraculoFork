#!/usr/bin/env python
import os
import sys
from pathlib import Path

# Add the project root and src directory to Python path
project_root = Path(__file__).resolve().parent.parent.parent
src_dir = project_root / 'src'
sys.path.insert(0, str(project_root))
sys.path.insert(0, str(src_dir))

if __name__ == '__main__':
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_auth.settings')
    try:
        from django.core.management import execute_from_command_line
    except ImportError as exc:
        raise ImportError(
            "Couldn't import Django. Are you sure it's installed and "
            "available on your PYTHONPATH environment variable? Did you "
            "forget to activate a virtual environment?"
        ) from exc
    execute_from_command_line(sys.argv)
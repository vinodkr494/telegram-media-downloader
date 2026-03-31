import os
import sys

def get_resource_path(relative_path: str) -> str:
    """Get the absolute path to a resource, supporting both development and PyInstaller bundles."""
    if hasattr(sys, '_MEIPASS'):
        # PyInstaller temporary extraction folder
        return os.path.join(sys._MEIPASS, relative_path)
    
    # Development: Resources are relative to the 'src' directory
    # Assume this file is in 'src/resource_utils.py'
    base_dir = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base_dir, relative_path)

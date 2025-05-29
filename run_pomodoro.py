
import sys
import os

project_root = os.path.dirname(os.path.abspath(__file__))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

try:
    from src.app import main as run_app
except ImportError as e:
    print("Error: Could not import the application.")
    print(f"Attempted to load from: {project_root}")
    print("Ensure 'src' directory exists under '{APP_DIR_NAME}' and contains all modules.")
    print(f"Details: {e}")
    sys.exit(1)
except Exception as e:
    print(f"An unexpected error occurred during import: {e}")
    sys.exit(1)

if __name__ == "__main__":
    run_app()

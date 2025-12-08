import sys
import os

# Add project root to sys.path
sys.path.insert(0, os.getcwd())

try:
    print("Attempting to import MessageService...")
    from app.services.message_service import MessageService
    print("Successfully imported MessageService")
except ImportError as e:
    print(f"ImportError: {e}")
    sys.exit(1)
except Exception as e:
    print(f"Error: {e}")
    sys.exit(1)

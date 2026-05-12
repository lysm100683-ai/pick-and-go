import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import backend_postgres as backend

def test():
    print("Testing Movement Cache...")
    # Add a mock cache directly using the function
    try:
        backend.save_movement_cache(37.5796, 126.9770, 37.5512, 126.9882, "driving", 1200, True)
        
        # Test Retrieval
        duration = backend.get_movement_cache(37.5796, 126.9770, 37.5512, 126.9882, "driving")
        print(f"Retrieved Duration: {duration}")

        # Test Cleanup
        backend.cleanup_old_movement_cache(180)
        print("Cleanup Ran Successfully.")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()

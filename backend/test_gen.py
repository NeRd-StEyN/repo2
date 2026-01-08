from lang import app
import os
import sys

def safe_print(*args, **kwargs):
    try:
        print(*args, **kwargs)
    except:
        pass

try:
    safe_print("Testing report generation...")
    topic = "Test Topic"
    language = "English"
    pages = 3
    
    for state in app.stream({"topic": topic, "language": language, "pages": pages}):
        safe_print(f"Step completed: {list(state.keys())}")
        if "report_generator" in state:
            safe_print("Success! PDF generated.")
            break
except Exception as e:
    import traceback
    safe_print("Failed!")
    traceback.print_exc()

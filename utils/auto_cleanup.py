import threading
import time
import shutil

def auto_cleanup(path, timeout=600):
    def _cleanup():
        time.sleep(timeout)
        shutil.rmtree(path, ignore_errors=True)
    threading.Thread(target=_cleanup, daemon=True).start()

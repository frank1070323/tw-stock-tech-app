from pathlib import Path
import sys

from app import app


if __name__ == "__main__":
    log_path = Path(__file__).with_name("server_runtime_5052.log")
    log_handle = log_path.open("a", encoding="utf-8")
    sys.stdout = log_handle
    sys.stderr = log_handle
    print("starting flask on 5052", flush=True)
    app.run(host="0.0.0.0", port=5052, debug=False)

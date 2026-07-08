import os
import sys
from pathlib import Path

TEST_DB = Path("/tmp/aishuati_backend_test.db")
TEST_DB.unlink(missing_ok=True)
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB}"
os.environ["UPLOAD_DIR"] = "/tmp/aishuati_uploads"
os.environ["DEBUG"] = "false"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

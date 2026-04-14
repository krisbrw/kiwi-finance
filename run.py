from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parent
APP_DIR = PROJECT_ROOT / "app"

sys.path.insert(0, str(APP_DIR))

from kiwi_finance.main import app
from kiwi_finance.database import init_db

if __name__ == "__main__":
    init_db()
    app.run(debug=True)
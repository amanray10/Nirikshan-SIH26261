import os
import tempfile

# Isolated database for tests; must be set before app.config is imported.
os.environ.setdefault("DATABASE_URL", f"sqlite:///{tempfile.mkdtemp()}/test.db")
os.environ.setdefault("LLM_BACKEND", "none")

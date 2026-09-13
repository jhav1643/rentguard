"""
RentGuard — Ingestion Entrypoint
Thin CLI entrypoint invoked by the Docker image
(`python -m services.ingestion.run_ingestion`). Configures logging once
for the whole process and delegates to the actual pipeline logic in
pipeline.py, translating a failure into a non-zero exit code so the
container/orchestrator can detect it.
"""
 
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from services.ingestion.pipeline import run_pipeline
 
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)
 
 
def main() -> int:
    try:
        run_pipeline()
    except Exception:
        logger.exception("Ingestion pipeline failed.")
        return 1
    return 0
 
 
if __name__ == "__main__":
    sys.exit(main())
 
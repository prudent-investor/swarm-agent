import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.rag import run_pipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run RAG ingestion and indexing pipeline.")
    parser.add_argument("--dry-run", action="store_true", help="Execute pipeline without embedding or indexing.")
    args = parser.parse_args()

    result = run_pipeline(dry_run=args.dry_run)
    print(
        json.dumps(
            {
                "dry_run": result.dry_run,
                "processed_urls": result.processed_urls,
                "raw_documents": result.raw_count,
                "chunks_created": result.chunks_count,
                "embedded_chunks": result.embedded_count,
                "index_items": result.index_count,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

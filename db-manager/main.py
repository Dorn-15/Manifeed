import asyncio

from app.services.migration_service import run_db_migrations
from app.services.result_consumer_service import run_result_consumer


def main() -> None:
    run_db_migrations()
    asyncio.run(run_result_consumer())


if __name__ == "__main__":
    main()

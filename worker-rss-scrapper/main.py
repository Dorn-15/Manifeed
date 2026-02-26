import asyncio

from app.services.scrape_job_service import run_scrape_worker


def main() -> None:
    asyncio.run(run_scrape_worker())


if __name__ == "__main__":
    main()

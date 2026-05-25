import logging

from config import TOKEN
from database import init_db
from bot import build_application

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)


def main() -> None:
    logger.info("Initializing database...")
    init_db()

    logger.info("Starting DayCommit bot...")
    app = build_application(TOKEN)
    app.run_polling()


if __name__ == "__main__":
    main()

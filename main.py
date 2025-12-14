import threading
import logging

from sqlalchemy import text

from web_server import app
from mqtt_client import mqtt_client
from config import config
from database import db_manager

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def initialize_system():
    """Инициализация всей системы"""
    try:
        logger.info("Initializing Smart Water Meter System...")

        # Подключение к MQTT
        logger.info(f"Connecting to MQTT broker at {config.MQTT_HOST}:{config.MQTT_PORT}")
        mqtt_client.connect()

        # Проверка подключения к БД
        logger.info("Testing database connection...")
        with db_manager.get_session() as session:
            session.execute(text("SELECT 1"))
        logger.info("Database connection successful")

        logger.info("System initialization complete")

    except Exception as e:
        logger.error(f"Failed to initialize system: {e}")
        raise


def run_web_server():
    """Запуск веб-сервера"""
    logger.info(f"Starting web server on port {config.API_PORT}")
    app.run(host='0.0.0.0', port=config.API_PORT, debug=config.DEBUG)


if __name__ == '__main__':
    # Инициализация системы
    initialize_system()

    try:
        # Запуск веб-сервера в основном потоке
        run_web_server()
    except KeyboardInterrupt:
        logger.info("Shutting down system...")
        mqtt_client.disconnect()
        logger.info("System shutdown complete")
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        mqtt_client.disconnect()
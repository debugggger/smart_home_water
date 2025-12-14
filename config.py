import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    # PostgreSQL конфигурация
    POSTGRES_HOST = os.getenv('POSTGRES_HOST', 'localhost')
    POSTGRES_PORT = os.getenv('POSTGRES_PORT', '5432')
    POSTGRES_USER = os.getenv('POSTGRES_USER', 'home_admin')
    POSTGRES_PASSWORD = os.getenv('POSTGRES_PASSWORD', 'admin007')
    POSTGRES_DB = os.getenv('POSTGRES_DB', 'smart_home')

    # MQTT конфигурация
    MQTT_HOST = os.getenv('MQTT_HOST', 'localhost')
    MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
    MQTT_KEEPALIVE = int(os.getenv('MQTT_KEEPALIVE', '60'))
    MQTT_TOPICS = ['water_meter/#', 'sensors/#', 'status/#']

    # Flask конфигурация
    SECRET_KEY = os.getenv('SECRET_KEY', 'dev-secret-key')
    DEBUG = os.getenv('FLASK_DEBUG', 'False').lower() == 'true'

    # API конфигурация
    API_PORT = int(os.getenv('API_PORT', '5001'))

    @property
    def DATABASE_URL(self):
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"


config = Config()
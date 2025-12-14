import paho.mqtt.client as mqtt
import json
import logging
from database import db_manager
from config import config
from datetime import datetime

logger = logging.getLogger(__name__)


class MQTTClient:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

        # Маппинг контроллеров к ID счетчиков
        # Можно настроить через конфиг или базу данных
        self.controller_mapping = {
            'water_meter_controller_001': 1,  # Холодная вода
            'water_meter_controller_002': 2  # Горячая вода
        }

        # Создаем счетчики при инициализации если их нет
        self.initialize_counters()

    def initialize_counters(self):
        """Создание счетчиков при запуске если их нет"""
        try:
            cold_id = db_manager.create_counter_if_not_exists("Холодная вода")
            hot_id = db_manager.create_counter_if_not_exists("Горячая вода")

            # Обновляем маппинг
            self.controller_mapping = {
                'water_meter_controller_001': cold_id,
                'water_meter_controller_002': hot_id
            }

            logger.info(f"Initialized counters: Cold={cold_id}, Hot={hot_id}")

        except Exception as e:
            logger.error(f"Error initializing counters: {e}")

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            logger.info("Connected to MQTT Broker")
            # Подписываемся на топики
            topics = [
                ("water_meter/pulse/#", 0),  # Импульсы счетчиков
                ("water_meter/status", 0),  # Статус контроллеров
                ("water_meter/command", 0)  # Команды
            ]
            client.subscribe(topics)
            logger.info("Subscribed to MQTT topics")
        else:
            logger.error(f"Failed to connect to MQTT Broker, return code {rc}")

    def on_message(self, client, userdata, msg):
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')

            logger.debug(f"Received MQTT: {topic} -> {payload}")

            if topic.startswith('water_meter/pulse/'):
                self.handle_pulse_message(topic, payload)
            elif topic == 'water_meter/status':
                self.handle_status_message(payload)

        except Exception as e:
            logger.error(f"Error processing MQTT message: {e}")

    def handle_pulse_message(self, topic, payload):
        """Обработка импульсных сообщений"""
        try:
            data = json.loads(payload)

            # Извлекаем ID контроллера из топика
            parts = topic.split('/')
            if len(parts) >= 3:
                controller_id = parts[2]
            else:
                controller_id = data.get('controller_id', 'unknown')

            # Получаем ID счетчика из маппинга
            counter_id = self.controller_mapping.get(controller_id)

            if not counter_id:
                logger.error(f"Unknown controller: {controller_id}")
                return

            # Получаем количество импульсов (по умолчанию 1)
            pulse_count = data.get('pulse_count', 1)

            logger.info(f"Pulse received from {controller_id} (counter {counter_id}): {pulse_count} pulses")

            # Обрабатываем каждый импульс отдельно
            for i in range(pulse_count):
                result = db_manager.add_water_pulse(counter_id)

                if not result['success']:
                    logger.error(f"Failed to process pulse: {result.get('error')}")

            logger.info(f"Successfully processed {pulse_count} pulses from {controller_id}")

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON in pulse message: {e}")
        except Exception as e:
            logger.error(f"Error handling pulse message: {e}")

    def handle_status_message(self, payload):
        """Обработка статусных сообщений"""
        try:
            data = json.loads(payload)
            controller_id = data.get('controller_id', 'unknown')
            logger.info(f"Status from {controller_id}: {data.get('status', 'unknown')}")

        except Exception as e:
            logger.error(f"Error handling status message: {e}")

    def connect(self):
        try:
            self.client.connect(config.MQTT_HOST, config.MQTT_PORT, config.MQTT_KEEPALIVE)
            self.client.loop_start()
            logger.info(f"MQTT client connected to {config.MQTT_HOST}:{config.MQTT_PORT}")
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")

    def disconnect(self):
        self.client.loop_stop()
        self.client.disconnect()
        logger.info("MQTT client disconnected")


# Глобальный экземпляр
mqtt_client = MQTTClient()
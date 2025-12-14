from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.sql import func
from contextlib import contextmanager
from models import WaterCounter, WaterMeterLog, init_db
from config import config
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)


class DatabaseManager:
    def __init__(self):
        self.engine = create_engine(config.DATABASE_URL)
        self.SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=self.engine)
        init_db()
        logger.info("Database initialized")

    @contextmanager
    def get_session(self):
        session = self.SessionLocal()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()

    def add_water_pulse(self, sensor_id: int):
        """
        Добавление импульса счетчика.
        Каждый импульс = 10 литров = 0.01 м³
        """
        with self.get_session() as session:
            try:
                # Находим счетчик
                counter = session.query(WaterCounter).filter(
                    WaterCounter.id == sensor_id
                ).first()

                if not counter:
                    logger.error(f"Counter with id {sensor_id} not found")
                    return {'success': False, 'error': f'Counter {sensor_id} not found'}

                # Создаем запись в логе
                log_entry = WaterMeterLog(
                    id_sensor=sensor_id,
                    time=datetime.now()
                )
                session.add(log_entry)

                # Обновляем счетчик
                counter.value += 0.01  # добавляем 0.01 м³ (10 литров)
                counter.last_time = datetime.now()

                logger.info(f"Added pulse for counter {sensor_id} ({counter.name}): {counter.value:.3f} m³")

                return {
                    'success': True,
                    'counter_id': sensor_id,
                    'counter_name': counter.name,
                    'new_value': counter.value,
                    'liters_added': 10.0,
                    'timestamp': datetime.now().isoformat()
                }

            except Exception as e:
                logger.error(f"Error adding water pulse: {e}")
                return {'success': False, 'error': str(e)}

    def get_current_readings(self):
        """Получение текущих показаний всех счетчиков"""
        with self.get_session() as session:
            try:
                counters = session.query(WaterCounter).all()
                return [counter.to_dict() for counter in counters]
            except Exception as e:
                logger.error(f"Error getting current readings: {e}")
                return []

    def get_counter_history(self, counter_id: int, limit: int = 100):
        """Получение истории импульсов конкретного счетчика"""
        with self.get_session() as session:
            try:
                logs = session.query(WaterMeterLog).filter(
                    WaterMeterLog.id_sensor == counter_id
                ).order_by(WaterMeterLog.time.desc()).limit(limit).all()

                return [log.to_dict() for log in logs]
            except Exception as e:
                logger.error(f"Error getting counter history: {e}")
                return []

    def get_consumption_for_period(self, counter_id: int, start_time: datetime, end_time: datetime):
        """
        Расчет расхода за период для конкретного счетчика.
        Возвращает количество импульсов и расход в м³
        """
        with self.get_session() as session:
            try:
                # Считаем количество импульсов за период
                pulse_count = session.query(WaterMeterLog).filter(
                    WaterMeterLog.id_sensor == counter_id,
                    WaterMeterLog.time >= start_time,
                    WaterMeterLog.time <= end_time
                ).count()

                # Расход = количество импульсов * 0.01 м³
                consumption = pulse_count * 0.01

                return {
                    'counter_id': counter_id,
                    'pulse_count': pulse_count,
                    'consumption_m3': consumption,
                    'consumption_liters': consumption * 1000,
                    'start_time': start_time.isoformat(),
                    'end_time': end_time.isoformat()
                }

            except Exception as e:
                logger.error(f"Error calculating consumption: {e}")
                return {'error': str(e)}

    def get_all_consumption_for_period(self, start_time: datetime, end_time: datetime):
        """Расчет расхода за период для всех счетчиков"""
        with self.get_session() as session:
            try:
                # Получаем все счетчики
                counters = session.query(WaterCounter).all()
                results = []

                for counter in counters:
                    pulse_count = session.query(WaterMeterLog).filter(
                        WaterMeterLog.id_sensor == counter.id,
                        WaterMeterLog.time >= start_time,
                        WaterMeterLog.time <= end_time
                    ).count()

                    consumption = pulse_count * 0.01

                    results.append({
                        'counter_id': counter.id,
                        'counter_name': counter.name,
                        'pulse_count': pulse_count,
                        'consumption_m3': consumption,
                        'consumption_liters': consumption * 1000,
                        'current_value': counter.value
                    })

                return results

            except Exception as e:
                logger.error(f"Error calculating all consumption: {e}")
                return []

    def create_counter_if_not_exists(self, name: str):
        """Создание счетчика если его нет"""
        with self.get_session() as session:
            try:
                # Проверяем, существует ли счетчик с таким именем
                existing = session.query(WaterCounter).filter(
                    WaterCounter.name == name
                ).first()

                if existing:
                    logger.info(f"Counter '{name}' already exists with id {existing.id}")
                    return existing.id

                # Создаем новый счетчик
                new_counter = WaterCounter(
                    name=name,
                    value=0.0
                )
                session.add(new_counter)
                session.flush()  # Получаем ID

                logger.info(f"Created new counter '{name}' with id {new_counter.id}")
                return new_counter.id

            except Exception as e:
                logger.error(f"Error creating counter: {e}")
                return None

    def reset_counter(self, counter_id: int):
        """Сброс счетчика (обнуление значения и очистка логов)"""
        with self.get_session() as session:
            try:
                counter = session.query(WaterCounter).filter(
                    WaterCounter.id == counter_id
                ).first()

                if not counter:
                    return {'success': False, 'error': 'Counter not found'}

                # Обнуляем значение
                old_value = counter.value
                counter.value = 0.0
                counter.last_time = datetime.now()

                # Удаляем все логи этого счетчика
                session.query(WaterMeterLog).filter(
                    WaterMeterLog.id_sensor == counter_id
                ).delete()

                logger.info(f"Reset counter {counter_id} ({counter.name}) from {old_value} to 0")

                return {
                    'success': True,
                    'counter_id': counter_id,
                    'counter_name': counter.name,
                    'old_value': old_value,
                    'new_value': 0.0
                }

            except Exception as e:
                logger.error(f"Error resetting counter: {e}")
                return {'success': False, 'error': str(e)}


# Глобальный экземпляр
db_manager = DatabaseManager()
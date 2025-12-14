from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from config import config

Base = declarative_base()
engine = create_engine(config.DATABASE_URL)


class WaterCounter(Base):
    __tablename__ = 'water_counter'

    id = Column(Integer, primary_key=True)
    name = Column(String(100), nullable=False)  # название счетчика
    value = Column(Float, nullable=False, default=0.0)  # текущее показание в м³
    last_time = Column(DateTime(timezone=True), default=func.now())  # время последнего обновления

    # Связь с логами
    logs = relationship("WaterMeterLog", back_populates="counter")

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'value': self.value,
            'last_time': self.last_time.isoformat() if self.last_time else None
        }


class WaterMeterLog(Base):
    __tablename__ = 'water_meter_log'

    id = Column(Integer, primary_key=True)
    id_sensor = Column(Integer, ForeignKey('water_counter.id'), nullable=False)  # ссылка на счетчик
    time = Column(DateTime(timezone=True), default=func.now())  # время импульса

    # Связь со счетчиком
    counter = relationship("WaterCounter", back_populates="logs")

    def to_dict(self):
        return {
            'id': self.id,
            'id_sensor': self.id_sensor,
            'time': self.time.isoformat() if self.time else None
        }


def init_db():
    Base.metadata.create_all(engine)
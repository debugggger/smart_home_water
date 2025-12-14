from flask import Flask, render_template, jsonify, request
from flask_cors import CORS
from sqlalchemy import text
import logging
from database import db_manager
from mqtt_client import mqtt_client
from config import config
from datetime import datetime

app = Flask(__name__)
app.config['SECRET_KEY'] = config.SECRET_KEY
CORS(app)

logger = logging.getLogger(__name__)


@app.route('/')
def index():
    """Главная страница"""
    return render_template('index.html')


@app.route('/api/current', methods=['GET'])
def get_current_readings():
    """Получение текущих показаний всех счетчиков"""
    try:
        readings = db_manager.get_current_readings()
        return jsonify({
            'success': True,
            'data': readings,
            'timestamp': datetime.now().isoformat(),
            'count': len(readings)
        })
    except Exception as e:
        logger.error(f"Error getting current readings: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/counter/<int:counter_id>', methods=['GET'])
def get_counter_data(counter_id):
    """Получение данных конкретного счетчика"""
    try:
        # Получаем все счетчики
        all_counters = db_manager.get_current_readings()
        current = next((c for c in all_counters if c['id'] == counter_id), None)

        if not current:
            return jsonify({'success': False, 'error': 'Counter not found'}), 404

        # История
        limit = request.args.get('limit', default=50, type=int)
        history = db_manager.get_counter_history(counter_id, limit)

        return jsonify({
            'success': True,
            'current': current,
            'history': history,
            'history_count': len(history)
        })
    except Exception as e:
        logger.error(f"Error getting counter data: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/consumption/period', methods=['POST'])
def get_consumption_for_period():
    """Расчет расхода за период"""
    try:
        data = request.json
        if not data:
            return jsonify({'success': False, 'error': 'No data provided'}), 400

        start_str = data.get('start_time')
        end_str = data.get('end_time')
        counter_id = data.get('counter_id')  # опционально, если не указан - все счетчики

        if not start_str or not end_str:
            return jsonify({'success': False, 'error': 'start_time and end_time required'}), 400

        # Парсим время
        try:
            start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
            end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
        except ValueError as e:
            return jsonify({'success': False, 'error': f'Invalid date format: {e}'}), 400

        if start_time >= end_time:
            return jsonify({'success': False, 'error': 'start_time must be before end_time'}), 400

        # Рассчитываем расход
        if counter_id:
            # Для конкретного счетчика
            result = db_manager.get_consumption_for_period(counter_id, start_time, end_time)
            if 'error' in result:
                return jsonify({'success': False, 'error': result['error']}), 500

            return jsonify({
                'success': True,
                'data': result,
                'counter_id': counter_id
            })
        else:
            # Для всех счетчиков
            results = db_manager.get_all_consumption_for_period(start_time, end_time)

            return jsonify({
                'success': True,
                'data': results,
                'count': len(results),
                'start_time': start_time.isoformat(),
                'end_time': end_time.isoformat()
            })

    except Exception as e:
        logger.error(f"Error calculating consumption: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/counter/reset/<int:counter_id>', methods=['POST'])
def reset_counter(counter_id):
    """Сброс счетчика"""
    try:
        result = db_manager.reset_counter(counter_id)
        if result['success']:
            return jsonify({
                'success': True,
                'message': f"Counter {counter_id} reset successfully",
                'data': result
            })
        else:
            return jsonify({'success': False, 'error': result.get('error', 'Unknown error')}), 500
    except Exception as e:
        logger.error(f"Error resetting counter: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """Проверка здоровья системы"""
    try:
        # Проверяем подключение к базе данных
        with db_manager.get_session() as session:
            session.execute(text("SELECT 1"))

        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'database': 'connected',
            'version': '1.0.0'
        })
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500


# Добавьте эти эндпоинты в web_server.py

@app.route('/api/grafana/metrics', methods=['GET'])
def get_grafana_metrics():
    """Метрики для Grafana (простые агрегированные данные)"""
    try:
        with db_manager.get_session() as session:
            from sqlalchemy import text

            # Общее потребление за последние 24 часа
            query = text("""
                SELECT
                    wc.name as counter,
                    COUNT(*) as pulses,
                    COUNT(*) * 10 as liters_24h,
                    COUNT(*) * 0.01 as cubic_meters_24h
                FROM water_meter_log wml
                JOIN water_counter wc ON wml.id_sensor = wc.id
                WHERE wml.time >= NOW() - INTERVAL '24 hours'
                GROUP BY wc.name
            """)

            result = session.execute(query)
            metrics = []

            for row in result:
                metrics.append({
                    'counter': row[0],
                    'pulses_24h': row[1],
                    'liters_24h': row[2],
                    'cubic_meters_24h': row[3]
                })

            return jsonify({
                'success': True,
                'metrics': metrics,
                'timestamp': datetime.now().isoformat()
            })

    except Exception as e:
        logger.error(f"Error getting Grafana metrics: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/grafana/timeseries', methods=['GET'])
def get_grafana_timeseries():
    """Временные ряды для Grafana"""
    try:
        hours = request.args.get('hours', default=24, type=int)

        with db_manager.get_session() as session:
            from sqlalchemy import text

            query = text("""
                SELECT
                    date_trunc('hour', wml.time) as timestamp,
                    wc.name as counter,
                    COUNT(*) as pulses,
                    COUNT(*) * 10 as liters
                FROM water_meter_log wml
                JOIN water_counter wc ON wml.id_sensor = wc.id
                WHERE wml.time >= NOW() - INTERVAL ':hours hours'
                GROUP BY date_trunc('hour', wml.time), wc.name
                ORDER BY timestamp
            """)

            result = session.execute(query, {'hours': hours})
            timeseries = []

            for row in result:
                timeseries.append({
                    'timestamp': row[0].isoformat() if row[0] else None,
                    'counter': row[1],
                    'pulses': row[2],
                    'liters': row[3]
                })

            return jsonify({
                'success': True,
                'data': timeseries,
                'hours': hours
            })

    except Exception as e:
        logger.error(f"Error getting timeseries: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500


if __name__ == '__main__':
    # Инициализация системы
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

        # Создаем счетчики если их нет
        logger.info("Initializing counters...")
        db_manager.create_counter_if_not_exists("Холодная вода")
        db_manager.create_counter_if_not_exists("Горячая вода")

        logger.info("System started successfully")

    except Exception as e:
        logger.error(f"Failed to start system: {e}")

    app.run(host='0.0.0.0', port=5000, debug=config.DEBUG)
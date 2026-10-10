import json
import logging
import ssl
import paho.mqtt.client as mqtt
from pydantic import ValidationError
from backend.database import SessionLocal, Telemetry
from backend.schemas.telemetry import TelemetryCreate
from backend.config import MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, CA_CERT_PATH

logger = logging.getLogger(__name__)

def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        logger.info(f"Connected to MQTT Broker at {MQTT_BROKER}:{MQTT_PORT}")
        client.subscribe(MQTT_TOPIC)
        logger.info(f"Subscribed to topic: {MQTT_TOPIC}")
    else:
        logger.error(f"Failed to connect to MQTT Broker, return code {rc}")

def on_message(client, userdata, msg):
    logger.info(f"Received message on topic {msg.topic}")
    payload_str = msg.payload.decode('utf-8')
    try:
        data = json.loads(payload_str)
        # Pydantic validation
        telemetry_data = TelemetryCreate(**data)
        
        # Save to database
        db = SessionLocal()
        try:
            db_telemetry = Telemetry(**telemetry_data.model_dump())
            db.add(db_telemetry)
            db.commit()
            logger.info("Telemetry data saved successfully from MQTT.")
        except Exception as e:
            db.rollback()
            logger.error(f"Database error while saving MQTT data: {e}")
        finally:
            db.close()
            
    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from MQTT message: {payload_str}")
    except ValidationError as e:
        logger.error(f"Validation error for MQTT data: {e.errors()}")
    except Exception as e:
        logger.error(f"Unexpected error processing MQTT message: {e}")

def get_mqtt_client() -> mqtt.Client:
    client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    client.tls_set(ca_certs=CA_CERT_PATH, tls_version=ssl.PROTOCOL_TLSv1_2)
    client.on_connect = on_connect
    client.on_message = on_message
    return client

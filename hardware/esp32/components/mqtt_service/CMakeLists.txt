idf_component_register(SRCS "mqtt_service.c"
                       INCLUDE_DIRS "include"
                       REQUIRES mqtt esp_driver_gpio freertos log telemetry esp_timer
                       EMBED_TXTFILES "mosquitto.org.crt")

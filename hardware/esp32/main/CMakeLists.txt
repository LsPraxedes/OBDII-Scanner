idf_component_register(SRCS "main.c"
                       INCLUDE_DIRS "."
                       REQUIRES telemetry obd2_can wifi_manager mqtt_service log)

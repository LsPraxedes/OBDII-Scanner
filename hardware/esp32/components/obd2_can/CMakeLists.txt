idf_component_register(SRCS "obd2_can.c"
                       INCLUDE_DIRS "include"
                       REQUIRES esp_driver_twai esp_driver_gpio freertos log telemetry esp_timer)

#include <WiFi.h>
#include <WiFiClientSecure.h>
#include <PubSubClient.h>

// ==========================================
// 1. CONFIGURAÇÕES DE WI-FI
// ==========================================
const char* ssid = "POCO X7 Pro";
const char* password = "umaoitoo";

// ==========================================
// 2. CONFIGURAÇÕES DO BROKER MQTT (MQTTS)
// ==========================================
const char* mqtt_server = "test.mosquitto.org"; // IP ou Domínio do broker Mosquitto
const int   mqtt_port = 8883;               // Porta padrão para MQTTS (SSL/TLS)
const char* mqtt_user = ""; // Deixe vazio "" se não usar
const char* mqtt_pass = "";   // Deixe vazio "" se não usar

const char* topico_envio = "praxedes";

// ==========================================
// 3. CERTIFICADO CA DO BROKER (PEM/X.509)
// ==========================================
// Cole aqui o certificado raiz (CA) que assinou o certificado do seu broker.
// Se estiver testando em rede local sem validação estrita, veja a nota abaixo.
const char* root_ca = "-----BEGIN CERTIFICATE-----\n" \
"MIIEAzCCAuugAwIBAgIUBY1hlCGvdj4NhBXkZ/uLUZNILAwwDQYJKoZIhvcNAQEL\n" \
"BQAwgZAxCzAJBgNVBAYTAkdCMRcwFQYDVQQIDA5Vbml0ZWQgS2luZ2RvbTEOMAwG\n" \
"A1UEBwwFRGVyYnkxEjAQBgNVBAoMCU1vc3F1aXR0bzELMAkGA1UECwwCQ0ExFjAU\n" \
"BgNVBAMMDW1vc3F1aXR0by5vcmcxHzAdBgkqhkiG9w0BCQEWEHJvZ2VyQGF0Y2hv\n" \
"by5vcmcwHhcNMjAwNjA5MTEwNjM5WhcNMzAwNjA3MTEwNjM5WjCBkDELMAkGA1UE\n" \
"BhMCR0IxFzAVBgNVBAgMDlVuaXRlZCBLaW5nZG9tMQ4wDAYDVQQHDAVEZXJieTES\n" \
"MBAGA1UECgwJTW9zcXVpdHRvMQswCQYDVQQLDAJDQTEWMBQGA1UEAwwNbW9zcXVp\n" \
"dHRvLm9yZzEfMB0GCSqGSIb3DQEJARYQcm9nZXJAYXRjaG9vLm9yZzCCASIwDQYJ\n" \
"KoZIhvcNAQEBBQADggEPADCCAQoCggEBAME0HKmIzfTOwkKLT3THHe+ObdizamPg\n" \
"UZmD64Tf3zJdNeYGYn4CEXbyP6fy3tWc8S2boW6dzrH8SdFf9uo320GJA9B7U1FW\n" \
"Te3xda/Lm3JFfaHjkWw7jBwcauQZjpGINHapHRlpiCZsquAthOgxW9SgDgYlGzEA\n" \
"s06pkEFiMw+qDfLo/sxFKB6vQlFekMeCymjLCbNwPJyqyhFmPWwio/PDMruBTzPH\n" \
"3cioBnrJWKXc3OjXdLGFJOfj7pP0j/dr2LH72eSvv3PQQFl90CZPFhrCUcRHSSxo\n" \
"E6yjGOdnz7f6PveLIB574kQORwt8ePn0yidrTC1ictikED3nHYhMUOUCAwEAAaNT\n" \
"MFEwHQYDVR0OBBYEFPVV6xBUFPiGKDyo5V3+Hbh4N9YSMB8GA1UdIwQYMBaAFPVV\n" \
"6xBUFPiGKDyo5V3+Hbh4N9YSMA8GA1UdEwEB/wQFMAMBAf8wDQYJKoZIhvcNAQEL\n" \
"BQADggEBAGa9kS21N70ThM6/Hj9D7mbVxKLBjVWe2TPsGfbl3rEDfZ+OKRZ2j6AC\n" \
"6r7jb4TZO3dzF2p6dgbrlU71Y/4K0TdzIjRj3cQ3KSm41JvUQ0hZ/c04iGDg/xWf\n" \
"+pp58nfPAYwuerruPNWmlStWAXf0UTqRtg4hQDWBuUFDJTuWuuBvEXudz74eh/wK\n" \
"sMwfu1HFvjy5Z0iMDU8PUDepjVolOCue9ashlS4EB5IECdSR2TItnAIiIwimx839\n" \
"LdUdRudafMu5T5Xma182OC0/u/xRlEm+tvKGGmfFcN0piqVl8OrSPBgIlb+1IKJE\n" \
"m/XriWr/Cq4h/JfB7NTsezVslgkBaoU=\n" \
"-----END CERTIFICATE----- \n";

WiFiClientSecure espClientSecure;
PubSubClient client(espClientSecure);

// ==========================================
// FUNÇÕES AUXILIARES
// ==========================================
void setup_wifi() {
  delay(10);
  Serial.println();
  Serial.print("Conectando-se a ");
  Serial.println(ssid);

  WiFi.mode(WIFI_STA);
  WiFi.begin(ssid, password);

  while (WiFi.status() != WL_CONNECTED) {
    delay(500);
    Serial.print(".");
  }

  Serial.println("");
  Serial.println("Wi-Fi conectado com sucesso!");
  Serial.print("Endereço IP: ");
  Serial.println(WiFi.localIP());
}

void reconnect() {
  // Loop até conseguir conectar no Broker
  while (!client.connected()) {
    Serial.print("Tentando conexão MQTT Segura (MQTTS)... ");
    
    // Gera um ID de cliente aleatório
    String clientId = "ESP32Client-" + String(random(0xffff), HEX);

    // Tenta conectar (com usuário/senha, se configurado)
    if (client.connect(clientId.c_str(), mqtt_user, mqtt_pass)) {
      Serial.println("Conectado ao Mosquitto!");
    } else {
      Serial.print("Falhou, rc=");
      Serial.print(client.state());
      Serial.println(" -> tentando novamente em 5 segundos");
      delay(5000);
    }
  }
}

// ==========================================
// SETUP E LOOP PRINCIPAL
// ==========================================
void setup() {
  Serial.begin(115200);
  setup_wifi();

  // Configura o certificado CA para validar o servidor SSL
  espClientSecure.setCACert(root_ca);
  
  // NOTA: Caso esteja em ambiente de teste apenas e não tenha o certificado CA em mãos:
  // espClientSecure.setInsecure(); // DESCOMENTE ESTA LINHA e comente setCACert(root_ca)

  client.setServer(mqtt_server, mqtt_port);
}

void loop() {
  if (!client.connected()) {
    reconnect();
  }
  client.loop();

  // Exemplo: Publica uma mensagem a cada 10 segundos
  static unsigned long ultimoEnvio = 0;
  if (millis() - ultimoEnvio > 1000) {
    ultimoEnvio = millis();

    String mensagem = "Olá do ESP32 via MQTTS! millis: " + String(millis());
    
    Serial.print("Publicando no tópico '");
    Serial.print(topico_envio);
    Serial.print("': ");
    Serial.println(mensagem);

    // Envia a mensagem para o tópico "praxedes"
    client.publish(topico_envio, mensagem.c_str());
  }
}
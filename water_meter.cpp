#include <ESP8266WiFi.h>
#include <PubSubClient.h>
#include <ArduinoJson.h>
#include <Ticker.h>

// WiFi
const char* WIFI_SSID = "";
const char* WIFI_PASSWORD = "";

// MQTT
const char* MQTT_SERVER = "192.168.12.12";  
const int MQTT_PORT = 1883;

const char* CONTROLLER_ID = "water_meter_controller_001";  
// const char* CONTROLLER_ID = "water_meter_controller_002";

const char* METER_NAME = "Холодная вода";  
// const char* METER_NAME = "Горячая вода";   

const int WATER_PIN = D1;

const float LITERS_PER_PULSE = 10.0;  
const unsigned long DEBOUNCE_DELAY = 50; 
// Топики MQTT
const char* TOPIC_PULSE = "water_meter/pulse/"; 
const char* TOPIC_STATUS = "water_meter/status";
const char* TOPIC_COMMAND = "water_meter/command/"; 

const unsigned long STATUS_INTERVAL = 30000;  

WiFiClient wifiClient;
PubSubClient mqttClient(wifiClient);
Ticker statusTicker;

volatile unsigned long pulseCount = 0;
volatile unsigned long lastPulseTime = 0;
volatile bool pulseTriggered = false;

unsigned long totalPulses = 0;
unsigned long lastStatusSend = 0;
unsigned long bootTime = 0;

ICACHE_RAM_ATTR void handleWaterPulse() {
  unsigned long currentTime = millis();
  
  if (currentTime - lastPulseTime > DEBOUNCE_DELAY) {
    pulseCount++;
    totalPulses++;
    lastPulseTime = currentTime;
    pulseTriggered = true;
  }
}

void sendPulseMessage() {
  if (pulseCount == 0) return;
  
  StaticJsonDocument<200> doc;
  char messageBuffer[200];
  char topicBuffer[100];
  
  doc["controller_id"] = CONTROLLER_ID;
  doc["meter_name"] = METER_NAME;
  doc["pulse_count"] = pulseCount;
  doc["liters"] = pulseCount * LITERS_PER_PULSE;
  doc["timestamp"] = millis();
  
  serializeJson(doc, messageBuffer);
  
  strcpy(topicBuffer, TOPIC_PULSE);
  strcat(topicBuffer, CONTROLLER_ID);
  
  if (mqttClient.publish(topicBuffer, messageBuffer)) {
    Serial.print("Pulse sent: ");
    Serial.print(pulseCount);
    Serial.print(" pulses (");
    Serial.print(pulseCount * LITERS_PER_PULSE);
    Serial.println("L)");
  } else {
    Serial.println("Failed to send pulse message");
  }
  
  pulseCount = 0;
}

void sendStatusMessage() {
  StaticJsonDocument<300> doc;
  char messageBuffer[300];
  
  doc["controller_id"] = CONTROLLER_ID;
  doc["status"] = "online";
  doc["ip_address"] = WiFi.localIP().toString();
  doc["rssi"] = WiFi.RSSI();
  doc["free_heap"] = ESP.getFreeHeap();
  doc["uptime"] = (millis() - bootTime) / 1000;
  doc["total_pulses"] = totalPulses;
  doc["total_liters"] = totalPulses * LITERS_PER_PULSE;
  doc["firmware_version"] = "1.0.0";
  doc["timestamp"] = millis();
  
  serializeJson(doc, messageBuffer);
  
  if (mqttClient.publish(TOPIC_STATUS, messageBuffer)) {
    Serial.println("Status sent");
  } else {
    Serial.println("Failed to send status message");
  }
}

void mqttCallback(char* topic, byte* payload, unsigned int length) {
  Serial.print("Message arrived [");
  Serial.print(topic);
  Serial.print("]: ");
  
  char message[length + 1];
  for (unsigned int i = 0; i < length; i++) {
    message[i] = (char)payload[i];
  }
  message[length] = '\0';
  
  Serial.println(message);
  
  StaticJsonDocument<200> doc;
  DeserializationError error = deserializeJson(doc, message);
  
  if (!error) {
    const char* command = doc["command"];
    
    if (strcmp(command, "reset") == 0) {
     
      totalPulses = 0;
      pulseCount = 0;
      Serial.println("Counter reset by command");
      
      sendStatusMessage();
      
    } else if (strcmp(command, "status") == 0) {
      
      sendStatusMessage();
      
    } else if (strcmp(command, "test") == 0) {
      
      Serial.println("Test command received");
    }
  }
}

void setupWiFi() {
  Serial.println();
  Serial.print("Connecting to ");
  Serial.println(WIFI_SSID);
  
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);
  WiFi.mode(WIFI_STA);
  
  int attempts = 0;
  while (WiFi.status() != WL_CONNECTED && attempts < 20) {
    delay(500);
    Serial.print(".");
    attempts++;
  }
  
  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("");
    Serial.println("WiFi connected");
    Serial.print("IP address: ");
    Serial.println(WiFi.localIP());
  } else {
    Serial.println("");
    Serial.println("WiFi connection failed");
    ESP.restart();
  }
}

void reconnectMQTT() {
  while (!mqttClient.connected()) {
    Serial.print("Attempting MQTT connection...");
    
    if (mqttClient.connect(CONTROLLER_ID)) {
      Serial.println("connected");
      
      // Подписываемся на команды
      char commandTopic[100];
      strcpy(commandTopic, TOPIC_COMMAND);
      strcat(commandTopic, CONTROLLER_ID);
      
      mqttClient.subscribe(commandTopic);
      Serial.print("Subscribed to: ");
      Serial.println(commandTopic);
      sendStatusMessage();
      
    } else {
      Serial.print("failed, rc=");
      Serial.print(mqttClient.state());
      Serial.println(" try again in 5 seconds");
      delay(5000);
    }
  }
}

// ========== SETUP ==========
void setup() {
  Serial.begin(115200);
  Serial.print("Controller ID: ");
  Serial.println(CONTROLLER_ID);
  
  bootTime = millis();
  
  pinMode(WATER_PIN, INPUT_PULLUP);
  attachInterrupt(digitalPinToInterrupt(WATER_PIN), handleWaterPulse, FALLING);
  
  setupWiFi();
  
  mqttClient.setServer(MQTT_SERVER, MQTT_PORT);
  mqttClient.setCallback(mqttCallback);
  
  statusTicker.attach_ms(STATUS_INTERVAL, []() {
    if (mqttClient.connected()) {
      sendStatusMessage();
    }
  });
  
  Serial.println("Setup complete");
  Serial.println("Waiting for water pulses...");
}

// ========== LOOP ==========
void loop() {
  if (!mqttClient.connected()) {
    reconnectMQTT();
  }
  mqttClient.loop();
  if (pulseTriggered && mqttClient.connected()) {
    sendPulseMessage();
    pulseTriggered = false;
  }
  
  delay(10);
}
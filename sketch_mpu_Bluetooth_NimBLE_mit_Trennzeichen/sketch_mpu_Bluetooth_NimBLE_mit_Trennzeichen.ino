#include <Wire.h>
#include <Adafruit_MPU6050.h>
#include <NimBLEDevice.h>
#include <ArduinoJson.h>

// MPU6050
Adafruit_MPU6050 mpu;
const int sdaPort = 4; // GPIO4 für SDA
const int sclPort = 5; // GPIO5 für SCL

NimBLEServer* pServer = nullptr;
NimBLECharacteristic* pCharacteristic = nullptr;
bool deviceConnected = false;
bool oldDeviceConnected = false;
unsigned long lastDataSent = 0;
const unsigned long SEND_INTERVAL = 100; // Sendeintervall in Millisekunden
const unsigned long RETRY_INTERVAL = 1000; // Reconnect-Intervall in Millisekunden

// UUIDs für den BLE-Service und die Charakteristik
#define SERVICE_UUID        "4fafc201-1fb5-459e-8fcc-c5c9c331914b"
#define CHARACTERISTIC_UUID "beb5483e-36e1-4688-b7f5-ea07361b26a8"

// Callback-Klasse für Server-Ereignisse
class MyServerCallbacks : public NimBLEServerCallbacks {
    void onConnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo) override {
        deviceConnected = true;
        Serial.println("Client verbunden");
    }

    void onDisconnect(NimBLEServer* pServer, NimBLEConnInfo& connInfo, int reason) override {
        deviceConnected = false;
        Serial.printf("Client getrennt. Grund: %d\n", reason);
    }
};

void setup() {
    Serial.begin(115200);
    
    // I2C für den MPU6050 initialisieren
    Wire.begin(sdaPort, sclPort);
    
    // MPU6050 Setup mit Retry
    int mpuRetries = 0;
    while (!mpu.begin() && mpuRetries < 5) {
        Serial.println("Failed to find MPU6050 chip");
        delay(1000);
        mpuRetries++;
    }
    
    if (mpuRetries >= 5) {
        Serial.println("MPU6050 initialization failed!");
        ESP.restart(); // Neustart wenn MPU nicht gefunden
    }
    
    Serial.println("MPU6050 Found!");

    // BLE Setup
    initBLE();
}

void initBLE() {
    // BLE-Gerät initialisieren
    NimBLEDevice::init("ESP32-C3-NimBLE");
    
    // Erhöhe die Sendeleistung für bessere Reichweite
    NimBLEDevice::setPower(ESP_PWR_LVL_P9);
    
    // BLE-Server erstellen
    pServer = NimBLEDevice::createServer();
    pServer->setCallbacks(new MyServerCallbacks());
    
    // Service erstellen
    NimBLEService* pService = pServer->createService(SERVICE_UUID);
    
    // Charakteristik mit angepassten Eigenschaften
    pCharacteristic = pService->createCharacteristic(
        CHARACTERISTIC_UUID,
        NIMBLE_PROPERTY::READ | 
        NIMBLE_PROPERTY::WRITE | 
        NIMBLE_PROPERTY::NOTIFY
    );
    
    // Setze initiale Werte
    JsonDocument doc;
    doc["Ax"] = 0;
    doc["Ay"] = 0;
    doc["Az"] = 0;
    doc["T"] = 0;
    doc["Gx"] = 0;
    doc["Gy"] = 0;
    doc["Gz"] = 0;
    doc["player"] = 1;
    
    char out[512];
    serializeJson(doc, out);
    strcat(out, "\n");
    pCharacteristic->setValue(out);
    
    // Service starten
    pService->start();
    
    // Advertising konfigurieren und starten
    NimBLEAdvertising* pAdvertising = NimBLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->setMinInterval(32); // 20ms Intervall
    pAdvertising->setMaxInterval(64); // 40ms Intervall
    pAdvertising->start();
    
    Serial.println("BLE-Server gestartet");
    Serial.println(NimBLEDevice::getAddress().toString().c_str());
}

void loop() {
    // Behandle Verbindungsstatus
    if (!deviceConnected && oldDeviceConnected) {
        delay(500); // Gib dem BLE-Stack Zeit zum Aufräumen
        pServer->startAdvertising(); // Starte Advertising neu
        Serial.println("Starte Advertising neu...");
        oldDeviceConnected = deviceConnected;
    }
    
    // Wenn neu verbunden
    if (deviceConnected && !oldDeviceConnected) {
        oldDeviceConnected = deviceConnected;
        Serial.println("Verbindung hergestellt.");
    }
    
    // Sende Daten nur wenn verbunden und Intervall erreicht
    if (deviceConnected && (millis() - lastDataSent >= SEND_INTERVAL)) {
        sendSensorData();
        lastDataSent = millis();
    }
    
    // Prüfe regelmäßig die Verbindung
    static unsigned long lastCheck = 0;
    if (millis() - lastCheck >= RETRY_INTERVAL) {
        if (!deviceConnected) {
            Serial.println("Keine Verbindung - Prüfe BLE-Status...");
            if (!NimBLEDevice::getAdvertising()->isAdvertising()) {
                Serial.println("Advertising gestoppt - Neustart...");
                NimBLEDevice::getAdvertising()->start();
            }
        }
        lastCheck = millis();
    }
}

void sendSensorData() {
    try {
        sensors_event_t a, g, temp;
        mpu.getEvent(&a, &g, &temp);
        
        JsonDocument doc;
        doc["Ax"] = a.acceleration.x;
        doc["Ay"] = a.acceleration.y;
        doc["Az"] = a.acceleration.z;
        doc["T"] = temp.temperature;
        doc["Gx"] = g.gyro.x;
        doc["Gy"] = g.gyro.y;
        doc["Gz"] = g.gyro.z;
        doc["player"] = 1;
        
        char out[512];
        serializeJson(doc, out);
        strcat(out, "\n");
        
        if (pCharacteristic->notify((uint8_t*)out, strlen(out))) {
            Serial.print("Daten gesendet: ");
            Serial.println(out);
        } else {
            Serial.println("Fehler beim Senden der Daten!");
        }
    } catch (const std::exception& e) {
        Serial.print("Fehler bei der Datenverarbeitung: ");
        Serial.println(e.what());
    }
}
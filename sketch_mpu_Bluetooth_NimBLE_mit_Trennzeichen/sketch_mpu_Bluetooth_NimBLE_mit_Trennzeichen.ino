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
        Serial.println("Client getrennt");
        pServer->getAdvertising()->start(); // Werbung erneut starten
    }
};

// Callback-Klasse für Charakteristik-Ereignisse
class MyCharacteristicCallbacks : public NimBLECharacteristicCallbacks {
    void onWrite(NimBLECharacteristic* pCharacteristic, NimBLEConnInfo& connInfo) override {
        std::string receivedValue = pCharacteristic->getValue();
        Serial.print("Empfangene Daten: ");
        Serial.println(receivedValue.c_str());

        // Antwort senden (falls gewünscht)
        pCharacteristic->setValue("Daten empfangen: " + receivedValue);
        pCharacteristic->notify();
    }

    void onRead(NimBLECharacteristic* pCharacteristic, NimBLEConnInfo& connInfo) override {
        Serial.println("Charakteristik wurde gelesen.");
    }
};

void setup() {
    Serial.begin(115200);
    
    // I2C für den MPU6050 initialisieren
    Wire.begin(sdaPort, sclPort);
    while (!mpu.begin()) {
        Serial.println("Failed to find MPU6050 chip");
        delay(1000);
    }
    Serial.println("MPU6050 Found!");

    // BLE-Gerät initialisieren
    NimBLEDevice::init("ESP32-C3-NimBLE");

    // BLE-Server erstellen
    pServer = NimBLEDevice::createServer();
    pServer->setCallbacks(new MyServerCallbacks());
    // Warte einen Moment, damit die Initialisierung abgeschlossen wird
    delay(1000);
    // Hole die MAC-Adresse und gebe sie aus
    Serial.println("ESP32-C3 BLE MAC-Adresse:");
    Serial.println(NimBLEDevice::getAddress().toString().c_str());

    // Service erstellen
    NimBLEService* pService = pServer->createService(SERVICE_UUID);

    // Charakteristik hinzufügen mit verschlüsselten Lese-/Schreibrechten
    pCharacteristic = pService->createCharacteristic(
        CHARACTERISTIC_UUID,
        NIMBLE_PROPERTY::READ | NIMBLE_PROPERTY::WRITE | NIMBLE_PROPERTY::NOTIFY |
        NIMBLE_PROPERTY::READ_ENC | NIMBLE_PROPERTY::WRITE_ENC // Verschlüsselung erforderlich
    );

    // Formatierung der Charakteristik mit NimBLE2904
    NimBLE2904* pDesc = (NimBLE2904*) pCharacteristic->create2904();
    pDesc->setFormat(NimBLE2904::FORMAT_UTF8);

    // Callbacks für die Charakteristik setzen
    pCharacteristic->setCallbacks(new MyCharacteristicCallbacks());

    // Initialen Wert für die Charakteristik setzen
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
    // Füge ein Trennzeichen hinzu
    strcat(out, "\n");
    pCharacteristic->setValue(out);

    // Service starten
    pService->start();

    // Werbung starten
    NimBLEAdvertising* pAdvertising = NimBLEDevice::getAdvertising();
    pAdvertising->addServiceUUID(SERVICE_UUID);
    pAdvertising->start();

    Serial.println("BLE-Server gestartet");
}
int iCount=0;
void loop() {
    iCount++;
    if (deviceConnected) {
        JsonDocument doc;
        sensors_event_t a, g, temp;
        mpu.getEvent(&a, &g, &temp);

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
        // Füge ein Trennzeichen hinzu
        strcat(out, "\n");

        // Daten über BLE senden
        pCharacteristic->setValue((uint8_t*)out, strlen(out));
        pCharacteristic->notify();
        Serial.println("Daten gesendet: " + String(out));
    } else {
        if (iCount >= 10) {
            Serial.println("Serielle Schnittstelle not connected!");
            iCount = 0;
        }
    }
    delay(100);
}
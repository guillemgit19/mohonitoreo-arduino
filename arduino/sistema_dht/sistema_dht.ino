#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <DHT.h>
#include <SoftwareSerial.h>

#define DHTTYPE DHT11

// Bluetooth HC-05
SoftwareSerial BT(2, 3); // RX, TX

// Sensores DHT11
DHT dhtTemp(8, DHTTYPE);
DHT dhtHum(10, DHTTYPE);

// LCD I2C
LiquidCrystal_I2C lcd(0x27, 16, 2);

void setup() {
  Serial.begin(9600);
  BT.begin(9600);

  dhtTemp.begin();
  dhtHum.begin();

  lcd.init();
  lcd.backlight();

  lcd.setCursor(0, 0);
  lcd.print("Iniciando...");
  
  Serial.println("Sistema iniciado");
  BT.println("Sistema iniciado");

  delay(2000);
  lcd.clear();
}

void loop() {
  float temperatura = dhtTemp.readTemperature();
  float humedad = dhtHum.readHumidity();

  if (isnan(temperatura) || isnan(humedad)) {
    lcd.clear();
    lcd.setCursor(0, 0);
    lcd.print("Error sensores");

    Serial.println("{\"error\":\"sensores\"}");
    BT.println("{\"error\":\"sensores\"}");

    delay(2000);
    return;
  }

  // Mostrar en LCD
  lcd.clear();

  lcd.setCursor(0, 0);
  lcd.print("P8 T:");
  lcd.print(temperatura, 1);
  lcd.print((char)223);
  lcd.print("C");

  lcd.setCursor(0, 1);
  lcd.print("P10 H:");
  lcd.print(humedad, 1);
  lcd.print("%");

  // Crear JSON
  String json = "{\"temperatura\":";
  json += String(temperatura, 1);
  json += ",\"humedad\":";
  json += String(humedad, 1);
  json += "}";

  // Enviar por USB
  Serial.println(json);

  // Enviar por Bluetooth
  BT.println(json);

  delay(2000);
}
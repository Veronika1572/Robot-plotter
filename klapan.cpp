/*
 * Простое управление клапаном Arii TRG через MOS-модуль MH.
 * Кнопка нажата  -> клапан открыт (GPIO 5 = HIGH)
 * Кнопка отпущена -> клапан закрыт (GPIO 5 = LOW)
 *
 * Подключение:
 *   Кнопка:      один вывод -> GPIO 4, второй -> GND
 *   MOS-модуль:  вход TRIG/PWM/IN -> GPIO 5
 *   Питание MOS-модуля: 12V, GND общий с ESP32
 *   Диод 1N4007 параллельно катушке клапана (катод к +12V)
 */

const int BUTTON_PIN = 4;
const int MOSFET_PIN = 5;

void setup() {
  Serial.begin(115200);
  pinMode(BUTTON_PIN, INPUT_PULLUP);  // подтяжка к 3.3В внутри чипа
  pinMode(MOSFET_PIN, OUTPUT);
  digitalWrite(MOSFET_PIN, LOW);      // на старте клапан закрыт
}

void loop() {
  // digitalRead вернёт LOW, когда кнопка нажата (замыкает на GND)
  if (digitalRead(BUTTON_PIN) == LOW) {
    digitalWrite(MOSFET_PIN, HIGH);   // кнопка нажата  -> открыть
  } else {
    digitalWrite(MOSFET_PIN, LOW);    // кнопка отпущена -> закрыть
  }
}
#define ZMPT_PIN 34

const int SAMPLES = 4000;

// Your calibration value
float calibration = 367.0;

void setup() {
  Serial.begin(115200);

  analogReadResolution(12);
  analogSetPinAttenuation(ZMPT_PIN, ADC_11db);

  delay(1000);

  Serial.println("ZMPT101B AC VOLTAGE METER");
}

void loop() {

  double sum = 0;
  double sumSquares = 0;

  for (int i = 0; i < SAMPLES; i++) {

    int adcValue = analogRead(ZMPT_PIN);

    sum += adcValue;
    sumSquares += (double)adcValue * adcValue;

    delayMicroseconds(200);
  }

  // DC offset
  double average = sum / SAMPLES;

  // AC RMS in ADC counts
  double variance =
      (sumSquares / SAMPLES) -
      (average * average);

  if (variance < 0)
    variance = 0;

  double rmsADC = sqrt(variance);

  // Convert ADC counts to voltage at ZMPT output
  double sensorRMS =
      (rmsADC / 4095.0) * 3.3;

  // Convert sensor voltage to input AC voltage
  double acVoltage =
      sensorRMS * calibration;

  Serial.print("ADC RMS = ");
  Serial.print(rmsADC, 2);

  Serial.print("   Sensor RMS = ");
  Serial.print(sensorRMS, 4);

  Serial.print(" V   AC Voltage = ");
  Serial.print(acVoltage, 2);

  Serial.println(" V RMS");

  delay(1000);
}
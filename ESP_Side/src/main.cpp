#include <LiquidCrystal.h>
#include "ArduinoJson.h"

LiquidCrystal lcd(14,27,26,25,33,32);

class Transmitter{
  enum class LastBitState {None = 3, Zero = 0, One = 1};
  LastBitState last_bit = LastBitState::None;
  
  void sendBit(bool bit, int duration){
    if (bit != static_cast<int>(last_bit)){
      tone(SquareWaveOut, bit ? Mark : Space);
    }
    delay(duration);
    last_bit = static_cast<LastBitState>(bit);
  }
  
  void sendBit(bool bit){
    sendBit(bit, BitDuration);
  }

  void sendStop(int times){
    sendBit(1, BitDuration * StopDuration * times);
  }
  public:
  Transmitter(){};
  static const int SquareWaveOut = 15;
  static const int Transmit = 4;

  //default values
  int Mark = 2125;
  int Shift = 170;
  int Space = Mark + Shift;
  double Baud = 45.45;
  int BitDuration = round(1000.0 / Baud);
  float StopDuration = 1.5;
  int PreStops = 40;
  
  void begin(){
    digitalWrite(Transmit, HIGH);
    pinMode(Transmit, OUTPUT);
    pinMode(SquareWaveOut, OUTPUT);
  }
  void start(){
    digitalWrite(Transmit, LOW);
    sendStop(PreStops);
  }
  void send_char(int code){
    sendBit(0);
    for (int i = 4; i >= 0; i--){
      sendBit(code & (1 << i));
    }
    sendStop(1);
  }
  void stop(){
    noTone(SquareWaveOut);
    digitalWrite(SquareWaveOut, LOW);
    digitalWrite(Transmit, HIGH);
    last_bit = LastBitState::None;
  }
};
Transmitter trans;

void deserializeJSON(String c){
  
  JsonDocument doc;
  deserializeJson(doc, c);

  DeserializationError err = deserializeJson(doc, c);

  if (err) {
    lcd.print("JSON ERR");
    return;
  }
  
  float stopbits = doc["stop_bits"];
  double baud = doc["baud"];
  long mark = doc["mark"];
  long shift = doc["shift"];
  long prestops = doc["pre_msg_stops"];

  trans.Mark = mark;
  trans.Shift = shift;
  trans.Space = trans.Mark + trans.Shift;
  trans.Baud = baud;
  trans.BitDuration = round(1000.0 / trans.Baud);
  trans.StopDuration = stopbits;
  trans.PreStops = prestops;
  
  JsonArray msgarr = doc["message"];

  trans.start();
  
  for(int i = 0; i < msgarr.size(); i++){
    //lcd.print(msgarr[i].as<int>());
    trans.send_char(msgarr[i].as<int>());
  }
  trans.stop();
  
}

String c;

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(1000);
  lcd.begin(16,2); 
  trans.begin();
}

void loop() {
  while(!Serial.available());
  c = Serial.readString();
  lcd.print(c);
  deserializeJSON(c);
  Serial.println("Received: " + c);
  Serial.flush();
  
  
}

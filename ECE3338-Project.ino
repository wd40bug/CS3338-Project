#include <LiquidCrystal.h>

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

  void sendStop(){
    sendStop(1);
  }

  void sendStop(int times){
    sendBit(1, BitDuration * StopDuration * times);
  }
  public:
  Transmitter(){};
  static const int SquareWaveOut = 15;
  static const int Transmit = 4;
  static const int Mark = 2125;
  static const int Shift = 170;
  static const int Space = Mark + Shift;
  static constexpr double Baud = 45.45;
  static const int BitDuration = round(1000.0 / Baud);
  static constexpr float StopDuration = 1.5;
  void begin(){
    digitalWrite(Transmit, HIGH);
    pinMode(Transmit, OUTPUT);
    pinMode(SquareWaveOut, OUTPUT);
  }
  void start(){
    digitalWrite(Transmit, LOW);
    sendStop(40);
  }
  void send_char(int code){
    sendBit(0);
    for (int i = 4; i >= 0; i--){
      sendBit(code & (1 << i));
    }
    sendStop();
  }
  void stop(){
    noTone(SquareWaveOut);
    digitalWrite(SquareWaveOut, LOW);
    digitalWrite(Transmit, HIGH);
    last_bit = LastBitState::None;
  }
};

Transmitter trans;

LiquidCrystal lcd(14,27,26,25,33,32);

int c;

void setup() {
  Serial.begin(115200);

  lcd.begin(16,2);
}

void loop() {
  while(!Serial.available());
  c = Serial.read();
  //send_char(c);
  lcd.print(c);
  
}

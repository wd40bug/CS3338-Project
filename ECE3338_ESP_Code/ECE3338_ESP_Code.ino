#include "ArduinoJson.h"

unsigned long __last_beat_time = 0;
const unsigned long HEARTBEAT_INTERVAL = 1000; // 1 seconds

void pumpHeartbeat() {
  unsigned long current_time = millis();
  if (current_time - __last_beat_time >= HEARTBEAT_INTERVAL) {
    Serial.println("BEAT:");
    __last_beat_time = current_time;
  }
}

class Transmitter{
  enum class LastBitState {None = 3, Zero = 0, One = 1};
  LastBitState last_bit = LastBitState::None;
  
  void sendBit(bool bit, int duration){
    pumpHeartbeat();
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
  static const int SquareWaveOut = 4;
  static const int Transmit = 15;

  //default values
  int Mark = 2125;
  int Shift = 170;
  int Space = Mark + Shift;
  double Baud = 45.45;
  int BitDuration = round(1000.0 / Baud);
  float StopDuration = 1.5;
  int PreStops = 40;
  
  void begin(){
    pinMode(Transmit, OUTPUT);
    digitalWrite(Transmit, HIGH);
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

String c;

void setup() {
  Serial.begin(115200);
  Serial.setTimeout(50);
  trans.begin();
  Serial.println("DEBUG: Awake");
}

void loop() {
  pumpHeartbeat();
  // Check if there is data waiting in the serial buffer
  if (Serial.available()) {

    JsonDocument doc;
    
    // Pass the Serial stream directly to the deserializer!
    // It will block here (up to the Serial timeout) until it finds a complete JSON object.
    DeserializationError err = deserializeJson(doc, Serial);

    if (err) {
      Serial.println("ERROR: " + String(err.c_str()));
      // Read out and discard any garbage left in the buffer to prevent a loop lock
      while(Serial.available()) Serial.read(); 
      return;
    }

    String errorMsg = "";

    // Check Root Elements
    if (!doc["options"].is<JsonObject>()) {
      errorMsg = "Missing or invalid 'options' (must be an object).";
    } 
    else if (!doc["message"].is<JsonArray>()) {
      errorMsg = "Missing or invalid 'message' (must be an array).";
    } 
    else {
      // Check Nested Options
      JsonObject opts = doc["options"];
      
      // Note: .is<float>() safely matches both floats and doubles.
      // .is<long>() safely matches both ints and longs.
      if (!opts["stop_bits"].is<float>()) {
        errorMsg = "'options.stop_bits' missing or not a number.";
      } 
      else if (!opts["baud"].is<float>()) { 
        errorMsg = "'options.baud' missing or not a number.";
      } 
      else if (!opts["mark"].is<long>()) {
        errorMsg = "'options.mark' missing or not an integer.";
      } 
      else if (!opts["shift"].is<long>()) {
        errorMsg = "'options.shift' missing or not an integer.";
      } 
      else if (!opts["pre_msg_stops"].is<long>()) {
        errorMsg = "'options.pre_msg_stops' missing or not an integer.";
      }
    }

    // Abort if any check failed
    if (errorMsg != "") {
      Serial.println("ERROR: " + errorMsg);
      // Read out and discard any garbage left in the buffer to prevent a loop lock
      while(Serial.available()) Serial.read(); 
      return; 
    }

    // Pass the populated document directly to handling logic
    handlePayload(doc);
    Serial.println("DONE: Sent Message");    
  }
}

void handlePayload(JsonDocument& doc) {
  JsonObject options = doc["options"];
  float stopbits = options["stop_bits"];
  double baud = options["baud"];
  long mark = options["mark"];
  long shift = options["shift"];
  long prestops = options["pre_msg_stops"];

  trans.Mark = mark;
  trans.Shift = shift;
  trans.Space = trans.Mark + trans.Shift;
  
  trans.Baud = (baud > 0) ? baud : 45.45; 
  trans.BitDuration = round(1000.0 / trans.Baud);
  
  trans.StopDuration = stopbits;
  trans.PreStops = prestops;
  
  JsonArray msgarr = doc["message"];

  Serial.println("DEBUG: Starting transmission");
  Serial.println("DEBUG: Msg has len " + String(msgarr.size()));
  trans.start();
  for(int i = 0; i < msgarr.size(); i++){
    pumpHeartbeat();
    int code = msgarr[i].as<int>();
    Serial.println("TRACE: Sending code" + String(code));
    trans.send_char(code);
  }
  trans.stop();
}

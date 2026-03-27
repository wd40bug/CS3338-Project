#include <WiFi.h>
#include <LiquidCrystal.h>
#include <CRC16.h>
#include "Baudot.h"



void send_data(int character){
  Serial.print(character);
  Serial.print(" ");
}

// 192.168.4.1 IP Address
// Network credentials
const char* ssid = "ESP-32 Network";
const char* pass = "RTTYROX";

const char* CallSign = "KJ5OEH";

const int NumBitsPerChar = 5;
const int Mark = 2125;
const int Shift = 170;
const double Baud = 45.45;
const int BitDuration = round(1000.0 / Baud);

WiFiServer server(80);

String header;

const int RSpin = 14;
const int Epin = 27;
const int D4pin = 26;
const int D5pin = 25;
const int D6pin = 33;
const int D7pin = 32;

LiquidCrystal lcd(RSpin,Epin,D4pin,D5pin,D6pin,D7pin);
BAUDOT Baudot;

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
    sendStop(20);
  }
  void send_char(int code){
    sendBit(0);
    for (int i = NumBitsPerChar - 1; i >= 0; i--){
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

void setup() {
  Serial.begin(115200);
  
  trans.begin();
  
  WiFi.softAP(ssid, pass);

  IPAddress IP = WiFi.softAPIP();
  Serial.print("IP address: ");
  Serial.print(IP);

  server.begin();

  lcd.begin(16, 2);
}

String sent_text = "";

void loop() {
  WiFiClient client = server.accept();
  
  if(client){
    int contentlength = 0;
    Serial.println("New Client.");
    String currentline = "";
    while(client.connected()){
      if(client.available()){
        char c = client.read();
        Serial.write(c);
        header += c;
        
        if(c== '\n') {
          if(currentline.startsWith("Content-Length: ")){
            contentlength = currentline.substring(16).toInt();
          }
          if(currentline.length() == 0){
            String body = "";
            int remaining = contentlength;
            while (remaining > 0) {
              if (client.available()) {
                char ch = (char)client.read();
                if(ch == '+' || ch == '*'){
                  ch = ' ';
                }
                
                if(ch == '%'){
                  remaining--;
                  char h1  = (char)client.read();
                  remaining--;
                  char h2  = (char)client.read();
                  remaining--;
                  char hexstr[3] = {h1, h2, '\0'};
                  

                  long int hexnum =  strtol(hexstr, NULL, 16);

                  char newch = (char)hexnum;

                  if((newch == ',') || (newch == '.') || (newch == ')') || (newch == '&') || (newch == ':') || (newch == ';') || (newch == '"') || (newch == '$') || (newch == '?') || (newch == '!') || (newch == '/') || (newch == '-') || (newch == '\'') || (newch == '(') || (newch == '#')) {
                    body += newch;
                  }
                  else {
                    body += " ";
                  }
                  
                }
                else{
                  body += ch;
                  remaining--;
                }
              }
            }
            
            if(body.substring(10) != ""){
              String msg = "";
              String content = body.substring(10);
              content.toUpperCase();

              CRC16 crc;
              crc.restart();
              
              if(content.length() < 16){
                  msg += "0";
                }
                
              if(content.length() < 256) {
                msg += String(content.length(), HEX);
                msg += content;
              }

              msg.toUpperCase();

              // State 1 - letter mode, State 0 - figure mode
              Baudot.setMode(0);
              
              int arrnum = 0;

              for(int i = 0; i < msg.length(); i++){
                if(Baudot.isLetter(msg[i])){
                  if(Baudot.getMode() == 0) {
                    arrnum++;
                    Baudot.setMode(1);
                  }
                  arrnum++;
                }
                else {
                  if(Baudot.getMode() == 1) {
                    arrnum++;
                    Baudot.setMode(0);
                  }
                  arrnum++;
                }
              }
              
              int EncodedMsg[arrnum + 17] = {0};
              
              Baudot.setMode(0);
              
              int arrpos = 0;
               
              for(int i = 0; i < msg.length(); i++){
                if(Baudot.isLetter(msg[i]) && Baudot.getMode() != 1){
                  Baudot.setMode(1);
                  EncodedMsg[arrpos] = BAUDOT_LETTERS;
                  arrpos++;
                  EncodedMsg[arrpos] = Baudot.Encode(msg[i]);
                 
                  arrpos++;
                }
                else if(!Baudot.isLetter(msg[i]) && Baudot.getMode() != 0) {
                  Baudot.setMode(0);
                  EncodedMsg[arrpos] = BAUDOT_FIGURES;
                  arrpos++;
                  EncodedMsg[arrpos] = Baudot.Encode(msg[i]);
                  if(msg[i] == '!') EncodedMsg[arrpos] = 13;
                  if(msg[i] == '$') EncodedMsg[arrpos] = 9;
                  if(msg[i] == '"') EncodedMsg[arrpos] = 17;
                  if(msg[i] == ';') EncodedMsg[arrpos] = 30;
                  if(msg[i] == '#') EncodedMsg[arrpos] = 20;
                  if(msg[i] == '&') EncodedMsg[arrpos] = 26;
                  arrpos++;
                }
                else {
                  EncodedMsg[arrpos] = Baudot.Encode(msg[i]);
                  if(msg[i] == '!') EncodedMsg[arrpos] = 13;
                  if(msg[i] == '$') EncodedMsg[arrpos] = 9;
                  if(msg[i] == '"') EncodedMsg[arrpos] = 17;
                  if(msg[i] == ';') EncodedMsg[arrpos] = 30;
                  if(msg[i] == '#') EncodedMsg[arrpos] = 20;
                  if(msg[i] == '&') EncodedMsg[arrpos] = 26;
                  arrpos++;
                }
              }

              int sumvalues = 0;
              for(int i = 0; i < arrnum; i++){
                sumvalues += EncodedMsg[i];
              }

              crc.add(sumvalues);
              
              String checkstr = String(crc.calc(), HEX);
              checkstr.toUpperCase();
              
              if(checkstr.length() == 2){
                checkstr = "00" + checkstr;
              }
              else if(checkstr.length() == 3){
                checkstr = "0" + checkstr;
              }
              else if(checkstr.length() == 1){
                checkstr = "000" + checkstr;
              }

              checkstr += CallSign;
              
              for(int i =  0; i < 10; i++){
                if(Baudot.isLetter(checkstr[i]) && Baudot.getMode() != 1){
                    Baudot.setMode(1);
                    EncodedMsg[arrpos] = BAUDOT_LETTERS;
                    arrpos++;
                    EncodedMsg[arrpos] = Baudot.Encode(checkstr[i]);
                    arrpos++;
                  }
                  else if(!Baudot.isLetter(checkstr[i]) && Baudot.getMode() != 0){
                    Baudot.setMode(0);
                    EncodedMsg[arrpos] = BAUDOT_FIGURES;
                    arrpos++;
                    EncodedMsg[arrpos] = Baudot.Encode(checkstr[i]);
                    arrpos++;
                  }
                  else{
                    EncodedMsg[arrpos] = Baudot.Encode(checkstr[i]);
                    arrpos++;
                  }
          
              }

              msg += checkstr;

              sent_text = sent_text + "Sending: " + content + "<br>Full Message: " + msg + "<br>";

              trans.start();
              for(int i = 0; i < arrnum + 17; i++){
                //send_data(EncodedMsg[i]);
                trans.send_char(EncodedMsg[i]);
              }
              trans.stop();
              lcd.clear();
              lcd.setCursor(0,0);
              lcd.print(msg);
              //lcd.setCursor(0,1);
              //lcd.print(checkstr);
              
              
            }
            
            client.println("HTTP/1.1 200 OK");
            client.println("Content-type:text/html");
            client.println("Connection: close");
            client.println();
          
            client.println("<!DOCTYPE html>");
            client.println("<html><head>");
            client.println("<title>RTTY Hub</title>");
            client.println("<style>input {width: 100%;padding: 0px;border: 1px solid black;margin-bottom: 2px;}");
            client.println("div {display: flex;}");
            client.println("p {margin: 0px;padding: 0px;border: 1px solid black;overflow: auto}");
            client.println("#sent {width: 100%;height: 275px;}");
            client.println("#received {width: 35%;height: 410px;}");
            client.println("#corrected {width: 35%;height: 410px;}");
            client.println("#meta {width: 30%;height: 410px;}");
            client.println("</style></head><body> ");
            client.println("<div><p id = sent>" + sent_text + "</p></div>");
            client.println("<form method = \"post\"><input name = \"send_data\" type = \"text\" placeholder=\"Enter text to send\"><input type = \"submit\"></form>");
            client.println("<div><p id = received>Received Text</p>");
            client.println("<p id = corrected>Corrected Text</p>");
            client.println("<p id = meta>Meta Data</p></div></body></html>");
            client.println();
            break;
          }
          else {
            currentline = "";
          }
        }
        else if(c != '\r'){
          currentline += c;
        }
      }
    }
    header = "";
    client.stop();
    Serial.println("");
  }
}

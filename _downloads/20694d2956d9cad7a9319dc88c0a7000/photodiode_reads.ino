const long BAUD_RATE = 9600;
int photodiode_state = 0;
const int photodiode = 14;


void setup() {
  // put your setup code here, to run once:
  Serial.begin(BAUD_RATE);
  pinMode(photodiode, INPUT);
}

void write_photodiode() {
  photodiode_state = analogRead(photodiode);
  //write16i(photodiode_state);
}

void loop() {
  // put your main code here, to run repeatedly:
  write_photodiode();
  Serial.println(photodiode_state);
  delay(1);
  //write16i(photodiode_state);
}
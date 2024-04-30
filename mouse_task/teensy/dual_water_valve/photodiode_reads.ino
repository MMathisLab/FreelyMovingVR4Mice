
// optimize interrupts and load encode library
#define ENCODER_OPTIMIZE_INTERRUPTS

// constants
const long BAUD_RATE = 115200;
const int SAMPLE_RATE = 500;

// pins
const int photodiode = 14;
// Other cst variables


// public variables to control I/O devices
bool task_on = false;
int last_print = 0;
bool water_on = false;
int photodiode_read = 0;
bool braking = false;


// setup
void setup() {

  Serial.begin(BAUD_RATE);
  pinMode(photodiode, INPUT);

}

// Read & Write functions
int read16i() {
  union u_tag { 
    byte b[2];
    int val;
  } par;
  
  for (int i=0; i<2; i++){
    if ((Serial.available() > 0))
      par.b[i] = Serial.read();
    else
      par.b[i] = 0;
  }
  return par.val;
}

void write16i(int x){
  Serial.write(x);
  Serial.write(x >> 8);
}

void send_line(){
  write16i(-32767);
  write16i(32767);
  Serial.flush();
}

// read and write wheel velocities


void loop() {

  int curr_time = millis();

  // read commands
  while(Serial.available() > 0){
    unsigned int cmd = Serial.read();
    photodiode_read = AnalogRead(photodiode);

    write16i(photodiode);

    if (task_on){
      if(cmd == 'Z'){
        task_on = false;
    }else{
      if (cmd == 'A'){
        task_on = true;
      }else if(cmd == 'Y'){
        _reboot_Teensyduino_();
      }
    }
  }

  if(task_on){
    if(curr_time >= last_print + 1000/SAMPLE_RATE){
      last_print = curr_time;
   
    }
  }

}

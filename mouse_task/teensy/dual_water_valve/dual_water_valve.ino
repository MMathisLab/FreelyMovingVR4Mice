/***
 * Template sketch for wheels rig
 * 
 * Hardware Inputs:
 * left wheel velocity - 23, 21, 19
 * right wheel velocity - 17, 15, 13
 * 
 * Hardware Outputs:
 * water valve - 0
 * speaker - 1
 * 
 * Commands:
 * A = Start
 * Z = Stop
 * Y = Reboot
 * W = turn on water, parameters = duration
 * T = turn on tone, parameters = frequency, duration
 * 
 ***/

// optimize interrupts and load encode library
#define ENCODER_OPTIMIZE_INTERRUPTS

// constants
const long BAUD_RATE = 115200;
const int SAMPLE_RATE = 500;

// pins
const int servoPin = 9;

const int left_a = 23;
const int left_b = 21;
const int left_index = 19;
const int right_a = 17;
const int right_b = 15;
const int right_index = 13;
const int R_water = 2;
const int L_water = 0;
const int speaker = 1;
// Other cst variables


// public variables to control I/O devices
bool task_on = false;
int last_print = 0;
bool water_on = false;
int water_start = 0, water_dur = 0;
int tone_freq = 0, tone_dur = 0;
int last_left = 0, last_right = 0;
int pos = 0;
bool braking = false;


// setup
void setup() {

  Serial.begin(BAUD_RATE);

  pinMode(R_water, OUTPUT);
  pinMode(L_water, OUTPUT);
  pinMode(speaker, OUTPUT);

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
    if (task_on){
      if(cmd == 'Z'){
        task_on = false;
      }else if(cmd == 'L'){
        water_start = curr_time;
        water_dur = read16i();
        if (water_dur >= 0){
          water_on = true;
        }
        digitalWrite(L_water, HIGH);
      }else if(cmd == 'R'){
        water_start = curr_time;
        water_dur = read16i();
        if (water_dur >= 0){
          water_on = true;
        }
        digitalWrite(R_water, HIGH);
      }else if(cmd == 'T'){
        tone_freq = read16i();
        tone_dur = read16i();
        if (tone_dur >= 0){
          tone(speaker, tone_freq, tone_dur);
        }else{
          tone(speaker, tone_freq);
        }
      }else if((cmd == 'S') & (!braking)){
        
        //for(pos = servoLoAngle; pos <= servoHiAngle; pos += 1) // goes from 0 degrees to 180 degrees 
        //{                                  // in steps of 1 degree 
        //  Servo1.write(pos);              // tell servo to go to position in variable 'pos' 
        //  delay(40);                       // waits 15ms for the servo to reach the position 
        //}
      
        braking = true;
      }else if((cmd =='B') & (braking)){

        //for(pos = servoHiAngle; pos >= servoLoAngle; pos -= 1) // goes from 0 degrees to 180 degrees 
        //{                                  // in steps of 1 degree 
        //  Servo1.write(pos);              // tell servo to go to position in variable 'pos' 
        //  delay(40);                       // waits 15ms for the servo to reach the position 
        //}
       
        braking = false;
      }
    }else{
      if (cmd == 'A'){
        task_on = true;
      }else if(cmd == 'Y'){
        _reboot_Teensyduino_();
      }
    }
  }

  // check signals
  if(water_on){
    if(curr_time > water_start+water_dur){
      digitalWrite(R_water, LOW);
      digitalWrite(L_water, LOW);
      water_on = false;
    }
  }

  if(task_on){
    if(curr_time >= last_print + 1000/SAMPLE_RATE){
      last_print = curr_time;
   
    }
  }

}

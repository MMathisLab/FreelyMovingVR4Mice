/*
  Optogenetics and Neural Engineering Core ONE Core
  University of Colorado, School of Medicine
  31.Oct.2021
  See bit.ly/onecore for more information, including a more detailed write up.
  arduino_barcodes.ino

  Continuously ouputs highly randomized 32-bit digital barcodes; for synchronizing data streams
    Use arduino_barcodes_triggered.ino for option to trigger barcode output from TTL or Button Press

  *Most* users need not change anything outside of USER INPUT.

  Written for DFRobot Beetle Board - Compatible with Arduino Leonardo

  Side: Be sure to well tie together/understand your frequency of measurements (DAQ) and how that
  relates to the frequency of the barcodes. Nyst equation says that we should know the fastest
  oscillation of our signal. We can then FULLY measure that signal by sampling at just over two
  times as fast. That means, if we plan to measure at 2000Hz, we can reliably FULLY measure a
  1000Hz signal. This corresponds to a 1 msec period. Our chosen fastest barcode of 10 msec is
  well above this.

  Based heavily on the ideas of a barcode generation ino from Open Ephys at https://open-ephys.org/
*/

/////////////////USER INPUT///////////////////////////////////
const int TOTAL_TIME = 5000;     // Total time between barcode initiation (includes initialization pulses) in milliseconds. The length of time between one barcode and the next
////////////END USER INPUT///////////////////////////////////

const int LED_INTER_PIN = 13; // LED indicator for interbarcode delay
const int RANDOM_PIN = A0;   // we will use analog pin 0 on beetle to read an analog signal to read random noise. Pin should not be connected to anything.
const int OUTPUT_PIN = 12;   // Digital pin 9 on beetle will Output the Barcode TTL
const int BARCODE_BITS = 32;   // Beetle (and uno) use 32 bits
byte PREVIOUS_BUTTON_STATE = HIGH;         // What state was the button last time. Initiate as HIGH


const int BARCODE_TIME = 30;  // time for each bit of the barcode to be on/off in milliseconds

const int INITIALIZATION_TIME = 10;  // We warp the beginning and ending of the barcode with 'some signal', well distinct from a barcode pulse, in milliseconds

const int INITIALIZATION_PULSE_TIME = 3 * INITIALIZATION_TIME;  // We wrap the barcode with a train of off/on/off initialization, then we have the barcode,
// and again off/on/off initialization. Why? I donno, it kind of makes sense to me

const int TOTAL_BARCODE_TIME = 2 * INITIALIZATION_PULSE_TIME + BARCODE_TIME * BARCODE_BITS; // the total time for the initialization train and barcode signal

const int WAIT_TIME = TOTAL_TIME - TOTAL_BARCODE_TIME; // the total time we wait until starting the next wrapped barcode

int barcode;   // initialize a variable to hold our barcode

void setup() {
  pinMode(OUTPUT_PIN, OUTPUT); // initialize digital pin
  pinMode(LED_INTER_PIN, OUTPUT); // initialize digital pin

  randomSeed(analogRead(RANDOM_PIN)); // sets up random() function to be, like, totally random, dude (it reads an analog pin connected to nothing and creates a
  // computer-ized 'random' number based on that

  barcode = random(0, pow(2, BARCODE_BITS)); // generates a random number between 0 and 2^32 (4294967296)
  // (example: if barcode = 4, in binary that would be 0000000000000100)
}

void loop() {
  // start barcode with a distinct pulse to signal the start. low, high, low
  digitalWrite(OUTPUT_PIN, LOW); delay(INITIALIZATION_TIME);
  digitalWrite(OUTPUT_PIN, HIGH); delay(INITIALIZATION_TIME);
  digitalWrite(OUTPUT_PIN, LOW); delay(INITIALIZATION_TIME);

  barcode += 1;
  // increment barcode on each cycle. Our initial value of barcode = 4
  // (in binary 0000000000000100) becomes barcode = 5 (or 0000000000000101)

  // BARCODE SECTION
  for (int i = 0; i < BARCODE_BITS; i++) // for between 0-31 (we will read all 32 bits)
  {
    int barcodedigit = bitRead(barcode >> i, 0);
    // bitRead(x, n) Reads the bit of number x at bit n. The '>>' is a
    // rightshift bitwise operator. For i=0 (0000000000000101) outputs 1. For
    // i=1 (0000000000000010) outputs 0.

    if (barcodedigit == 1)    // if the digit is 1
    {
      digitalWrite(OUTPUT_PIN, HIGH);  // set the output pin to high
    }
    else
    {
      digitalWrite(OUTPUT_PIN, LOW);   // else set it to low
    }
    delay(BARCODE_TIME);   // delay 30 ms
  }

  // end barcode with a distinct pulse to signal the beginning. low, high, low
  digitalWrite(OUTPUT_PIN, LOW); delay(INITIALIZATION_TIME);
  digitalWrite(OUTPUT_PIN, HIGH); delay(INITIALIZATION_TIME);
  digitalWrite(OUTPUT_PIN, LOW); delay(INITIALIZATION_TIME);

  // Then be sure to wait long enough before starting the next barcode
  digitalWrite(LED_INTER_PIN, HIGH);
  delay(WAIT_TIME);
  digitalWrite(LED_INTER_PIN, LOW);
}

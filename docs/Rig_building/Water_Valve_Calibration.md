# Water Valve Calibration

## Preparation

1. Label and weigh two weigh boats for the left and right water valves respectively.
2. Ensure that the syringes on both sides are suspended at the same height and the lengths of the water tubes are equal. Make sure the water tubes are not compressed (e.g., by the arena lid).

## Removing Air Bubbles

1. Perform flushing procedure:
   1. Select the manual water task in `vr4mice`.
   2. Set the water valve opening time to 5000 ms.
   3. Flush the tubes repeatedly to remove air bubbles.
2. Apply pressure with syringe plunger for persistent bubbles:
   - If bubbles persist, apply pressure with the syringe plunger while the water valve is open.
3. Refill syringe:
   - After removing the air bubbles, refill the syringe to the 20 ml mark.

## Measurement

To accurately measure the amount of water dispensed by the valve, it is required to take measurements of the water dispensed at different valve opening times. For instance, we will do so for the following opening times: `100 ms`, `200 ms`, `300 ms`, `400 ms`, `500 ms`, `600 ms`, `700 ms`, `800 ms`, `900 ms`, `1000 ms`.

Perform the following set of steps <u>**3 times**</u> steps <u>**for each opening time**</u>:

1. In `vr4mice`, select the manual water task and set the water valve opening times to the desired value (i.e. one of the values listed above).
2. Collect dispensed water:
   1. Place the weigh boat under the lick port.
   2. Open the valve and dispense the water into the weigh boat.
3. Weigh the collected water:
   1. Carefully remove the weigh boat after water has been dispensed. Collect any clinging water droplets with the edge of the weigh boat.
   2. Weigh the boat to measure the water dispensed.

```{important}
Perform 3 measurements for each opening time to ensure consistency. Performing steps 1-3 amounts to making a single measurement.
```

## Get reward size

1. Subtract the weight of the weigh boat from the recorded measurements, and enter the results into the code.
2. Use curve fitting to determine the corresponding time needed to open the water valve for the desired water volume.  

Here is an example of a calibration from Tolias Lab.

```{code-block} python
import numpy as np
import matplotlib.pyplot as plt

time = [100,200,300,400,500,600,700,800,900,1000]
time = [100,200,300,400,500,600,700,800,900,1000]

# 2024-07-08
valve_1 = [0.0221,0.0548,0.0867,0.1206,0.1537,0.1859,0.2190,0.2504,0.2832,0.3074]
valve_2 = [0.0228,0.0539,0.0864,0.1205,0.1529,0.1864,0.2185,0.2542,0.2864,0.3179]

valve = valve_1 + valve_2
time_2 = time + time

def func_time (x,m,l):
   return m*np.array(x) + l

from scipy.optimize import curve_fit
popt, pcov = curve_fit(func_time, valve, time_2)

plt.plot(valve_1,time,color='black',label ='valve 1',marker='8')
plt.plot(valve_2,time,color='red',label='valve 2',marker='8')
plt.plot(valve,func_time(valve,*popt),color='blue',label='func',marker='8',alpha = 0.5)
plt.xlabel('weight g')
plt.ylabel('time ms')
plt.legend()
# plt.savefig("time needed for water weight.jpg")

# get reward size
reward_size = func_time(0.005,*popt)
print('reward size 5ul = ' + str(reward_size)+'ms')
```

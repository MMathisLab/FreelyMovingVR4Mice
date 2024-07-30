# Another Teensy for Recording from the Photodiode

To compute the latency of the system or for synchronization with a recording device, we have created an option to record a signal from the computer monitor using a photodiode via a teensy. This is a separate teensy from the one that is used for the water delivery. To do this the dlc processor script generates an oscillating signal that can be sent to the unity game and rendered as a black and white square in the top right hand corner of one of the computer monitors. This signal can be read using a photodiode that is attached to the screen via a teensy and is read on a separate thread within the dlc processor and time stamped. 

Here is a schematic of the circuit:

```{image} ../../docs/images/Schematic_photodiode_detector.jpg
:alt: pd
:class: bg-primary mb-1
:width: 400px
:align: center
```

Once the cicuit is built upload this [script](../../mouse_task/teensy/dual_water_valve/photodiode_reads.ino) onto it and update the `COM` port and `baudrate` in the `dlc_inference_w_pd` class in the `dlc_processor_socket_pd.py`.

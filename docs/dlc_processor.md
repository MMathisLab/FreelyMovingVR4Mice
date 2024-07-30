---
jupytext:
  formats: md:myst
  text_representation:
    extension: .md
    format_name: myst
kernelspec:
  display_name: Python 3
  language: python
  name: python3
---

# DLC processor file 
The dlc processor file is a python script that is loaded into the `dlclive-gui`. This file first establishes a socket with the `vr4mice `software. Then every time the camera captures an image of the mouse in the arena, it processes the pose of the animal and computes the mean position of its head on each frame in x, y, alongside the head angle and heading direction of the body. In addition to this the dlc processor generates an oscillating signal that can be sent to the unity game and rendered as a black and white square in the top right hand corner of one of the computer monitors. This signal can be read using a photodiode that is attached to the screen via a teensy and is read on a separate thread within the dlc processor and time stamped (please note that this is a separate teensy to the one that is used to deliver water rewards). This can be used either for latency testing or for synchronization with a recording device. **PLEASE USE THE `dlc_inference_w_pd `class.**



```{code-cell} ipython3
:tags: [dlc_processor_input]

class dlc_inference_w_pd(Processor):
    def __init__(self, com = "COM3", baudrate=9600, signal_delay = 10, signal_type ="pulse", freq =5, use_teensy = 1):
```

1. `com`: Str, the com port for the teensy, default is `COM3`
2. `baudrate`: Int, the baudrate that the teensy is running at, default is `9600`
3. `signal_delay`: Int, the delay between starting the game and the oscillating signal starting in seconds. This allows for the game to start before the signal starts being generated. 
4. `signal_type`: Str, options: `pulse` = a square wave pulse that changes in time (best to use), `flip`= a black and white signal that flips every time dlc sends a frame (caution: this can miss frames!!!), `sin` = a sine wave. default is `pulse`.
5. `freq`: Int, the frequency of the square pulse or sine wave. default is `5`
6. `use_teensy`: Bool: If the photodiode teensy is connected this should be set to `True` for recording the photodiode singal. If the photodiode teensy is not connected you can set this to `False`. If set to `False` the dlc processor will still send a signal but this will not be recorded using the photodiode. 

## Photodiode teensy
when the script is initialized and the use_teensy parameter is set to true the script starts reading from the teensy on a separate thread:


```{code-cell} ipython3
:tags: [check_reward]
if use_teensy == 1:
    self.teensy = TeensyLatency(com, baudrate=baudrate)
    print("using_teensy")
```


## The process function
The process function takes the dlc pose and computes the head x,y positions, head_angle and heading direction of the body and then send these via a socket to the vr4mice software.


```{code-cell} ipython3
:tags: [check_reward]

def process(self, pose, **kwargs):
        #print(pose.keys())
        xy = pose[:, :2]
        conf = pose[:, 2]

        # compute head position using a weighted average of the head keypoints
        head_xy = xy [[0, 1, 2, 3, 4, 5, 6, 26],:]
        head_conf =  conf [[0, 1, 2, 3, 4, 5, 6, 26]]
        center = np.average(head_xy, axis=0, weights=head_conf)

        # compute head angle and body heading direction
        body_axis = xy[7] - xy[13]  # tail_base -> neck
        body_axis /= sqrt(np.sum(body_axis ** 2))
        head_axis = xy[0] - xy[7]  # neck -> nose
        head_axis /= sqrt(np.sum(head_axis ** 2))
        cross = body_axis[0] * head_axis[1] - head_axis[0] * body_axis[1]
        sign = copysign(1, cross)  # Positive when looking left
        try:
            head_angle = acos(body_axis @ head_axis) * sign
        except ValueError:
            head_angle = 0
        
        #Generate synchronization signal
        self.curr_time = time.time()
        self.curr_signal = self.get_signal(curr_time = self.curr_time, st=self.start_time,
                                           freq = self.signal_freq, 
                                           delay=self.signal_delay,  
                                           signal_type=self.signal_type)
        
        self.curr_step + self.curr_step + 1

        heading = atan2(body_axis[1], body_axis[0])
        heading = degrees(heading)
        vals = *center, heading % (360), head_angle, self.curr_signal
        
        # add data for saving
        self.center_x.append(vals [0])
        self.center_y.append(vals [1])
        #print("center_y: ", vals [1], ", center_x: ", vals [0])
        self.heading_direction.append(vals [2])
        self.head_angle.append(vals [3])
        self.time_stamp.append(self.curr_time)
        self.step.append(self.curr_step)
        self.signal.append(self.curr_signal)
        self.frame_time.append(kwargs ["frame_time"])
        
        # send the data and time stamp via the socket
        self.conn.send([time.time(), vals [0], vals [1], vals [2], vals [3], vals [4]])
        return pose
```

## Save function
At the end of the experiment when the experimenter stops the recording and hits save video in the dlclivegui window the data is then saved using this function:




```{code-cell} ipython3
:tags: [check_reward]
    def save(self, file=None):
        save_code = 0
        if file:
            print(file)
            try:
                save_dict = self.save_latency_data()
                print(save_dict)
               
                pickle.dump(
                    save_dict,
                    open(file, "wb"),
                )
                save_code = 1
            except Exception:
                save_code = -1
        return save_code
    
    def save_latency_data(self):
        self.teensy.close_serial()
        save_dict =  dict()
        save_dict ["start_time"] = np.array(self.start_time)
        save_dict ["frame_time"] = np.array(self.frame_time)
        save_dict ["time_stamp"] = np.array(self.time_stamp)
        save_dict ["step"] =  np.array(self.step)
        save_dict ["signal"] = np.array(self.signal)
        save_dict ["photodiode_read"] = np.array(self.teensy.input_data)
        save_dict ["photodiode_time"] = np.array(self.teensy.input_data_time)
        save_dict ["x_pos"] =np.array(self.center_x)
        save_dict ["y_pos"] = np.array(self.center_y)
        save_dict ["heading_direction"] = np.array(self.heading_direction)
        save_dict ["head_angle"] = np.array(self.head_angle)
        return(save_dict)
```

This data gets saved into `*_PROC` file which can be loaded as a pickle.

parameters:
1. `start_time`: Float, the time that the script was started
2. `frame_time`: Vector, the time stamp that for when the camera
3. `time_stamp`: Vector, time stamp for when data was sent through the socket
4. `step`: Vector, the step number containing how many times the process function was called
5. `signal`: Vector, the generated oscillating signal
6. `photodiode_read`: Vector, the recorded signal from the photodiode
7. `photodiode_time`: Vector, the time stamps for each of the reads from the photodiode
8. `x_pos`: Vector, the x position of the head (pixels)
9. `y_pos`: Vector, the y position of the head (pixels)
9. `heading_direction`: Vector, the heading direction of the body of the mouse (degrees)
10. `head_angle`: Vector, the angle of the head relative to the body of the mouse (degrees)

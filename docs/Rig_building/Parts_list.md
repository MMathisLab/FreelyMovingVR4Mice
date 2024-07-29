# Parts list

## Computer:
Lambda vector workstation:

Operating system: Windows 10 Pro: Includes TensorFlow, PyTorch, CUDA, cuDNN, and Visual Studio. Processor: Intel Core i9-10900X: 10 cores, 3.70 GHz, 19.25 MB cache

CPU Cooler: Air cooling

GPUs: 2x RTX 3080 

Memory: 128 GB

Operating system drive: 1 TB SSD (NVMe)

Data drive: 2 TB SSD (SATA)

Network: 2x 1 gigabit LAN (RJ45)

Case: Lambda Vector case

## Cameras:
2 x imaging source cameras (DMK 37BUX28) + cables

2 x Navitar lenses (3.5mm EFL, F1/4 1/2”)

Two cameras are necessary if you would like to use 3d reconstruction.


## Thor labs parts (for building monitor mounting cage):
5 x [Raw, Unanodized 25 mm Rail Extrusion, 2 m](https://www.thorlabs.com/thorproduct.cfm?partnumber=XE25RL2)

4 x [1" Construction Cube](https://www.thorlabs.com/thorproduct.cfm?partnumber=RM1G)

15 x [Right-Angle Bracket for 25 mm Rails](https://www.thorlabs.com/thorproduct.cfm?partnumber=XE25A90)

2x [Drop-In T-Nut, 1/4\"-20 Tapped Hole, 10 Pack](http://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=4101)

1x [1/4\"-20 Low-Profile Channel Screw, 5/8\" Long, 50 Pack](http://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=4101)


## Water delivery teensy components:
We will send across one of our custom PCB boards with these components attached but this is the parts list for these just in case:

- Teensy 4.0

- [TIP120G, Darlington Transistor, TO-220, NPN, 60V, onsemi](https://www.distrelec.ch/en/darlington-transistor-npn-60v-to-220-onsemi-tip120g/p/30240404?no-cache=true&marketingPopup=false&track=true)

- [1N4005-E3/54 - Standard Recovery Rectifier Diode 600V 1A DO-204AL, Vishay](https://www.distrelec.ch/en/standard-recovery-rectifier-diode-600v-1a-do-204al-vishay-1n4005-e3-54/p/30151890?marketingPopup=false&no-cache=true&track=true)

## photodiode teensy components (optional):

- Teensy 4.0
- 1.2 pF capacitor
- 330 kOhms resistor
- Photodiode - TEFD4300
- OpAmp - MCP6002-I/P


## Monitors:
5x acer (SB241Y) + HDMI cables

4 monitors for the mouse setup, 1 for launching the task.

**Calibration:**
- For all, brightness: 18.
- For the side and back monitors: 153 pixels full screen image (see plot of luminance across pixels)

```{image} ../../docs/images/monitor_luminance.png
:alt: monitors_luminance
:class: bg-primary mb-1
:width: 400px
:align: center
```


## Anti-reflection material: 

4x [0.9 neutral density filters](https://www.amazon.com/Filters-Neutral-Density-Compact-Roll/dp/B0C5KT8H5P/ref=sr_1_3?crid=LZW094XXVJMZ&keywords=LEE+Filters+211+0.9+Neutral+Density+Filter&qid=1698694952&sprefix=lee+filters+211+0.9+neutral+density+filter%2Caps%2C412&sr=8-3). For all screens, to decrease the monitor luminance into the 10 cd/m2 range.

1x [Anti-glare adhesive](https://www.amazon.com/dp/B0BZ33NP92?ref_=cm_sw_r_cso_cp_apin_dp_MFR3FADA7P2NRNE6F3CY&starsLeft=1&language=en-US&th=1). For the floor. The size is not exactly the same as the setup floor. The seam needs to be at the back of the box (close to the back monitor). Mice do not seem to show interest in it (or very briefly at the beginning).


## Transparent Perspex box:

2x Floor: 520 x 520 x 5 mm (transparent plastic = PMMA).

4x Sides: 525 x 360 x 5 mm (transparent plastic = PMMA).

1x [light diffuser](https://www.thomannmusic.ch/lee_farbfolie_rolle_216_w_diffusi.htm) (The size of the sheet must be able to cover the floor plate ie. 520mm x 520mm)


## IR lights:
4 x [lights](https://www.amazon.com/CMVision-IR30-WideAngle-IR-Illuminator/dp/B001P2E4U4)

## Water valves
[Solenoid (solenoid: Lee lhda1233115H2)](https://www.theleeco.com/product/high-flow-2-way-single-coil-solenoid-valve/)

## Power supply
1x Power Supply (12V Wall wart)

## 3D printed parts
8 x  Top monitor holder - `../stl_files/top_monitor_holder.stl`

4 x Bottom monitor holder - `../stl_files/Bottom_monitor_holder_only.stl`

4 x Bottom monitor holder with box adaptor - `../stl_files/Bottom_monitor_box_holder.stl`







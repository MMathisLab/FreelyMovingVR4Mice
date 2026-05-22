# Parts list

## Computer

Lambda vector workstation:

Operating system: Windows 10 Pro: Includes TensorFlow, PyTorch, CUDA, cuDNN, and Visual Studio.

Processor: Intel Core i9-10900X: 10 cores, 3.70 GHz, 19.25 MB cache

Motherboard: ASUS ws x299 sage

CPU Cooler: Air cooling

GPUs: 2 x RTX 3080

Memory: 128 GB

Operating system drive: 1 TB SSD (NVMe)

Data drive: 2 TB SSD (SATA)

Network: 2 x 1 Gigabit LAN (RJ45)

Case: Lambda Vector case

## Cameras

2 x imaging source cameras (DMK 37BUX28) + cables

2 x Navitar lenses (3.5mm EFL, F1/4 1/2”)

Two cameras are necessary if you would like to use 3d reconstruction.

## Parts for building montior-supporting cage

### Thor labs parts

5 x [Raw, Unanodized 25 mm Rail Extrusion, 2 m](https://www.thorlabs.com/thorproduct.cfm?partnumber=XE25RL2)

8 x [1" Construction Cube](https://www.thorlabs.com/thorproduct.cfm?partnumber=RM1G)

5 x [Right-Angle Bracket for 25 mm Rails](https://www.thorlabs.com/thorproduct.cfm?partnumber=XE25A90) (4 + 1 for the camera)

2 x [Drop-In T-Nut, 1/4\"-20 Tapped Hole, 10 Pack](http://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=4101)

1 x [1/4\"-20 Low-Profile Channel Screw, 5/8\" Long, 50 Pack](http://www.thorlabs.com/newgrouppage9.cfm?objectgroup_id=4101)

### 3D printed parts

8 x [Top monitor holder](https://github.com/MMathisLab/FreelyMovingVR4Mice/blob/main/docs/stl_files/top_monitor_holder.stl)

4 x [Bottom monitor holder](https://github.com/MMathisLab/FreelyMovingVR4Mice/blob/main/docs/stl_files/Bottom_monitor_holder_only.stl)

4 x [Bottom monitor holder with box adaptor](https://github.com/MMathisLab/FreelyMovingVR4Mice/blob/main/docs/stl_files/Bottom_monitor_box_holder.stl)

## Water delivery

### Teensy components

The teensy circuit will need to be soldered to a perforated board:

- Teensy 4.0

- [TIP120G, Darlington Transistor, TO-220, NPN, 60V, onsemi](https://www.distrelec.ch/en/darlington-transistor-npn-60v-to-220-onsemi-tip120g/p/30240404?no-cache=true&marketingPopup=false&track=true)

- [1N4005-E3/54 - Standard Recovery Rectifier Diode 600V 1A DO-204AL, Vishay](https://www.distrelec.ch/en/standard-recovery-rectifier-diode-600v-1a-do-204al-vishay-1n4005-e3-54/p/30151890?marketingPopup=false&no-cache=true&track=true)

### Lickports & Water circuitery

- [EW-06407-41 - Cole-Parmer, PTFE Tubing, 1/32"ID x 1/16"OD](cole_parmer_ew_06407_41_packof1_masterflex_transfer_p9556775) rigid tube that goes from the valves to the lickport cases.

- 2 x [Lickport case](../stl_files/lickport_case.stl).


Additional tubing material and synringes to complete the water delivery system:

- Auxiliary [Masterflex Peroxide-cured silicone tubing, L/S 13, 25 ft.](https://www.vwr.com/us/en/product/NA5144570/masterflex-ls-precision-pump-tubing-peroxide-cured-silicone-avantor) for the water delivery system. Necessary to bridge syringes, valves, and lickport tubes together.

- 2 x [20 ml syringe](https://www.eickemeyer.com/shop/050361-eickinject-3-part-syringe-20ml-50-box-sterile-14177#attr=) with needle. Used as water reservoirs.

 ```{hint}
 *Lick port v2:* Following a redesign of the reward ports so that all tubings are outside the arena, we designed new lick ports composed of a [first](../stl_files/lickport_v2_1.stl) and [second](../stl_files/lickport_v2_2.stl) part that needs to be threaded and screwed together. They insert in a water slot in the Perspex box directly.
  ```

## Photodiode teensy components (optional)

<u>Tolias lab set-up</u>:

- Teensy 4.0
- TSL257, with a built-in circuit

<u>Mathis lab setup</u>:

- OPT101 (Texas Instruments)
- Mounting board for the photodiode - CJMCU-101
- 1 Megaohm resistor

## Monitors

4 x acer (SB241Y) + HDMI cables

3 monitors for the mouse setup, 1 for launching the task.

**Calibration:**

- For all, brightness: 18.
- For the side and back monitors: 153 pixels full screen image (see plot of luminance across pixels)

```{image} ../../docs/images/monitor_luminance.png
:alt: monitors_luminance
:class: bg-primary mb-1
:width: 400px
:align: center
```

## Anti-reflection and filtering material

4 x [0.9 neutral density filters](https://www.amazon.com/Filters-Neutral-Density-Compact-Roll/dp/B0C5KT8H5P/ref=sr_1_3?crid=LZW094XXVJMZ&keywords=LEE+Filters+211+0.9+Neutral+Density+Filter&qid=1698694952&sprefix=lee+filters+211+0.9+neutral+density+filter%2Caps%2C412&sr=8-3) for all screens, to decrease the monitor luminance to the 10 cd/m2 range.

1 x [Anti-glare adhesive](https://www.amazon.com/dp/B0BZ33NP92?ref_=cm_sw_r_cso_cp_apin_dp_MFR3FADA7P2NRNE6F3CY&starsLeft=1&language=en-US&th=1) for the floor. The size is not exactly the same as the setup floor. The seam needs to be at the back of the box (close to the back monitor). Mice do not seem to show interest in it (or very briefly at the beginning).

1 x [Light diffuser sheet](https://leefilters.com/colour/216/) to be placed between the two perspex floor plates.

## Transparent Perspex box

2 x Floor: 520 x 520 x 5 mm (transparent plastic = PMMA).

4 x Sides: 525 x 360 x 5 mm (transparent plastic = PMMA).

## IR lights

4 x [lights](https://www.amazon.com/CMVision-IR30-WideAngle-IR-Illuminator/dp/B001P2E4U4)

## Power supply

1 x Power Supply (12V Wall wart)

## Monitor Luminance Measurement

### Some Information
- **Luminance Meter**: KONICA MINOLTA LS-100
- **Monitor**: Acer SB241Y Abi 23.8" Full HD (1920 x 1080) VA Zero-Frame Home Office Monitor
- **0.9 Neutral Density Filter**: [Lee Filters 0.9 Neutral Density Filter](https://www.amazon.com/lee-filters-diffusion-lighting-gel-pack/dp/B0C5KT8H5P/ref=sr_1_7_sspa?crid=35Q5LB7GFKQ20&dib=eyJ2IjoiMSJ9.kJjJZFNRFwKRCg_4cgQHTdvtGFV3ketrVOEHMeX4JQRz9NCUoCJNT99_cVRAnvgI3e0AICo1PtKW5OC4ViLKHuWnOQbXFpJkG5XMAvpNyF_TEf-sFMdavP9epNYewtJTN07f6k9pH4nvIo14bPSWg_o0aXShHBjxdkFjfg-D14LjmcB13kUtMJHpWCKBnQ1mrUfy0prxxSNCYULhrF0yTk-SWlUDOLxJLl0ey9Aoxv4.aE-hVi2GVpNyaNjq0IkXOG6rJrGIKp08Up7yCowUtm0&dib_tag=se&keywords=Neutral+Density+Gels+Filter+ND9&qid=1721919620&sprefix=neutral+density+gels+filter+nd9%2Caps%2C133&sr=8-7-spons&sp_csd=d2lkZ2V0TmFtZT1zcF9tdGY&psc=1)

### Tolias Lab Monitor Display Setup
##### Hardware (monitor settings)
- **Brightness**: 18
- **Contrast**: 50
- **Black Boost**: 6
- **Blue Light**: Off
- **ACM**: Off
- **Super Sharpness**: On

##### Software (Settings-Display)
- **Night Light**: Off
- **Stream HDR Video**: No
- **Use HDR**: No
- **Use WCG Apps**: No

### Procedure
1. Temporarily turn off the four infrared supplementary lights and cover any excess indicator lights with black electrical tape. Ensure there are no other light sources in the room except for the four screens.
2. Position the photometer aiming at the center of the screen, 21 cm away, with the top of the photometer flat on the arena floor. You can use tape to mark the position of the photometer to ensure it is placed in the same spot each time.
3. Sequentially display images with brightness levels ranging from 0 to the maximum (0-255 pixels, with one image every 17 pixels) in full screen mode. You can find all the required images [here](https://github.com/MMathisLab/FreelyMovingVR4Mice/tree/main/docs/images/Intensity_calibration_images/)!
4. Measure the luminance multiple times to ensure stable results.
5. Adjust the monitor brightness and apply filters to ensure that the light intensity at maximum brightness is approximately 10 cd/m². This corresponds to the mesopic light intensity regime, where both rods and cones are active.


Here are the monitor luminance measurement results from Tolias Lab. You can use the provided code to calculate the gamma value of the monitor after adding the neural density filter.

```python
import numpy as np
import matplotlib.pyplot as plt
from skimage import io

image_pixels = [0,17,34,51,68,85,102,119,136,153,170,187,204,221,238,255]
luminance = [0.039,0.144,0.309,0.523,0.874,1.245,1.703,2.273,2.926,3.688,4.481,5.503,6.506,7.653,8.792,10.08]

from scipy.optimize import curve_fit
def func(x, a, b, m):
    return a + b * (x**m)
popt, pcov = curve_fit(func,image_pixels, luminance)
gamma = popt[2]
print('gamma value = ' + str(gamma))

plt.plot(image_pixels, func(image_pixels,*popt),color = 'black',marker='8' ,alpha=1, label = 'func luminace')
plt.plot(image_pixels, luminance,color = 'red',marker='8', alpha=0.5, label = 'measured luminance')
plt.title('with filter -- luminance value across image pixels value')
plt.xlabel('pixel')
plt.ylabel('luminance cd/m2')
plt.legend()
#plt.savefig("with filter -- luminance value across image pixels value.jpg")
```

**Generate the images for measurement.**

```python
import numpy as np
import matplotlib.pyplot as plt
from PIL import Image
import os

width, height = 1920, 1080 

save_dir = '/Users/yang/Desktop/temp/pixel'  # Adjust this to your desired directory
if not os.path.exists(save_dir):
    os.makedirs(save_dir)

# Loop through pixel intensities from 0 to 255 in steps of 17
for pixel_intensity in range(0, 256, 17):
    image_array = np.full((height, width), pixel_intensity, dtype=np.uint8)
    
    plt.figure(figsize=(6, 6))
    plt.imshow(image_array, cmap='gray', vmin=0, vmax=255)
    plt.axis('off')
    plt.title(f'Pixel Intensity: {pixel_intensity}')
    plt.show()
    
    # Save the image as a PNG file
    image = Image.fromarray(image_array)
    image.save(os.path.join(save_dir, f'image_{pixel_intensity}_intensity.png'))

    print(f"Image saved as 'image_{pixel_intensity}_intensity.png'")

print("All images have been generated and saved.")
```

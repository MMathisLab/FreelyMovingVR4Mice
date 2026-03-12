# Random occluders task

To test whether mice seek out obstructed information we have developed a random occluder task. In this task the occluder slit size randomly changes on every trial. On trials where the task is more difficult (i.e. the slit size is narrower) the mouse needs to move to new locations to seek out the information required to perform the discrimination task. 

In this task there are two new parameters:

1. `slit size`: this is a list of numbers [min_slit_size, max_slit_size, number_of_slit_sizes] i.e. [10,20,5] would give a range of 5 slit sizes with 10 being the minimum and 20 being the max.

2. `target rotation`:  to prevent self occlusion of the zebra object a parameter controlling the target rotation has also been occluded, changing this parameter will cause the tail of the tear drop to be rotated towards the mouse (if a positive number is given)




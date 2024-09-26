# Contrast discrimination game parameters

## Detection task

### Stage 1, P1

```{admonition} Permissive trial initiation
:class: dropdown
:name: stage-1-p1

- | Parameter          | Value                     | Parameter          | Value                     |
  |--------------------|---------------------------|--------------------|---------------------------|
  |teensy              |`teensy` object            |slit_size           |`[4.0, 4.0, 1]`            |
  |monitor             |`None`                     |slit_depth          |`0.2`                      |
  |write_video         |`False`                    |target_selection    |`6.0`                      |
  |fps                 |`60.0`                     |distractor_selection|`4.0`                      |
  |session_label       |`["ar_detection_no_velthr]`|occlusion_type      |`0.0`                      |
  |epochs              |`[250]`                    |camera_type         |`1.0`                      |
  |epoch_labels        |`["single_teardrop"]`      |target_spread       |`4.0`                      |
  |config_file_path    |`Path` object              |target_rotation     |`0`                        |
  |reward_size         |`100`                      |target_size         |`2.0`                      |
  |cropped_image       |`[0, 530, 0, 510]`         |target_height       |`3.0`                      |
  |unity_arena_size    |`[-9, 9, -10, -2]`         |block_length        |`1.0`                      |
  |r_report_box        |`[5, 10, -4, -2]`          |start_box_delay     |`0.1`                      |
  |l_report_box        |`[-10, -5, -4, -2]`        |velocity_threshold  |`20.0`                     |
  |start_box           |`[-4, 4, -9, -5, 90]`      |distractor          |`0.0`                      |
  |rotate_camera       |`90.0`                     |grey_screen_active  |`0.0`                      |
  |prob_obj_on_left    |`0.5`                      |target_distance     |`3`                        |
  |prob_block_coherence|`0.5`                      |use_dlc             |`True`                     |
  |mouse_report_delay  |`0.0`                      |                    |                           |
```

### Stage 1, P2

```{admonition} Restricted trial initiation
:class: dropdown
:name: stage-1-p2

- | Parameter          | Value                     | Parameter          | Value                     |
  |--------------------|---------------------------|--------------------|---------------------------|
  |teensy              |`teensy` object            |slit_size           |`[19.0, 20.0, 2]`          |
  |monitor             |`None`                     |slit_depth          |`0.2`                      |
  |write_video         |`False`                    |target_selection    |`6.0`                      |
  |fps                 |`60.0`                     |distractor_selection|`4.0`                      |
  |session_label       |`["ar_detection_velthr]`   |occlusion_type      |`0.0`                      |
  |epochs              |`[250]`                    |camera_type         |`1.0`                      |
  |epoch_labels        |`["single_teardrop"]`      |target_spread       |`4.0`                      |
  |config_file_path    |`Path` object              |target_rotation     |`0`                        |
  |reward_size         |`100`                      |target_size         |`2.0`                      |
  |cropped_image       |`[0, 530, 0, 510]`         |target_height       |`3.0`                      |
  |unity_arena_size    |`[-9, 9, -10, -2]`         |block_length        |`1.0`                      |
  |r_report_box        |`[5, 10, -4, -2]`          |start_box_delay     |`0.25`                     |
  |l_report_box        |`[-10, -5, -4, -2]`        |velocity_threshold  |`10.0`                     |
  |start_box           |`[-4, 4, -9, -5, 90]`      |distractor          |`0.0`                      |
  |rotate_camera       |`90.0`                     |grey_screen_active  |`0.0`                      |
  |prob_obj_on_left    |`0.5`                      |target_distance     |`3`                        |
  |prob_block_coherence|`0.5`                      |use_dlc             |`True`                     |
  |mouse_report_delay  |`0.0`                      |                    |                           |
```

## Discrimination task

### Stage 2

```{admonition} Contrast discrimination without occlusion
:class: dropdown
:name: stage-2

- | Parameter          | Value                     | Parameter          | Value                     |
  |--------------------|---------------------------|--------------------|---------------------------|
  |teensy              |`teensy` object            |slit_size           |`[4.0, 10.0, 2]`           |
  |monitor             |`None`                     |slit_depth          |`0.2`                      |
  |write_video         |`False`                    |target_selection    |`6.0`                      |
  |fps                 |`60.0`                     |distractor_selection|`4.0`                      |
  |session_label       |`["ar_discrim"]`           |occlusion_type      |`0.0`                      |
  |epochs              |`[250]`                    |camera_type         |`1.0`                      |
  |epoch_labels        |`["dual_teardrop"]`        |target_spread       |`4.0`                      |
  |config_file_path    |`Path` object              |target_rotation     |`0`                        |
  |reward_size         |`100`                      |target_size         |`2.0`                      |
  |cropped_image       |`[0, 530, 0, 510]`         |target_height       |`3.0`                      |
  |unity_arena_size    |`[-9, 9, -10, -2]`         |block_length        |`1.0`                      |
  |r_report_box        |`[5, 10, -4, -2]`          |start_box_delay     |`0.25`                     |
  |l_report_box        |`[-10, -5, -4, -2]`        |velocity_threshold  |`10.0`                     |
  |start_box           |`[-4, 4, -9, -5, 90]`      |distractor          |`1.0`                      |
  |rotate_camera       |`90.0`                     |grey_screen_active  |`0.0`                      |
  |prob_obj_on_left    |`0.5`                      |target_distance     |`3`                        |
  |prob_block_coherence|`0.5`                      |use_dlc             |`True`                     |
  |mouse_report_delay  |`0.0`                      |                    |                           |
```

### Stage 3

```{admonition} Contrast discrimination with single occlusion size
:class: dropdown
:name: stage-3

- | Parameter          | Value                     | Parameter          | Value                     |
  |--------------------|---------------------------|--------------------|---------------------------|
  |teensy              |`teensy` object            |slit_size           |`[4.3, 12.0, 2]`           |
  |monitor             |`None`                     |slit_depth          |`0.2`                      |
  |write_video         |`False`                    |target_selection    |`6.0`                      |
  |fps                 |`60.0`                     |distractor_selection|`4.0`                      |
  |session_label       |`["ar_discrim_occluders]`  |occlusion_type      |`1.0`                      |
  |epochs              |`[250]`                    |camera_type         |`1.0`                      |
  |epoch_labels        |`["dual_teardrop"]`        |target_spread       |`4.0`                      |
  |config_file_path    |`Path` object              |target_rotation     |`0`                        |
  |reward_size         |`100`                      |target_size         |`2.0`                      |
  |cropped_image       |`[0, 530, 0, 510]`         |target_height       |`3.0`                      |
  |unity_arena_size    |`[-9, 9, -10, -2]`         |block_length        |`1.0`                      |
  |r_report_box        |`[5, 10, -4, -2]`          |start_box_delay     |`0.25`                     |
  |l_report_box        |`[-10, -5, -4, -2]`        |velocity_threshold  |`10.0`                     |
  |start_box           |`[-4, 4, -9, -5, 90]`      |distractor          |`1.0`                      |
  |rotate_camera       |`90.0`                     |grey_screen_active  |`0.0`                      |
  |prob_obj_on_left    |`0.5`                      |target_distance     |`3`                        |
  |prob_block_coherence|`0.5`                      |use_dlc             |`True`                     |
  |mouse_report_delay  |`0.0`                      |                    |                           |
```

### Stage 4

```{admonition} Contrast discrimination with multiple occlusion sizes
:class: dropdown
:name: stage-4

- | Parameter          | Value                     | Parameter          | Value                     |
  |--------------------|---------------------------|--------------------|---------------------------|
  |teensy              |`teensy` object            |slit_size           |`[12.0, 8.48, 6., 4.2, 3]` |
  |monitor             |`None`                     |slit_depth          |`0.2`                      |
  |write_video         |`False`                    |target_selection    |`6.0`                      |
  |fps                 |`60.0`                     |distractor_selection|`4.0`                      |
  |session_label       |`["ar_discrim_5_occluders]`|occlusion_type      |`1.0`                      |
  |epochs              |`[250]`                    |camera_type         |`1.0`                      |
  |epoch_labels        |`["dual_teardrop"]`        |target_spread       |`4.0`                      |
  |config_file_path    |`Path` object              |target_rotation     |`0`                        |
  |reward_size         |`100`                      |target_size         |`2.0`                      |
  |cropped_image       |`[0, 530, 0, 510]`         |target_height       |`3.0`                      |
  |unity_arena_size    |`[-9, 9, -10, -2]`         |block_length        |`1.0`                      |
  |r_report_box        |`[5, 10, -4, -2]`          |start_box_delay     |`0.25`                     |
  |l_report_box        |`[-10, -5, -4, -2]`        |velocity_threshold  |`10.0`                     |
  |start_box           |`[-4, 4, -9, -5, 90]`      |distractor          |`1.0`                      |
  |rotate_camera       |`90.0`                     |grey_screen_active  |`0.0`                      |
  |prob_obj_on_left    |`0.5`                      |target_distance     |`3`                        |
  |prob_block_coherence|`0.5`                      |use_dlc             |`True`                     |
  |mouse_report_delay  |`0.0`                      |                    |                           |
```

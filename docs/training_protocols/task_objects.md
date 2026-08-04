# Task objects

This is the single reference list of the objects that can be spawned as targets and
distractors in the `Vr4mice` game. Select them by setting the `target_selection` and
`distractor_selection` parameters in the python GUI to the ID of the object you want.

Objects are matched by their index within the `Targets` list of the `target spawner`
script, so the IDs below must stay in sync with that list. See
{doc}`../software_unity_games/add_new_objects` for how to add a new object.

(sec:target-distractor-list)=

```{list-table} **List of available targets/distractors**
:align: center
:width: 500px
:header-rows: 1

* - ID
  - Name
  - Notes
* - `0.`
  - white cube
  - Used internally. Do NOT modify
* - `1.`
  - black cube
  - Used internally. Do NOT modify
* - `2.`
  - white teardrop
  - Original white teardrop
* - `3.`
  - black teardrop
  - Original black teardrop
* - `4.`
  - white teardrop
  - v2 iteration of white teardrop
* - `5.`
  - black teardrop
  - v2 iteration of black teardrop
* - `6.`
  - white pacman 10
  - v2
* - `7.`
  - black pacman 10
  - v2
* - `8.`
  - white pacman 20
  - v2
* - `9.`
  - black pacman 20
  - v2
* - `10.`
  - white pacman 30
  - v2
* - `11.`
  - black pacman 30
  - v2
* - `12.`
  - white threetails
  - v2
* - `13.`
  - black threetails
  - v2
```

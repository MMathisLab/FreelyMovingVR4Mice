# Adding new targets 
This page describes how to add new targets and distractor objects to the unity game such as the tear drop and the white pacman seen below:

```{image} ../../docs/images/black_white_pacman.png
:alt: black_white
:class: bg-primary mb-1
:width: 400px
:align: center
```
## Sculpting objects in blender 
To create new objects, or to edit the shape of existing objects in you will need to use blender:

1. to install blender visit this - https://www.blender.org/. 
2. Details on how to make and sculpt objects can be found in this youtube tutorial - https://www.youtube.com/watch?v=AMQcuRHWyOg.
3. This tutorial was useful for creating the original tear drop - https://blender.stackexchange.com/questions/199456/how-to-model-a-teardrop-shape

When saving objects from blender to use in unity you want to export the selected object as a `.FBX format`. This is a format that is also readable by unity. To do this you want to follow these steps: 

1. File > Export_as > Fbx
```{image} ../../docs/images/save_as_fbx.png
:alt: black_white
:class: bg-primary mb-1
:width: 400px
:align: center
```

2. make sure you tick the selected object only tab and export 
```{image} ../../docs/images/fbx_save_options.png
:alt: black_white
:class: bg-primary mb-1
:width: 400px
:align: center
```

If you have any issues with this you can find more detailed steps alongside an explanation of the different save options here - https://all3dp.com/2/blender-to-unity-how-to-import-blender-models-in-unity/#:~:text=Importing%20a%20Blender%20File%20to%20Unity,-Importing%20a%20Blender&text=Alternatively%2C%20move%20and%20save%20the,That's%20it.


## Importing the file into unity
To import the object into unity open the unity editor and click on the `asset tab` and then `import asset` and find the `.fbx` file that you want to import. Once imported the object will appear in the editor. 

Put the object into the prefab folder in the unity project. You will see that this object has a little play button on it. If you click on this play button the object will unravel and reveal multiple objects. We only want the object that looks like a "mesh" so drag this into the game and it should appear as a pink object - the reason that the object is pink is because it has no material attached to it. 

```{image} ../../docs/images/importing_to_unity.png
:alt: black_white
:class: bg-primary mb-1
:width: 400px
:align: center
```

## Adding a material
To create a new material click on the materials folder in the asset folder of the project tab. Then right click on a spare space within this `folder > Create > Material`. 

```{image} ../../docs/images/create_material.png
:alt: black_white
:class: bg-primary mb-1
:width: 400px
:align: center
```

Then give the material a name such as "blue" and then click on it to get the inspector window for that object to pop up. Then you can click on the color picker and change the color of the material. In this case I have gone for a blue.


```{image} ../../docs/images/create_material_2.png
:alt: black_white
:class: bg-primary mb-1
:width: 400px
:align: center
```
You can then drag an drop the material onto the object we just imported and it will turn it the color of the material.

```{image} ../../docs/images/create_material_3.png
:alt: black_white
:class: bg-primary mb-1
:width: 400px
:align: center
```

Then drag this colored object into the prefab folder so that we can programmatically spawn it (rather than it always being present in the game!). And give it a clear name.

## Adding the object to the list of targets and distractors
To add this newly made object to the list of objects that are used in the game:

In the hierarchy window select scenario > plane 

```{image} ../../docs/images/target_spawner_1.png
:alt: black_white
:class: bg-primary mb-1
:width: 400px
:align: center
```

This will open the inspector window for the plane object on the right hand side of the screen. Scroll down in this window until you find the `target spawner` script. scroll down some more and you will see a field called Targets. This Targets object is a list of individual game objects which can be spawned in the game. To add a new object increase the `size` parameter by 1 and then you will see an empty slot appear (it will say "None (Game Object)"). You can simply drag an drop the object that u recently imported onto this slot.

```{image} ../../docs/images/target_spawner_2.png
:alt: black_white
:class: bg-primary mb-1
:width: 400px
:align: center
```

The object can then be selected when running the Vr4mice game by changing either the `Target_selection` or `Distractor_selection` parameters in the python GUI with the number used corresponding to the index within the Targets list.


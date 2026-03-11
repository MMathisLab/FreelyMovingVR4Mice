# Add new target objects

This page describes how to add new targets and distractor objects to the unity game such as the tear drop and the white pacman below.

```{image} ../../docs/images/black_white_pacman.png
:alt: black_white
:class: bg-primary mb-1
:width: 800px
:align: center
```

## Sculpting objects in Blender 
To create new objects, or to edit the shape of existing objects, you will need to use [Blender](https://www.blender.org/):

1. To install Blender visit [their website](https://www.blender.org/). 

**Useful resources on how to use Blender:**
- Details on how to make and sculpt objects can be found in this [youtube tutorial](https://www.youtube.com/watch?v=AMQcuRHWyOg).
- [This tutorial](https://blender.stackexchange.com/questions/199456/how-to-model-a-teardrop-shape) was useful for creating the original tear drop.


2. When saving objects from Blender to use in Unity you want to export the selected object as a `.FBX format`. This is a format that is also readable by Unity. To do this you want to follow these steps: 

    1. `File` >> `Export` >> `Fbx`.

    ```{image} ../../docs/images/save_as_fbx.png
    :alt: save_as_fbx
    :class: bg-primary mb-1
    :width: 700px
    :align: center
    ```

    2. Make sure you tick `Selected Objects` only and click on `Export FBX`.

    ```{image} ../../docs/images/fbx_save_options.png
    :alt: fbx_save_options
    :class: bg-primary mb-1
    :width: 700px
    :align: center
    ```


ℹ️ If you have any issues with this, you can find more detailed steps alongside an explanation of the different save options [here](https://all3dp.com/2/blender-to-unity-how-to-import-blender-models-in-unity/#:~:text=Importing%20a%20Blender%20File%20to%20Unity,-Importing%20a%20Blender&text=Alternatively%2C%20move%20and%20save%20the,That's%20it).


## Importing the file into Unity

To import the object into Unity

- Open the Unity editor.
- Click on the `asset tab` and then `import asset` and find the `.fbx` file that you want to import. 
- Once imported the object will appear in the editor. Put the object into the prefab folder in the unity project. You should see that this object has a little play button on it. If you click on this play button the object will unravel and reveal multiple objects. We only want the object that looks like a "mesh" so drag this into the game and it should appear as a pink object - the reason that the object is pink is because it has no material attached to it.

    ```{image} ../../docs/images/importing_to_unity.png
    :alt: importing_to_unity
    :class: bg-primary mb-1
    :width: 700px
    :align: center
    ```

## Adding a material

To create a new material: 

- Click on the materials folder in the asset folder of the project tab.
- Right click on a spare space within this `folder` >> `Create` >> `Material`. 

    ```{image} ../../docs/images/create_material.png
    :alt: create_material
    :class: bg-primary mb-1
    :width: 700px
    :align: center
    ```

- Give the material a name, i.e. `blue`.
- Click on it to get the inspector window for that object to pop up. Then you can click on the color picker and change the color of the material. In this case I have gone for a blue.

    ```{image} ../../docs/images/create_material_2.png
    :alt: create_material_2
    :class: bg-primary mb-1
    :width: 700px
    :align: center
    ```

- Drag an drop the material onto the object we just imported and it will turn it to the color of the material.

    ```{image} ../../docs/images/create_material_3.png
    :alt: create_material_3
    :class: bg-primary mb-1
    :width: 700px
    :align: center
    ```

- Drag this colored object into the prefab folder so that we can programmatically spawn it (rather than it always being present in the game!). And give it a clear name.

## Adding the object to the list of targets and distractors
To add this newly made object to the list of objects that are used in the game:

- In the hierarchy window, select `scenario` >> `plane`. This will open the inspector window for the plane object on the right hand side of the screen.

    ```{image} ../../docs/images/target_spawner_1.png
    :alt: target_spawner_1
    :class: bg-primary mb-1
    :width: 700px
    :align: center
    ```

- Scroll down in this window until you find the `target spawner` script. 
- Scroll down some more and you will see a field called `Targets`. This `Targets` object is a list of individual game objects which can be spawned in the game. To add a new object increase the `size` parameter by 1 and then you will see an empty slot appear (it will say `None (Game Object)`). You can simply drag an drop the object that you recently imported onto this slot.

    ```{image} ../../docs/images/target_spawner_2.png
    :alt: target_spawner_2
    :class: bg-primary mb-1
    :width: 400px
    :align: center
    ```

You just created a new target! 💫 The object can then be selected when running the `Vr4mice` game by changing either the `Target_selection` or `Distractor_selection` parameters in the python GUI with the number used corresponding to the index within the `Targets` list.

Now, to make the object available for all users (and your future self), you can follow {doc}`../../docs/Unity_games/update_Unity_Game` to push the changes on the GitHub repo.
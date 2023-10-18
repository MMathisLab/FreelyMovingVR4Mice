# Augmented Reality Games

#### 💡 Developer Note
````{admonition}
DEV NOTE: This repo contains version 2 of the augmented reality game, 
orginally developed here: https://github.com/AdaptiveMotorControlLab/AugmentedRealityVersion2/blob/master/README.md
````

This Document outlines the code required to build the Unity games.

## Installation

To run the game(s) with MLagents you will need to:
1. Download and install anaconda:
https://www.anaconda.com/products/individual

2. Download and install unity (version 2019.3.2):
Download UnityHub: https://unity3d.com/fr/get-unity/download
Download Unity version: https://unity3d.com/fr/unity/whats-new/2019.3.2
Install both in the same order. 

3. Install MLagents:

Clone the ml_agents github repo: https://github.com/Unity-Technologies/ml-agents
Reset the version back to the one that we are using 

```
cd in git ml_agent folder
git reset --hard 803e62ff32f731995c11254a06c9ae15fe0a7567
```

4. Open the Unity-Hub, add the `AugmentedReality` folder as a project. Open the project and you will get an error saying that unity cannot find the mlagents package, this is fine just click continue and the project will still open.
 Then go to window >> package manager >> click on the plus icon then:
Add a new package from disk
Go to cloned mlagent git repository in the com.unity.ml-agent folder and select `package.json`

This will add your cloned MLagents repo to the game and if you now click on the ▶️ play icon, the game should start to run with no comiple errors.

If you encouter any additional problems let Tom know so that he can update this README with solutions!

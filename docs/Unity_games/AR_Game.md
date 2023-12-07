# Augmented Reality Game installation

This page outlines the steps required to install the Unity Augmented Reality game(s).

### Install Unity

#### Download and install Anaconda.

You can install Anaconda from the [Anaconda website](https://www.anaconda.com/products/individual) directly.

#### Download and install unity (version 2019.3.2).

Install both in the same order: 
- Download [UnityHub](https://unity3d.com/fr/get-unity/download).
- Download the right version (2019.3.2) of [Unity Editor](https://unity3d.com/fr/unity/whats-new/2019).

#### Install the MLagents package.

- Clone the `ml-agents` [github repo](https://github.com/Unity-Technologies/ml-agents).

```
git clone git@github.com:Unity-Technologies/ml-agents.git
```

- Reset the version back to the one that we are using:

```
cd ml_agent
git reset --hard 803e62ff32f731995c11254a06c9ae15fe0a7567
```

### Add the `AugmentedReality` project to Unity.

- Open the Unity-Hub app.
- Go to `Add` >> ``Add from disk`` and add the `FreelyMovingVR4Mice/AugmentedReality` folder as a project (you should have the repo cloned on your computer for that step -- see {doc}`../../docs/Installation/installSumUp` if that's not the case).
- Open the project. 🚨 You should get a `Unity Package Manager Error` pop-up message saying that Unity cannot find the `mlagents` package. Click `Continue` so the project opens anyway.

(unity:mlagents)=
### Add the `mlagents` package to your project.

- Go to `Window` >> `Package manager` >> click on the `+` icon.

```{image} ../../docs/images/window.png
:alt: window
:class: bg-primary mb-1
:width: 400px
:align: center
```

- Click on `Add package from disk...`. 

```{image} ../../docs/images/add_package.png
:alt: add-package
:class: bg-primary mb-1
:width: 400px
:align: center
```


- Go to the `ml-agents` folder you cloned previously and select `com.unity.ml-agents/package.json`. This should import the `ml-agents` package.

- If you now click on the ▶️ play icon, the game should start to run with no comiple errors.


ℹ️ If you encouter any problems, let the Mathis lab (as of now - 07.12.23 - contact Célia Benquet) know so that they can update this document with solutions!

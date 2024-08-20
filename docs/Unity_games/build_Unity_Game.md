# Rebuild a Unity game

If a game is updated in the `FreelyMovingVR4Mice` repo (see {doc}`../../docs/Unity_games/update_Unity_Game` if you want to update a game), you will need to rebuild the game entirely. Here are the steps to do so.

1. Pull the new version of the game, once the branch is merged into the `main` of the repo. For that, make sure you are in the `main` branch and run:

	```
	git pull
	```

2. Open the `Unity-Hub` app.
3. Open your `AugmentedReality` project (you need to have the project installed for this step -- follow {doc}`../../docs/Unity_games/AR_Game` if that's not the case already). You should get a `Unity Package Manager Error` pop-up message saying that Unity cannot find the `ml-agents` package. Click `Continue` so the project opens anyway.
4. You need to add the `ml-agents` package again. Follow the steps described in {ref}`Add the mlagents package to your project <unity:mlagents>`.
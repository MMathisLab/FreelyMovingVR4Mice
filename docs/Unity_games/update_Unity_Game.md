# Update the `AugmentedReality` game

The `FreelyMovingVR4Mice` repo is a classical GitHub repository. Below you will find classical resources on how to develop and manage code on GitHub. It is loosely based on the GitHub documentation on [how to contribute to projects](https://docs.github.com/en/get-started/quickstart/contributing-to-projects).

If you want to update game, here is the classical process:

1. Create a branch in which you will do all your changes.

    ```bash
    git checkout -b <your-name>/<your-update>
    ```

    **Example of branch name:** ``celia/add-circle-shape``.

2. Go ahead and make your changes on the project in your branch 🔥, using your favorite text editor, like [Visual Studio Code](https://code.visualstudio.com/).

3. When you are satisfied with your changes, commit your changes. `git add .` tells Git that you want to include all of your changes in the next commit, you can also specify the file to add, by replacing the `.` by the file names of the files you changed. `git commit` takes a snapshot of those changes. Please provide a message with your `git commit`, to specify what you implemented (see [how to write a good commit message](https://cbea.ms/git-commit/) if you're new at it 🤗).

    - To stage all changes, run:

        ```bash
        git add .
        ```

    - To commit all staged changes, run:

        ```bash
        git commit -m "your commit message"
        ```

    ```{tip}
    For more information you can check the [Git documentation](https://git-scm.com/book/en/v2/Git-Basics-Recording-Changes-to-the-Repository).
   ```

4. Right now, your changes only exist locally. When you're ready to push your changes up to GitHub, push your changes to the remote. For that, run:

    ```bash
    git push origin <name-of-your-branch>
    ```

5. You're ready to propose changes into the main project! 🎉 Next step is to create a pull request. Go to the [repo page](https://github.com/MMathisLab/FreelyMovingVR4Mice). By default, you're seeing the code on the `main` branch.

    - Select the branch with the changes you just pushed.

       ```{image} ../../docs/images/choose_branch.png
       :alt: create branch
       :class: bg-primary mb-1
       :width: 400px
       :align: center
       ```

    - Click on `Contribute` >> `Open pull request`.

       ```{image} ../../docs/images/open_pr.png
       :alt: open pull request
       :class: bg-primary mb-1
       :width: 100%
       :align: center
       ```

    - Add a clear title summarizing your changes, describe in detail your changes in the description, add reviewers and once you are satisfied with it, click on <u>**Create pull request**</u>.

       ```{image} ../../docs/images/create_pr.jpg
       :alt: create pull request
       :class: bg-primary mb-1
       :width: 100%
       :align: center
       ```

6. Congratulation you updated our codebase! 🧚‍♀️ The reviewers will read your code and need to approve the changes. Then the changes can be merged to the main codebase.

🚨 To get the changes up and running on Unity, follow {doc}`../../docs/Unity_games/build_Unity_Game`.

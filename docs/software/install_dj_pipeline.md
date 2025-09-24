
# Install and Run the vr4mice pipeline

## Rig Data Transfer GUI Installation
1. `git clone` the [`FreelyMovingVR4Mice`](https://github.com/MMathisLab/FreelyMovingVR4Mice) repo.
2. Ensure that Python 3 and PyQt 5 are installed (else, a setup file is provided).
3. Navigate to the `gui_transfer/` folder and locate the `config.json` file within the `config/` folder.
4. Fill in the appropriate paths within the `config.json` file.
5. Start the GUI:
   - *For Linux/Mac,* execute the command `make run_gui` from the `gui_transfer/` folder root.
   - *For Windows,* adjust the paths in the provided batch file.

## DataJoint database user remote access via Jupiter Notebook
1. Ensure that `jupyter-notebook` is installed, `vr4mice` repository is loaded, and `base_schemas` is pip-installed.
2. Update information in the `env.py` file (IP of server, user name and password provided by administrator).
3. From working `vr4mice` directory start Jupyter Notebook and create a new Python3 page.
4. ```%run env.py``` to load environmental variables
5. ```%run run.py connect``` to connect
7. Bravo 👏! Data can be fetched ```vr4mice.Dataset()``` (relative imports were done in the run script).

## DataJoint database user remote access
> Similar to [general auxPipelines connection instructions](https://github.com/AdaptiveMotorControlLab/auxPipelines-DataJoint_Mathis?tab=readme-ov-file#connect-to-database-from-local-host-to-remote-server).

1. Obtain server access and database user credentials from the administrator (add them to the `.env` file).
2. To connect to a remote database from a local host, modify the server IP address and user credentials in the `docker-compose` file.
3. Build the client service container using the `docker-compose` file and the command `make build_client`.
4. Run the client container to access the remote database using the command `make up_client`.
5. To connect to the DataJoint database, launch `make ipython` and execute the minimal script `%run run.py connect`. 

## DataJoint database deployment (on server or locally)
### Setup Instructions
1. **Ensure that Docker Compose is installed and that the user is added to the Docker group.** Refer to the [Docker installation guide](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository) for more info.
    ```bash
    # Add user to the Docker group
   sudo usermod -aG docker <username>
    ```
2. **Download the current repository.** Make sure your git key is active. Else [learn how to generate a SSH key for git](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent#generating-a-new-ssh-key).
   ```bash
   git clone git@github.com:MMathisLab/FreelyMovingVR4Mice.git
   cd dj_pipeline
   ```
3. **Adjust the paths in the shared volumes for the database storage and shared volumes.**
   ```bash
   # Create folders if needed to store the data and database (Warning concerning permissions on /mnt, run ```sudo chmod 0777 /mnt``` if needed or change the location)
   mkdir -p /path/to/database_directory
   mkdir -p /path/to/data_directory
   mkdir -p /mnt/database/vr4mice/vr4mice_database/database
   mkdir -p /mnt/database/vr4mice/vr4mice_database/data
   
   # if gui is not used /data/dlc_video /data/data /data/summary_plots have to be created manually
   mkdir -p /mnt/database/vr4mice/vr4mice_database/data/data/data
   mkdir -p /mnt/database/vr4mice/vr4mice_database/data/data/dlc_video
   mkdir -p /mnt/database/vr4mice/vr4mice_database/data/summary_plots
   
   # if gui is not used: unused
   mkdir -p /shared
   ```
4. To make the database accessible from any machine in the local subnet, change the IP in `docker-compose` to the server's IP (and choose the port). Find the IP address via `ifconfig`.

### Build and Run
5. **Build the Docker Compose** using the command `make build_all` to create the image for the DataJoint database and client container (do not use "sudo"). 

> This command will also start the containers.

6. **Add default MySQL credentials** to `~/.my.cnf` file. Ask the administrator for host, user, password.
   ```bash
   [client-vr4mice]
   host=host
   user=default_user
   password=default_pwd
   port=3309
   ```
   Now you can run `make mysql` to connect to the database from MySQL interface. Here you can create a new user or change the credentials of an existing one.

7. **Install base schemas inside the container.** Run `make base_install` from the host.

### Remote Access and Testing
8. **To connect to the DataJoint database remotely**, follow the instructions for local or remote connection provided in the previous section. To connect from the same server under the root account, you can call `make ipython` that will place you in the container's IPython shell.
   ```bash
   %run run.py connect
   # Import some schemas to play with 
   from base_schemas.schemas import exp, mice
   from vr4mice.schema import vr4mice
   vr4mice.Dataset()```
   
9. **Test populate:**
   Upload some files from GUI(s): `.pickle` file go to the `/mnt/database/vr4mice/vr4mice_database/data/data` folder and the `.hdf5` and `PROC.TS.npy` files in `/mnt/database/vr4mice/vr4mice_database/data/data/dlc_video` (`/data/dlc_video` path if you are in a container). Then run: 

```bash
   %run run.py populate
   # Import some schemas and check that Dataset is here
   from base_schemas.schemas import exp, mice
   from vr4mice.schema import vr4mice
   vr4mice.Dataset()
  ```
   > **Note: **
   > If the subfolder name is different (not `/data/data` but `/data/rawdata` for example, change the path in `run.py` script).

10. **To populate analysis**, run:
 ```bash
   from vr4mice.schema import base_analysis, federated_db
   base_analysis.DataFrame.populate()
   base_analysis.BoxDataFrame()
   base_analysis.OutputPlots.populate()

 # or via run.py
   %run run.py analysis
```

### Additional Configurations
11. The logs can be checked in the logs current folder.

12. *(Optional)* Configure cron jobs for regular populating and menu file generation.
```bash
0 2 * * * bash /mnt/database/auxPipelines-DataJoint_Mathis/vr4mice/cron_script.sh >> ~/vrlogs/cron.log 2>&1

@reboot  bash /mnt/database/auxPipelines-DataJoint_Mathis/vr4mice/cron_script_reboot.sh >> ~/vrlogs/cron.log 2>&1
```

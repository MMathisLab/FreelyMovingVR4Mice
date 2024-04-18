## VR4mice Pipeline
### Key components:
1. Graphical User Interface (GUI) for metadata and data transfer.
2. VR4mice DataJoint pipeline including table definitions, as well as external schemas for experiments and mice.
3. Data fetching and population.
4. System part: docker (docker-compose). Please ensure that *docker-compose* is installed and that the user is added to the Docker group.

### Codebase overview:

1. The `base_schemas/min_base` directory contains minimal **exp** and **mice** schema definitions that are required for correct data fetching and population for the GUI dropdown menu.
2. The `docker/client directory` includes the Dockerfile used to build the client's image in *docker-compose.yml*, which contains the necessary environment for interacting with the DataJoint database. Any new Dockerfiles with specific environments for data analysis should be added here.
3. The `gui_transfer` folder contains all GUI-related information. Only this folder, as well as Python 3 and PyQt5, are needed to build the GUI on the rig computer.
4. The `run` folder includes Bash scripts that can be run directly from the shell to launch a specific action on the database via Docker Compose service. For example, `docker-compose exec app python3 scripts/minimal_run.py`.
5. The `scripts` folder includes all scripts for interacting with the database. Each script always has a database connection part and a scenario to execute, and the simplest script only includes a connection. Scripts can be called via Bash run or via IPython, for example, `%run scripts/minimal_run.py` (assuming IPython is launched in the Docker via `docker-compose exec app ipython`).
6. The `vr4mice` folder contains the core of the pipeline, including **vr4mice** schema (table definitions) and actions (which build the scenarios in scripts).
7. The `Makefile` provides a shortcut for calling commands.
8. The `docker-compose.yml` file contains all Docker definitions, including the database Docker and client. New services can be added if a different configuration is needed. Volumes that correspond to the locations on the drive where all data will be stored are defined here.

![Untitled presentation(4)](https://user-images.githubusercontent.com/43879378/234044336-e7693e02-e8de-4000-9dd0-1716a80002db.jpg)


### Datajoint ERD of vr4mice pipeline:
![vr4mice](https://user-images.githubusercontent.com/43879378/234043578-22b7c8d7-acc9-4f44-9b80-9ec7d25f13f2.png)

### Instructions for Installing and Running the vr4mice pipeline:
#### Rig's GUI installation and run:
1. git clone the "gui_transfer" folder.
2. Ensure that Python 3 and PyQt 5 are installed (a setup file is provided).
3. Navigate to the "gui_transfer" folder and locate the "config.json" file within the "config" folder.
4. Fill in the appropriate paths within the "config.json" file.
5. For Linux, execute the command `make run_gui` from the "gui_transfer" folder to start the GUI.
6. For Windows, adjust the paths in the provided batch file.

#### DataJoint database user remote access via Jupiter Notebook:
1. assuming that jupiter notebook is installed, vr4mice repository is loaded, and base_schemas are pip-installed
2. update information in the `env.py` file (IP of server, user name provided by administrator)
3. from working vr4mice directory start jupiter notebook  and create new Python3 page
4. ```%run env.py``` to load environmental variables
5. ```%run scripts/minimal_run.py connect``` to connect
7. bravo, data can be fetched ```vr4mice.Dataset()``` (relative imports were done in the run script)

#### DataJoint database user remote access: 
similar to [general connection instrunctions](https://github.com/AdaptiveMotorControlLab/auxPipelines-DataJoint_Mathis/blob/mary/vr4mice/README.md#connect-to-database-from-local-host-to-remote-server)
1. Obtain server access and database user credentials from the administrator.
2. To connect to a remote database from a local host, modify the server IP address and user credentials in the "docker-compose" file.\
_Note: make sure that third_party/datajoint-sftp exists in the parent folder (auxPipelines..)\
Note-2: if using minimalistic base_schemas rename base_schemas/min_base to base_schemas/schemas, if using full base_schemas move base_schemas/schemas from current folder to the present one. (This step will be optimized, script is coming)_
3. Build the client service container using the "docker-compose" file and the command `make build_client`.
4. Run the client container to access the remote database using the command `make up_client`.
5. To execute a specific scenario, run the bash script "run/scenario1.sh", which will call the "docker-compose" application and execute the databse-related actions inside the container (actions are organized in the python scripts in the scripts folder).
6. To connect to the DataJoint database, launch "ipython" and execute the minimal script "connect" with the appropriate username and password. 
For example:
`docker-compose app axec ipython3` \
`%run scripts/minimal_run.py connect username pwd` \
`from vr4mice.schema import vr4mice` \
`vr4mice.Dataset()`

## DataJoint database deployment (on server or locally): Setup Instructions

1. Ensure that Docker Compose is installed and that the user is added to the Docker group.
   - Refer to the [Docker installation guide](https://docs.docker.com/engine/install/ubuntu/#install-using-the-repository).
    ```bash
    # Add user to the Docker group
   sudo usermod -aG docker <username>
    ```
2. Download the current repository.
   - Make sure your git key is active. [Learn how to generate a SSH key for git](https://docs.github.com/en/authentication/connecting-to-github-with-ssh/generating-a-new-ssh-key-and-adding-it-to-the-ssh-agent#generating-a-new-ssh-key).
   ```bash
   git clone git@github.com:MMathisLab/FreelyMovingVR4Mice.git
   cd dj_pipeline
   ```
3. Adjust the paths in the shared volumes for the database storage and shared volumes.
   ```bash
   # Create folders if needed to store the data and database
   mkdir -p /path/to/database_directory
   mkdir -p /path/to/data_directory
   # For example: (Attention concerning permissions on /mnt,
   # Run ```sudo chmod 0777 /mnt``` if needed or change the location)
   
   mkdir -p /mnt/database/vr4mice/vr4mice_database/database
   mkdir -p /mnt/database/vr4mice/vr4mice_database/data
   
   # if gui is not used /data/dlc_video /data/data have to be created manually
   mkdir -p /mnt/database/vr4mice/vr4mice_database/data/data/data
   mkdir -p /mnt/database/vr4mice/vr4mice_database/data/data/dlc_video
   
   # if gui is not used: unused
   mkdir -p /shared
   ```
4. To make the database accessible from any machine in the local subnet, change the IP in docker-compose to the server's IP (and choose the port). Find the IP address via `ifconfig`.

##### Building and Running

5. Build the Docker Compose using the command `make build_all` to create the image for the DataJoint database and client container (do not use "sudo"). Note: this command will also start the containers.
   make build_all

6. Add default MySQL credentials to `~/.my.cnf` file:
   ```bash
   [client-vr4mice]
   host=127.0.0.1
   user=root
   password=simple
   port=3309
   ```
   Now you can run `make mysql` to connect to the database from MySQL interface. Here you can create a new user or change the credentials of an existing one.

7. Install base schemas inside the container by running `make base_install` from the host.
   ```make base_install```

##### Remote Access and Testing

8. To connect to the DataJoint database remotely, follow the instructions for local or remote connection provided in the previous section. To connect from the same server under the root account, you can call `make ipython` that will place you in the container's IPython shell.
   ```bash
   %run run.py connect
   # Import some schemas to play with 
   from base_schemas.schemas import exp, mice
   from vr4mice.schema import vr4mice
   vr4mice.Dataset()```
   
9. Test populate:
   Upload some files from GUI(s): .pickle .npy in the `/mnt/database/vr4mice/vr4mice_database/data/data` folder (2 times data) and run:
   Note: place .hdf5, PROC.TS.npy files in `/mnt/database/vr4mice/vr4mice_database/data/data/dlc_video` respectively (/data/dlc_video path for container)
 ```bash
   %run run.py populate
   # Import some schemas and check that Dataset is here
   from base_schemas.schemas import exp, mice
   from vr4mice.schema import vr4mice
   vr4mice.Dataset()
  ```
   Note: if the subfolder name is different (not `/data/data` but `/data/rawdata` for example, change the path in `run.py` script).
   
   Attention: ignore .npy files by now, as it needs some pre-initialisation part for base schemas (don't put .npy in /data/data)

   To populate analysis run:
 ```bash
   from vr4mice.schema import base_analysis, federated_db
   base_analysis.DataFrame.populate()
   base_analysis.BoxDataFrame()
   base_analysis.OutputPlots.populate()

 # or via run.py
   %run run.py analysis
```

##### Additional Configurations

10. The logs can be checked in the logs current folder.

11. *(Optional)* Configure cron jobs for regular populating and menu file generation.

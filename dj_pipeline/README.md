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
4. ```%run env.py``` to load enviromental variables
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

#### DataJoint database deployment (on server or locally):

1. Ensure that Docker Compose is installed and that the user is added to the Docker group.
2. Download the current repository.
3. Adjust the paths in the shared volumes for the database storage and shared volumes.
4. Build the Docker Compose using the command "make build" to create the image for the DataJoint database and client container (do not use "sudo").
5. Modify the root credentials via MySQL and grant user rights via MySQL using the appropriate user-related file (a template is provided in the "mysql_acces" folder).
6. Configure cron jobs for regular populating and menu file generation.
7. To connect to the DataJoint database, follow the instructions for local or remote connection provided in the previous section.


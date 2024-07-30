## Mathis lab VR4Mice datajoint pipeline 

This repository is the code base for VR4Mice pipeline.

`vr4mice` folder contains database's server related code 
   aka datajoin schema's definitions in `schema` subfolder as well as 
  `actions` that describes interactions with the database. It's the core of pipeline: main development of pipeline happens here. 
  `utils` contains all dev-related functions to assume the functionality of pipeline.

`prototype` folder contains system-related files, for example Dockerfile for the client (term "client" applies to any process that addresses to the database and used to keep visible the database-server client-app architecture)

`scripts` folder contains python scripts that execute the sequence of actions to communicate with database (ex. setup-connect-populate). The input can be made via .json config file. Scripts are considered as ephemera scenarios, it's flexible part of the codebase and not the core datajoint pipeline's code.

`Makefile` is here to facilitate the deployment of containers via `make build/up/down` short commands as well as the input of shell-arguments to docker.

`docker-compose.yml` definition of containers used in current system. `docker-compose` approach makes possible to define all needed containers in one place and manage their network: it's helpful to have the overview of all system components and their hierarchy in one place. Every container form `docker-compose`  can be rebuild/restart independently.

## Configure and run:
0. check that mounts in docker-compose.yml corresponds to the desired mounts (ex. video folder)
1. build docker server and client images
```
make build
```
2. runs containers based on just created images
```
make up
```
3. adjust paths in .json config file ex. /video)
run easy scenario that populated video tables from client container 
```
./run.sh
```

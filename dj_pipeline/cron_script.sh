#!/bin/bash

# Change to the directory where your docker-compose.yml file is located
cd /mnt/database/vr4mice/vr4mice_database/FreelyMovingVR4Mice/dj_pipeline

# add git hash
docker-compose up -d client
docker-compose exec -d client bash -c "pip install /base_schemas/ && pip install /base_actions/ && python cron_scenario.py"


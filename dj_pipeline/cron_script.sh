#!/bin/bash

# Change to the directory where your docker-compose.yml file is located
cd /mnt/database/auxPipelines-DataJoint_Mathis/vr_wheels/

# add git hash
docker-compose up -d client
docker-compose exec -d client bash -c "pip install /base_schemas/ && pip install /base_actions/ && python cron_scenario.py"


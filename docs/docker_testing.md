# Running Tests in Docker

This guide explains how to run the pipeline tests inside Docker containers.

## Overview

The test setup uses docker-compose to orchestrate:
- **MySQL 8.0** container for the database
- **Test runner** container built from the pipeline Dockerfile

Tests connect to the external MySQL container instead of using testcontainers,
avoiding Docker-in-Docker complexity.

## Prerequisites

- Docker and docker-compose installed
- Test data in `test_data/golden_dataset/`

## Running All Tests

```bash
cd dj_pipeline
docker-compose -f docker-compose.test.yml up --build --abort-on-container-exit --exit-code-from tests
```

This command:
1. Builds the test container from the Dockerfile
2. Starts MySQL and waits for it to be healthy
3. Runs all unit and integration tests
4. Stops all containers when tests complete
5. Returns the test exit code (for CI integration)

## Running Specific Tests

### Unit tests only
```bash
docker-compose -f docker-compose.test.yml run tests bash -c "cd tests && python -m pytest unit/ -v"
```

### Integration tests only
```bash
docker-compose -f docker-compose.test.yml run tests bash -c "cd tests && python -m pytest integration/ -v"
```

### Single test file
```bash
docker-compose -f docker-compose.test.yml run tests bash -c "cd tests && python -m pytest unit/test_helpers_dj.py -v"
```

## Cleanup

Remove containers and volumes:
```bash
docker-compose -f docker-compose.test.yml down -v
```

## How It Works

The tests use "external MySQL mode" via environment variables:
- `DJ_USE_EXTERNAL_CONTAINERS=1` - bypasses testcontainers
- `DJ_HOST=mysql` - connects to the MySQL service by Docker network name
- `DJ_PORT=3306`, `DJ_USER=root`, `DJ_PASSWORD=simple`

This is implemented in `tests/integration/conftest.py` (lines 133-170).

## Troubleshooting

### Tests fail to connect to MySQL
Wait for MySQL to be fully ready. The healthcheck should handle this, but you can
increase `retries` in docker-compose.test.yml if needed.

### Container build fails
Check that the base image `deeplabcut/deeplabcut:latest-jupyter` is accessible.

### Test data not found
Ensure `test_data/golden_dataset/` exists in the repository root with the
Nightingale test dataset files.

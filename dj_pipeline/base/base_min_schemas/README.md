
# Mathis lab base tables for all datajoint pipelines

The `base_schema` folder is a python package that contains the definition of main schemas (ensemble of tables) that are shared across distinct pipelines. The actual main schemas are `mice` and `exp`.

Main schemas definitions should be the same for all pipelines, so the organization via separate package helps to isolate the code during development and deployment.

## Installation

### From source code

For the development version, clone the repository, and run

```
# for development
pip install -e base_schemas

# for usage
pip install base_schemas
```

Alternatively, the package can be directly installed using (`main` can be replaced by a commit hash or branch):

```
pip install git+ssh://git@github.com/AdaptiveMotorControlLab/auxPipelines-DataJoint_Mathis.git@main#egg=base_schemas\&subdirectory=base_schemas
```

Note that this command will prompt you for a password, so it cannot be used e.g. within a Docker container.

### Building a distribution

To build an installable package (source release or wheel), run

```
make dist
```

which will create the release files in the `dist/` subfolder:

```
dist
dist/base_schemas-0.0.1.tar.gz
dist/base_schemas-0.0.1-py2.py3-none-any.whl
```

The wheel can be directly installed with pip:

```
pip install dist/base_schemas-0.0.1-py2.py3-none-any.whl
```

This workflow is useful when e.g. distributing package versions for use within a Docker container.

## Usage

``` python
from  base_schemas.schemas import mice, exp
print(mice.Mouse())
```


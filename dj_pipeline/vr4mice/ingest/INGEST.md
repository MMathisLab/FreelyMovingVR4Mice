## Ingest VR4Mice datajoint pipeline 

This is a slightly more direct method of populating the main schemas without using the gui.
The schemas are currently vr4mice, dlc, and base_analysis though they might have prefixes in some databases.

Currently the way to access and use this module is the same as the rest of the dj_pipeline/vr4mice modules, which can be found in [README.md](../README.md).

## Usage

An example of using the data_ingest module

```python
from vr4mice.schema import vr4mice
from vr4mice.ingest import data_ingest
from pathlib import Path
from tqdm import tqdm # tqdm is optional

ACTIVE_SENSING_DIR = Path('/storage')
PICKLE_DIR = ACTIVE_SENSING_DIR / 'data'
VIDEO_DIR = ACTIVE_SENSING_DIR / 'videos'

# For ingesting one dataset, specified by dataset name
dataset_name = '30559_2024-02-06_1'
manual_ingest.fill_for(dataset_name, teensy_dir=PICKLE_DIR, videos_dir=VIDEO_DIR, skip_duplicates=True)

# For ingesting/populating all remaining datasets (that aren't in the database yet)
data_ingest.fill_all_in_dir(teensy_dir=PICKLE_DIR, videos_dir=VIDEO_DIR, tqdm=tqdm, ignore_errors=True, skip_duplicates=True)
```

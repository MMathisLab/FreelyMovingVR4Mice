from typing import List
import datajoint as dj

# FreelyMovingVR4Mice to DataJoint utils

# reads in data using the datajoint table headings


def autofill_table(table: dj.Table, data: dict, **dj_kwargs):
    """
    Pulls relevant keys (which could be a subset of the dict), found using the table heading, from a data dict.

    table: DataJoint table to insert into
    data: dictionary of fields (field_name=field_data pairs) of which
        a subset from the dictionary will be used
    pop: If True, will pop the relevant fields from the dictionary (default: False)
    **dj_kwargs: Will be passed directly to the table.insert1(..., **dj_kwargs) call
        If `allow_direct_insert` is not supplied here, it will default to True.
    """
    # enable support for filling computed tables by default
    if "allow_direct_insert" not in dj_kwargs:
        dj_kwargs["allow_direct_insert"] = True

    # read field attributes from heading
    attributes = table.heading.attributes
    data_subset = {}
    for field in attributes.keys():
        data_subset[field] = data[field]
    table.insert1(data_subset, **dj_kwargs)


def fill_tables_from_dict(tables: List[dj.Table], data: dict, **dj_kwargs):
    for table in tables:
        autofill_table(table=table, data=data, **dj_kwargs)

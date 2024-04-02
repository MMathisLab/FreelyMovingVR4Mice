"""

    Template for keys2tables file related to the random schema

"""

local_def = {
    'attributeB': functionB,
    'attributeY': no_value_function,
}

table1 = [
    'attributeX',
    'attributeY',
]

table2 = [
    'attributeA',
    'attributeB',
]

tables = {
    "Table1": table1,
    "Table2": table2,
}

dj_tables = {
    "TableName": schema_name.TableName(),
}

transformer = {
    "dj_attribute_name": "raw_data_name",
}
"""
    obligatory fields:
    
    "tables": link to "tables" dictionary; 
        every table contains all attributes to populate according to the datajoint table definition for the given table;
         should be in the order of population, check dependencies via primary keys in database tables definitions.
    "dj_tables": link to "dj_tables" dictionary
        contains the datajoint table object schema_name.TableName()
    "local_def": link to "local_def" dictionary
        contains function definition 
        if attribute needs special definition or
        additional processing/checks of raw data before be added to database;
        functions should be defined in the additional file
    "transformer": link to "transformer" dictionary
        associate the names of raw data keys with attribute's names in database (if mismatch)
        
"""

base = {
    "tables": tables,
    "dj_tables": dj_tables,
    "local_def": local_def,
    "transformer": transformer
}

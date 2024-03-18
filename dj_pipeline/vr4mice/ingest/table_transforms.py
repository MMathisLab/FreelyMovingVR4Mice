"""
Manual ingest into the FreelyMovingVR4Mice pipeline.
"""

from vr4mice.schema import vr4mice, dlc, base_analysis
from vr4mice.ingest.data_loading import TeensyData

# Tables to fill with data
fill_tables = {
    vr4mice: [
        # "Camera", # Lookup table
        "Dataset",
        "VR4Mice",
        "Video",
        # "ModelName", # Lookup table
        "DLC",
        "MouseState",
        "State",
        "Metadata",
        "Box",
    ],
    dlc: [
        "VideoToAnalyze",
        # "ModelName", # Lookup table
        "DLC",
        # "DLCProcessor", # Should be filled via populate, but we have the PROC (DLC Processor) file
        # "DLCKeypoints", # Should be filled via populate, but should be fillable from the DLC hdf5 file
    ],
    # base_analysis: [  # Might have to skip base_analysis for now
    #     "DataFrame",
    #     "BoxDataFrame",
    #     # "OutputPlots", # This has a primary key that is a blob, might be a newer datajoint version thing
    # ],
}

# this should have the autofill take priority for the keys from this data source, but still look for any missing keys from the original source
data_nesting = {
    vr4mice: {
        "MouseState": TeensyData.export_mouse_state,  # flattening data for only this table, otherwise we have key naming conflicts
    },
    dlc: {},
    base_analysis: {},
}

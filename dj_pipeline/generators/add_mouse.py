import pathlib
from PIL import Image
import shutil
import datetime
from random import choice, randint
import datajoint as dj

from base_schemas.schemas import mice

# Sample data for the mouse info
mouse_data = {
    "mouse_name": "Testmouse",
    "mouse_id": 999,  # Unique mouse ID; adjust if necessary to avoid conflicts, start from big number if external
    "dob": datetime.date(2022, 3, 15), # date of birth
    "sex": choice(["M", "F"]),
    "strain": "WT",  # Assuming "WT" strain exists in Strain table contents
}

# Example
surgery_types = ["injection craniotomy", "7 mm craniotomy", "optical fibers"]

surgery_data = {
        "mouse_name": "Testmouse",
        "surgery_type": "7 mm craniotomy",
        "surgery_details": "Initial surgery for imaging access",
        "surgery_date": "2022-05-01",
}
# Note: modify populate_surgery_image too

def populate_mouse():
    try:
        mice.Mouse.insert1(mouse_data)
    except dj.errors.DuplicateError:
        print(f"Mouse {mouse_data} already exists.")

def populate_surgery_type():
    for s_type in surgery_types:
        mice.SurgeryType.insert1({"surgery_type": s_type}, skip_duplicates=True)

def populate_surgery():
    mice.Surgery.insert1(surgery_data, skip_duplicates=True)

def create_fake_paths(
    folder="/tmp/data/rawdata/surgery_images", fpath="fake_image.png"
):
    surgery_images_path = pathlib.Path(folder)
    fake_image_path = surgery_images_path / fpath

    if not surgery_images_path.exists():
        surgery_images_path.mkdir(parents=True, exist_ok=True)
        temp_directory_created = True
    else:
        temp_directory_created = False

    if not fake_image_path.exists():
        image = Image.new("RGB", (100, 100), color="gray")
        image.save(fake_image_path)
        fake_image_created = True
    else:
        fake_image_created = False
    return fake_image_path, surgery_images_path


def populate_surgery_image():
    fake_image_path, fake_folder = create_fake_paths()
    surgery_image_data = {
        "mouse_name": "Testmouse",
        "surgery_type": "7 mm craniotomy",
        "surgery_image": fake_image_path,
    }
    mice.SurgeryImage.insert1(
        surgery_image_data, allow_direct_insert=True, skip_duplicates=True
    )

    fake_image_path.unlink()
    shutil.rmtree(fake_folder)


# Main function to execute all population steps
def populate_all():
    populate_mouse()
    #populate_surgery_type()
    #populate_surgery()
    #populate_surgery_image()


# Execute the population process
populate_all()

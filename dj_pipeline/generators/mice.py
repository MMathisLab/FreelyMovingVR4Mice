import datetime
from base_schemas.schemas import mice

def insert_mice():
    mouse_entries = [
        {"mouse_name": "31436", "mouse_id": 31436, "dob": datetime.date(2024, 3, 5), "sex": "M", "strain": "WT"},
        {"mouse_name": "31437", "mouse_id": 31437, "dob": datetime.date(2024, 3, 5), "sex": "M", "strain": "WT"},
        {"mouse_name": "31438", "mouse_id": 31438, "dob": datetime.date(2024, 3, 5), "sex": "M", "strain": "WT"},
        {"mouse_name": "31537", "mouse_id": 31537, "dob": datetime.date(2024, 5, 21), "sex": "F", "strain": "WT"},
        {"mouse_name": "31538", "mouse_id": 31538, "dob": datetime.date(2024, 5, 21), "sex": "F", "strain": "WT"},
        {"mouse_name": "31539", "mouse_id": 31539, "dob": datetime.date(2024, 5, 21), "sex": "F", "strain": "WT"},
        {"mouse_name": "31475", "mouse_id": 31475, "dob": datetime.date(2024, 7, 1), "sex": "M", "strain": "WT"},
        {"mouse_name": "31476", "mouse_id": 31476, "dob": datetime.date(2024, 7, 1), "sex": "M", "strain": "WT"},
    ]

    for mouse in mouse_entries:
        try:
            mice.Mouse().insert1(mouse)
            print(f"Inserted mouse {mouse['mouse_name']} successfully.")
        except Exception as e:
            print(f"Error inserting mouse {mouse['mouse_name']}: {e}")

if __name__ == "__main__":
    insert_mice()


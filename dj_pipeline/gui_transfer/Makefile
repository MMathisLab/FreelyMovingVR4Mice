export config_path := default
export config_name := config.json

env:
	pip install "PyQt5" "numpy" "moviepy>=1.0.3"

run_gui:
	python3 main.py

test:
	cd ../../tests && python -m pytest unit/test_gui_transfer.py -v


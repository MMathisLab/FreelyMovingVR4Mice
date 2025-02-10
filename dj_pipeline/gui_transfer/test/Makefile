run_gui:
	@export config_path=test/test_config.json && \
	export config_name=test_config.json && \
	cd .. && python3 main.py && \
	echo $$config_name

BASE_DIR=/tmp/vr4mice_test_gui

dirs = \
	$(BASE_DIR)/remote \
	$(BASE_DIR)/remote/data \
	$(BASE_DIR)/dlc_output \
	$(BASE_DIR)/remote/dlc_video \
	$(BASE_DIR)/dlc_video_raw \
	$(BASE_DIR)/processed_rig
	#$(BASE_DIR)/raw

files = \
	$(BASE_DIR)/dlc_video_raw/Testmouse_2023-02-22_2.pickle \
	$(BASE_DIR)/dlc_video_raw/Testmouse_2023-02-22_2_TS.npy \
	$(BASE_DIR)/dlc_video_raw/Imagingsource_Testmouse_2023-02-22_2_DLC.hdf5 \
	$(BASE_DIR)/dlc_video_raw/Imagingsource_Testmouse_2023-02-22_2_PROC \
	$(BASE_DIR)/dlc_video_raw/Imagingsource_Testmouse_2023-02-22_2_VIDEO.mp4 \

all: $(dirs) $(files)

$(dirs):
	mkdir -p $@

build_tree: | $(dirs)
	touch $(files)

menu:
	python create_menu.py

config:
	python create_config.py
clean:
	rm -rf $(BASE_DIR)


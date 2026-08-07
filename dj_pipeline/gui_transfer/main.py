import sys

from PyQt5.QtWidgets import QApplication

from config.config import config, logger
from gui import Gui
from modules.exp import Exp
from modules.mouse import Mouse
from modules.opto import Opto
from modules.transfer import Transfer
from utils.utils import load_dj_input

if __name__ == "__main__":

    ok, message = config.validate()
    if not ok:
        logger.warning(message)
        sys.exit(1)

    menu = config.get_menu_path
    if menu is False:
        sys.exit()

    dj_dict, date, json_dict = load_dj_input(
        path_dj_data=menu, path_json=config.get_cache_file_path
    )

    app = QApplication(sys.argv)
    elms = dict()

    # create main main gui window
    main_window = Gui()

    # create components
    test_version = False
    if not test_version:
        mouse = Mouse(main_window)
        exp = Exp(dj_dict, main_window)
        opto = Opto(dj_dict, main_window)
        transfer = Transfer(main_window)
        dj_elms = {
            mouse.get_nick(): mouse,
            exp.get_nick(): exp,
            opto.get_nick(): opto,
        }
        sys_elms = {transfer.get_nick(): transfer}
        # start to run (in order of appearance)

        for v in dj_elms.values():
            v.run(dj_dict, json_dict, date)

        transfer.run(dj_dict, dj_elms)
        elms = {**dj_elms, **sys_elms}

    main_window.run(elms)

    main_window.show()

    # from utils import read_npy
    # read_npy()

    sys.exit(app.exec_())

import os
from terrascript import function


def get_user_data_script():
    function.file(os.path.join(os.path.dirname(__file__), "scripts", "install-docker-ce.sh"))

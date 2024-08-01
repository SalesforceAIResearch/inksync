from datetime import datetime
from colorama import Fore
import sys, os

# Printing related business
class DoublePrint(object):
    def __init__(self, name=None, show_timings=False):
        if name is None:
            filename = "%s.log" % (sys.argv[0].split("/")[-1].split(".")[0])
            file_folder = "/".join(sys.argv[0].split("/")[:-1])
            log_folder = os.path.join(file_folder, "logs")
            # Create folder if it doesn't exist:
            if not os.path.exists(log_folder):
                os.makedirs(log_folder)
            name = os.path.join(log_folder, filename)

        self.file = open(name, "a")
        self.stdout = sys.stdout
        self.stderr = sys.stderr
        self.show_timings = show_timings
        sys.stderr = self
        sys.stdout = self

    def __del__(self):
        sys.stdout = self.stdout
        sys.stderr = self.stderr
        self.file.close()

    def write(self, data):
        if self.show_timings:
            data = str(data)
            if len(data.strip()) > 0:
                data = Fore.LIGHTBLUE_EX+"["+datetime.now().strftime("%Y-%m-%d %H:%M:%S")+"] " +Fore.RESET+data

        self.file.write(data)
        self.stdout.write(data)
        self.file.flush()

    def flush(self):
        self.file.flush()

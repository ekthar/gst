import sys

from gst_hsn_tool.cli import main as cli_main
from gst_hsn_tool.gui import main as gui_main


if __name__ == "__main__":
    if len(sys.argv) > 1:
        cli_main()
    else:
        gui_main()

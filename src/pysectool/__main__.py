"""支持 python -m pysectool 运行。"""

import sys

from pysectool.cli import main

if __name__ == "__main__":
    sys.exit(main())

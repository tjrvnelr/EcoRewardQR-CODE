import importlib.util
from pathlib import Path


module_path = Path(__file__).with_name("EcoRewardQR-CODE.py")
spec = importlib.util.spec_from_file_location("ecorewardqr_code", module_path)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)

app = module.app

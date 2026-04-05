"""
PyInstaller runtime hook to prevent pyarrow import errors.
"""
import sys
import types

_fake = types.ModuleType('pyarrow')
_fake.__version__ = '0.0.0'
_fake.__path__ = []
_fake.HAS_PYARROW = False

sys.modules['pyarrow'] = _fake
sys.modules['pyarrow.lib'] = _fake
sys.modules['pandas.compat.pyarrow'] = _fake
sys.modules['pandas.io.parquet'] = _fake
sys.modules['pandas.io.feather'] = _fake

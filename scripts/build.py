from pathlib import Path
import shutil
root = Path(__file__).resolve().parents[1]
shutil.rmtree(root / 'dist', ignore_errors=True)
shutil.copytree(root / 'src', root / 'dist')
print('Static export: dist/')

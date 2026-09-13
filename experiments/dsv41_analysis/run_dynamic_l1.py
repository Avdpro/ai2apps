"""Compatibility entry: dynamic L1 is now the default in the main MLX runner."""
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'dsv41_mlx'))
from run import main
if __name__=='__main__':main()

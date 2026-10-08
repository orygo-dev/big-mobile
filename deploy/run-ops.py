import argparse, os, runpy, sys
from pathlib import Path
from dotenv import dotenv_values

parser=argparse.ArgumentParser()
parser.add_argument('--env',action='append',required=True)
parser.add_argument('command',choices=['monitor','backup'])
arguments,remaining=parser.parse_known_args()
for filename in arguments.env:
    path=Path(filename)
    if os.name!='nt' and path.stat().st_mode & 0o077: raise RuntimeError('Ops env files must have permissions 0600')
    os.environ.update({key:value for key,value in dotenv_values(path).items() if value is not None})
sys.argv=[arguments.command,*remaining]
runpy.run_path(str(Path(__file__).parent/(arguments.command+'.py')),run_name='__main__')

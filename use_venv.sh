

make venv
. .env/bin/activate

export PYTHONPATH=$PWD
alias virt-deploy="python $PWD/qdeploy/main.py"

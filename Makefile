
VENV=.env
MAIN=./qdeploy/main.py
TARGET=virt-deploy


all::standalone

venv: ${VENV}

${VENV}: requirements.txt
	test -d ${VENV} || virtualenv ${VENV}
	. ${VENV}/bin/activate; 				\
	pip install -r requirements.txt

standalone:: ${VENV}
	. ${VENV}/bin/activate; 				\
	PYTHONPATH=$(PYTHONPATH) pyinstaller --name $(TARGET) --onefile $(MAIN) \
		--add-data './resources:/resources'

clean:
	- rm -rf build dist *.spec ${VENV}

.PHONY: standalone clean venv all

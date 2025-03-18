install:
	python -m venv venv
	source venv/bin/activate && pip install -r requirements.txt --use-pep517

run:
	source venv/bin/activate && cd EagleOps_Peer_Eval && python manage.py runserver

migrate:
	source venv/bin/activate && cd EagleOps_Peer_Eval && python manage.py migrate

python -m venv .venv
.venv\\Scripts\\activate
pip install -r requirements.txt



docker-compose down --remove-orphans && docker system prune -f && docker-compose build --no-cache && docker-compose up -d
docker-compose down --remove-orphans; docker system prune -f; docker-compose build --no-cache; docker-compose up -d
up:
	docker-compose up -d

down:
	docker-compose down

run: down
	docker-compose run --rm --service-ports web

build: down
	docker-compose build

logs:
	docker-compose logs -f --tail=40


.PHONY: all clean fclean re

all:
	docker compose up --build -d

clean:
	docker compose down

fclean:
	docker compose down --rmi local --volumes --remove-orphans
	docker system prune -f

re: fclean all


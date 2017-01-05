.PHONY: test
test:
	py.test --cov=app

.PHONY: test-buildcov
test-buildcov:
	py.test --cov=app && (echo "building coverage html, view at './htmlcov/index.html'"; coverage html)

{% if database.is_pg_sqlalchemy %}
.PHONY: reset-database
reset-database:
	python -c "from app.management import prepare_database; prepare_database(True)"
{% endif %}

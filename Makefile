.PHONY: install index search app clean

install:
	pip install -r requirements.txt

index:
	python scripts/build_index.py

index-force:
	python scripts/build_index.py --force

search:
	@read -p "Query: " q; python scripts/search.py "$$q"

app:
	streamlit run app.py

clean:
	rm -rf data/vectorstore/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

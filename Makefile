.PHONY: install fetch-docs fetch-docs-force fetch-docs-dry well-profiles well-profiles-local index index-force search app clean

install:
	pip install -r requirements.txt

# Baixa documentos do repositorio petrobras/3W (incremental — pula arquivos ja existentes)
fetch-docs:
	python scripts/fetch_docs.py

# Re-baixa todos os documentos, mesmo os ja existentes
fetch-docs-force:
	python scripts/fetch_docs.py --force

# Lista documentos disponiveis sem efetuar download
fetch-docs-dry:
	python scripts/fetch_docs.py --dry-run

# Gera perfis de completude de sensores por poco via GitHub (classes 0,2,3,4,5,8)
well-profiles:
	python scripts/generate_well_profiles.py --source github --classes 0 2 3 4 5 8

# Gera perfis a partir de parquets ja baixados localmente
# Uso: make well-profiles-local DATASET_PATH=/caminho/para/3W/dataset
well-profiles-local:
	python scripts/generate_well_profiles.py --source local --path $(DATASET_PATH)

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

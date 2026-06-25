"""
PetroRAG — Busca Semântica & IA para Documentação de Poços Offshore
====================================================================
Streamlit app com 3 abas:
  1. Busca Semântica — top-K chunks relevantes com score de similaridade
  2. Perguntas & Respostas (RAG) — resposta gerada pelo LLM com fontes citadas
  3. Gerenciar Documentos — upload e reindexação

Início rápido:
    streamlit run app.py
"""
import logging
import sys
from pathlib import Path

import streamlit as st

# Garantir que src/ está no path
sys.path.insert(0, str(Path(__file__).parent))

from config import APP_TITLE, RAW_DIR, VECTORSTORE_DIR, LLM_PROVIDER, OLLAMA_MODEL, OPENAI_MODEL
from src.utils import setup_logging, format_source, validate_data_dir
from src.indexer import build_index
from src.retriever import semantic_search
from src.rag import build_rag_chain, answer

setup_logging("WARNING")
logger = logging.getLogger(__name__)

# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="PetroRAG",
    page_icon="🛢️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS ───────────────────────────────────────────────────────────────────────
st.markdown("""
<style>
.result-card {
    background: #f8f9fa;
    border-left: 4px solid #007AC3;
    padding: 12px 16px;
    border-radius: 4px;
    margin-bottom: 10px;
}
.score-badge {
    background: #007AC3;
    color: white;
    padding: 2px 8px;
    border-radius: 12px;
    font-size: 0.8em;
    font-weight: bold;
}
.source-tag {
    color: #666;
    font-size: 0.85em;
    font-style: italic;
}
</style>
""", unsafe_allow_html=True)

# ── Header ────────────────────────────────────────────────────────────────────
st.title(APP_TITLE)
st.caption("Powered by sentence-transformers · FAISS · LangChain · Petrobras 3W")
st.divider()

# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.header("⚙️ Configurações")
    top_k = st.slider("Top-K resultados", min_value=1, max_value=10, value=5)

    llm_label = f"{LLM_PROVIDER.upper()} / {OLLAMA_MODEL if LLM_PROVIDER == 'ollama' else OPENAI_MODEL}"
    st.info(f"**LLM:** {llm_label}")
    st.info(f"**Documentos:** {RAW_DIR}")

    st.divider()
    if st.button("🔄 Reindexar documentos", use_container_width=True):
        with st.spinner("Reindexando..."):
            try:
                st.session_state.pop("vectorstore", None)
                st.session_state.pop("rag_chain", None)
                build_index(force=True)
                st.success("Índice reconstruído com sucesso!")
            except Exception as e:
                st.error(f"Erro: {e}")

# ── Carregar índice (cache na session) ────────────────────────────────────────
@st.cache_resource(show_spinner="Carregando índice semântico...")
def load_vectorstore():
    if not validate_data_dir(RAW_DIR):
        return None
    return build_index()

vectorstore = load_vectorstore()

if vectorstore is None:
    st.warning(
        "⚠️ Nenhum documento indexado. Acesse a aba **Gerenciar Documentos** "
        "para fazer upload de PDFs ou arquivos TXT."
    )

# ── Abas ─────────────────────────────────────────────────────────────────────
tab_search, tab_rag, tab_docs = st.tabs([
    "🔍 Busca Semântica",
    "🤖 Perguntas & Respostas (RAG)",
    "📂 Gerenciar Documentos",
])

# ════════════════════════════════════════════════════════════════════════════
# ABA 1 — Busca Semântica
# ════════════════════════════════════════════════════════════════════════════
with tab_search:
    st.subheader("Busca Semântica por Similaridade")
    st.caption(
        "Encontra os trechos mais semanticamente próximos da sua query, "
        "mesmo usando palavras diferentes do texto original."
    )

    query = st.text_input(
        "Query",
        placeholder="Ex: fechamento espúrio da válvula de segurança de fundo DHSV",
        key="search_query",
    )

    col1, col2 = st.columns([1, 4])
    search_btn = col1.button("🔍 Buscar", type="primary", use_container_width=True)

    if search_btn and query:
        if vectorstore is None:
            st.error("Indexe documentos primeiro.")
        else:
            with st.spinner("Buscando..."):
                results = semantic_search(vectorstore, query, k=top_k)

            if not results:
                st.info("Nenhum resultado encontrado.")
            else:
                st.success(f"{len(results)} trechos relevantes encontrados")
                for i, r in enumerate(results, 1):
                    similarity_pct = max(0, (1 - r.score) * 100) if r.score > 0 else (1 / (1 + r.score)) * 100
                    source_label = format_source(r.source, r.page)
                    st.markdown(f"""
<div class="result-card">
<b>#{i}</b>&nbsp;&nbsp;
<span class="score-badge">sim {similarity_pct:.1f}%</span>
&nbsp;&nbsp;<span class="source-tag">📄 {source_label}</span>
<br><br>{r.content}
</div>""", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════════════════════
# ABA 2 — RAG
# ════════════════════════════════════════════════════════════════════════════
with tab_rag:
    st.subheader("Perguntas & Respostas com IA Generativa")
    st.caption(
        "O modelo recupera os trechos mais relevantes e usa um LLM para gerar "
        "uma resposta contextualizada, citando as fontes."
    )

    # Exemplos rápidos
    st.markdown("**Exemplos de perguntas:**")
    examples = [
        "O que é o evento DHSV Closure e quais sensores indicam esse evento?",
        "Como o pipeline ETL processa os dados da camada Bronze para a Gold?",
        "Qual sensor tem maior importância SHAP na classificação de eventos?",
        "Como funciona o ajuste de thresholds para classes desbalanceadas?",
    ]
    cols = st.columns(2)
    for i, ex in enumerate(examples):
        if cols[i % 2].button(f"💬 {ex[:55]}...", key=f"ex_{i}", use_container_width=True):
            st.session_state["rag_question"] = ex

    question = st.text_area(
        "Sua pergunta",
        value=st.session_state.get("rag_question", ""),
        height=80,
        key="rag_question_input",
        placeholder="Faça uma pergunta técnica sobre os documentos indexados...",
    )

    ask_btn = st.button("🤖 Gerar resposta", type="primary")

    if ask_btn and question:
        if vectorstore is None:
            st.error("Indexe documentos primeiro.")
        else:
            with st.spinner(f"Gerando resposta via {llm_label}..."):
                try:
                    if "rag_chain" not in st.session_state:
                        st.session_state["rag_chain"] = build_rag_chain(vectorstore)
                    chain = st.session_state["rag_chain"]
                    resp = answer(chain, question)
                    st.markdown("### 📝 Resposta")
                    st.markdown(resp["result"])
                    if resp["sources"]:
                        st.divider()
                        st.markdown("**📚 Fontes consultadas:**")
                        for src in resp["sources"]:
                            st.markdown(f"- `{Path(src).name}`")
                except Exception as e:
                    st.error(f"Erro ao gerar resposta: {e}")
                    if "ollama" in LLM_PROVIDER.lower():
                        st.info("💡 Verifique se o Ollama está rodando: `ollama serve`")

# ════════════════════════════════════════════════════════════════════════════
# ABA 3 — Gerenciar Documentos
# ════════════════════════════════════════════════════════════════════════════
with tab_docs:
    st.subheader("Gerenciar Documentos Indexados")

    col_upload, col_list = st.columns([1, 1])

    with col_upload:
        st.markdown("**📤 Upload de novos documentos**")
        uploaded = st.file_uploader(
            "Arraste PDFs ou arquivos TXT",
            type=["pdf", "txt"],
            accept_multiple_files=True,
        )
        if uploaded and st.button("💾 Salvar e reindexar", type="primary"):
            RAW_DIR.mkdir(parents=True, exist_ok=True)
            for f in uploaded:
                dest = RAW_DIR / f.name
                dest.write_bytes(f.read())
                st.success(f"✅ {f.name} salvo")
            with st.spinner("Reindexando..."):
                st.cache_resource.clear()
                build_index(force=True)
            st.success("Índice atualizado! Recarregue a página.")

    with col_list:
        st.markdown("**📋 Documentos no índice**")
        files = list(RAW_DIR.rglob("*.pdf")) + list(RAW_DIR.rglob("*.txt"))
        if files:
            for f in sorted(files):
                size_kb = f.stat().st_size // 1024
                st.markdown(f"- `{f.name}` ({size_kb} KB)")
        else:
            st.info("Nenhum documento indexado ainda.")

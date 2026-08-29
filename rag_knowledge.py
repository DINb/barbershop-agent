"""
rag_knowledge.py
-----------------
RAG leve baseado em TF-IDF (sem dependências pesadas de vetor DB), no mesmo
espírito do oic-fusion-incident-agent: transforma o JSON de serviços da
barbearia em "documentos" pesquisáveis, para o agente responder perguntas
como "quanto custa a barba?" ou "vocês abrem domingo?" sem precisar de uma
chamada de tool separada para cada pergunta.
"""

import json
import math
import os
import re
from collections import Counter

DATA_DIR = os.path.join(os.path.dirname(__file__), "data")
SERVICES_FILE = os.path.join(DATA_DIR, "services.json")


def _tokenize(text: str):
    return re.findall(r"[a-zà-úçã-õ0-9]+", text.lower())


class TfidfIndex:
    def __init__(self, documents: list):
        """documents: lista de dicts {"id": ..., "text": ...}"""
        self.documents = documents
        self.doc_tokens = [_tokenize(d["text"]) for d in documents]
        self.df = Counter()
        for tokens in self.doc_tokens:
            for term in set(tokens):
                self.df[term] += 1
        self.n_docs = len(documents)

    def _idf(self, term):
        return math.log((1 + self.n_docs) / (1 + self.df.get(term, 0))) + 1

    def _tfidf_vector(self, tokens):
        tf = Counter(tokens)
        return {term: (count / len(tokens)) * self._idf(term) for term, count in tf.items()}

    @staticmethod
    def _cosine(vec_a: dict, vec_b: dict):
        common = set(vec_a) & set(vec_b)
        numerator = sum(vec_a[t] * vec_b[t] for t in common)
        norm_a = math.sqrt(sum(v * v for v in vec_a.values())) or 1e-9
        norm_b = math.sqrt(sum(v * v for v in vec_b.values())) or 1e-9
        return numerator / (norm_a * norm_b)

    def search(self, query: str, top_k: int = 2):
        query_vec = self._tfidf_vector(_tokenize(query))
        scored = []
        for doc, tokens in zip(self.documents, self.doc_tokens):
            doc_vec = self._tfidf_vector(tokens)
            score = self._cosine(query_vec, doc_vec)
            scored.append((score, doc))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [doc for score, doc in scored[:top_k] if score > 0]


def build_knowledge_base() -> TfidfIndex:
    with open(SERVICES_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    documents = []
    for s in data["servicos"]:
        text = f"{s['nome']}. {s['descricao']} Preço: R${s['preco']:.2f}. Duração: {s['duracao_min']} minutos."
        documents.append({"id": s["id"], "text": text, "tipo": "servico"})

    horarios = data["horario_funcionamento"]
    dias_abertos = ", ".join(f"{dia}: {h}" for dia, h in horarios.items() if h)
    dias_fechados = ", ".join(dia for dia, h in horarios.items() if not h)
    documents.append({
        "id": "horario_funcionamento",
        "text": f"Horário de funcionamento da barbearia. Dias abertos: {dias_abertos}. Fechado: {dias_fechados}.",
        "tipo": "horario",
    })

    barbeiros = ", ".join(b["nome"] for b in data["barbeiros"])
    documents.append({
        "id": "barbeiros",
        "text": f"Barbeiros disponíveis na equipe: {barbeiros}.",
        "tipo": "equipe",
    })

    return TfidfIndex(documents)

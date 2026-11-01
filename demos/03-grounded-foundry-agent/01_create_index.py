"""Build the ``hbl-site-knowledge`` index in Azure AI Search from the eight knowledge documents.

Steps: define the index (keyword + vector + semantic), chunk each Markdown document by section (one chunk per
``##`` section, longer ones split at ~800 characters with overlap; every chunk carries its heading and the
document's "not legal advice" note), embed the chunks with the Foundry project's embedding deployment, upload.

Auth: DefaultAzureCredential (Entra ID). The signed-in identity needs on the search service:
  * Search Service Contributor   - create/update the index definition
  * Search Index Data Contributor - upload documents
and on the Foundry resource: Cognitive Services OpenAI User (to call the embedding model).
For hybrid/vector queries from the agent's AI Search tool, the index carries an Azure OpenAI vectorizer; the
search service's managed identity then also needs Cognitive Services OpenAI User on the Foundry resource.

Usage: python 01_create_index.py [--recreate] [--no-vectorizer]
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
from pathlib import Path
from typing import Iterable

import _shared  # noqa: F401
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient
from azure.search.documents.indexes.models import (
    AzureOpenAIVectorizer,
    AzureOpenAIVectorizerParameters,
    HnswAlgorithmConfiguration,
    HnswParameters,
    SearchField,
    SearchFieldDataType,
    SearchIndex,
    SemanticConfiguration,
    SemanticField,
    SemanticPrioritizedFields,
    SemanticSearch,
    VectorSearch,
    VectorSearchAlgorithmMetric,
    VectorSearchProfile,
)
from foundry_util import load_env
from openai import OpenAI

KNOWLEDGE_DIR = Path(__file__).resolve().parents[1] / "00-shared" / "data" / "knowledge"
CHUNK_CHARS = 800
CHUNK_OVERLAP = 120
SEMANTIC_CONFIG = "hbl-semantic"
VECTOR_PROFILE = "hbl-hnsw-profile"
VECTORIZER = "hbl-aoai-vectorizer"


def build_index(name: str, dimensions: int, vectorizer: AzureOpenAIVectorizer | None) -> SearchIndex:
    """Index schema: id, title, source, content, chunk_id, content_vector + semantic config + HNSW profile."""
    fields = [
        SearchField(name="id", type=SearchFieldDataType.String, key=True, filterable=True),
        SearchField(name="title", type=SearchFieldDataType.String, searchable=True, filterable=True, facetable=True),
        SearchField(name="source", type=SearchFieldDataType.String, filterable=True, facetable=True),
        SearchField(name="content", type=SearchFieldDataType.String, searchable=True, analyzer_name="en.microsoft"),
        SearchField(name="chunk_id", type=SearchFieldDataType.Int32, filterable=True, sortable=True),
        SearchField(
            name="content_vector",
            type=SearchFieldDataType.Collection(SearchFieldDataType.Single),
            searchable=True,
            stored=False,
            vector_search_dimensions=dimensions,
            vector_search_profile_name=VECTOR_PROFILE,
        ),
    ]
    vector_search = VectorSearch(
        algorithms=[
            HnswAlgorithmConfiguration(
                name="hbl-hnsw",
                parameters=HnswParameters(m=4, ef_construction=400, ef_search=500, metric=VectorSearchAlgorithmMetric.COSINE),
            )
        ],
        profiles=[
            VectorSearchProfile(
                name=VECTOR_PROFILE,
                algorithm_configuration_name="hbl-hnsw",
                vectorizer_name=vectorizer.vectorizer_name if vectorizer else None,
            )
        ],
        vectorizers=[vectorizer] if vectorizer else None,
    )
    semantic = SemanticSearch(
        default_configuration_name=SEMANTIC_CONFIG,
        configurations=[
            SemanticConfiguration(
                name=SEMANTIC_CONFIG,
                prioritized_fields=SemanticPrioritizedFields(
                    title_field=SemanticField(field_name="title"),
                    content_fields=[SemanticField(field_name="content")],
                ),
            )
        ],
    )
    return SearchIndex(name=name, fields=fields, vector_search=vector_search, semantic_search=semantic)


def foundry_openai_url(project_endpoint: str) -> str:
    """``https://<account>.openai.azure.com`` from the project endpoint.

    Verified live (16 Oct 2026): the project's ``/openai/v1`` route serves chat but returns 404 for embeddings, and the
    AI Search vectorizer expects the Azure OpenAI host, so both use the account's OpenAI endpoint. Override with
    ``AZURE_OPENAI_ENDPOINT``."""
    explicit = os.environ.get("AZURE_OPENAI_ENDPOINT")
    if explicit:
        return explicit.rstrip("/")
    account = re.sub(r"^https?://", "", project_endpoint).split(".")[0]
    return f"https://{account}.openai.azure.com"


def chunk_text(text: str, size: int = CHUNK_CHARS, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Paragraph-aware chunks of roughly ``size`` characters; each new chunk repeats the last ``overlap``
    characters of the previous one, starting at a word boundary."""
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    chunks: list[str] = []
    current = ""
    for para in paragraphs:
        if current and len(current) + len(para) + 2 > size:
            chunks.append(current)
            current = current[-overlap:].split(" ", 1)[-1] + "\n\n" + para if overlap else para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        chunks.append(current)
    return chunks


def chunk_document(text: str) -> list[str]:
    """One chunk per ``##`` section (long sections split by ``chunk_text``), each carrying its section heading and
    the document's own provenance note, so any passage the agent retrieves says where it comes from and that it is
    simplified guidance."""
    note = ""
    sections: list[tuple[str, list[str]]] = []
    for line in text.splitlines():
        if line.startswith("# "):
            continue
        if line.startswith("> ") and not note:
            note = re.sub(r"\*\*", "", line[2:]).strip()
            continue
        if line.startswith("## "):
            sections.append((line[3:].strip(), []))
        elif sections:
            sections[-1][1].append(line)
    chunks: list[str] = []
    for heading, lines in sections:
        for part in chunk_text("\n".join(lines).strip()):
            chunks.append(f"{note}\n\n## {heading}\n\n{part}" if note else f"## {heading}\n\n{part}")
    return chunks


def read_documents() -> Iterable[tuple[str, str, str]]:
    """(source filename, H1 title, full text) for each knowledge document."""
    for path in sorted(KNOWLEDGE_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        title = next((l[2:].strip() for l in text.splitlines() if l.startswith("# ")), path.stem)
        yield path.name, title, text


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--recreate", action="store_true", help="delete the index first")
    parser.add_argument("--no-vectorizer", action="store_true", help="omit the Azure OpenAI vectorizer (keyword/semantic only)")
    args = parser.parse_args()
    load_env()

    index_name = os.environ.get("AI_SEARCH_INDEX", "hbl-site-knowledge")
    dimensions = int(os.environ.get("AI_SEARCH_VECTOR_DIMENSIONS", "1536"))
    embedding_model = os.environ.get("FOUNDRY_EMBEDDING_MODEL_NAME", "text-embedding-3-small")
    credential = DefaultAzureCredential()
    index_client = SearchIndexClient(endpoint=os.environ["AI_SEARCH_ENDPOINT"], credential=credential)

    vectorizer = None
    if not args.no_vectorizer:
        vectorizer = AzureOpenAIVectorizer(
            vectorizer_name=VECTORIZER,
            parameters=AzureOpenAIVectorizerParameters(
                resource_url=foundry_openai_url(os.environ["FOUNDRY_PROJECT_ENDPOINT"]),
                deployment_name=embedding_model,
                model_name=embedding_model,
            ),
        )

    if args.recreate:
        try:
            index_client.delete_index(index_name)
            print(f"Deleted index {index_name}")
        except ResourceNotFoundError:
            pass
    index_client.create_or_update_index(build_index(index_name, dimensions, vectorizer))
    print(f"Index {index_name} ready ({dimensions} dims, vectorizer={'yes' if vectorizer else 'no'})")

    documents: list[dict] = []
    token = credential.get_token("https://cognitiveservices.azure.com/.default").token
    with OpenAI(base_url=foundry_openai_url(os.environ["FOUNDRY_PROJECT_ENDPOINT"]) + "/openai/v1", api_key=token) as openai_client:
        for source, title, text in read_documents():
            chunks = chunk_document(text)
            embeddings = openai_client.embeddings.create(model=embedding_model, input=chunks, dimensions=dimensions)
            for i, (chunk, item) in enumerate(zip(chunks, embeddings.data)):
                documents.append(
                    {
                        "id": hashlib.sha1(f"{source}:{i}".encode()).hexdigest(),
                        "title": title,
                        "source": source,
                        "content": chunk,
                        "chunk_id": i,
                        "content_vector": item.embedding,
                    }
                )
            print(f"  {source:42s} {len(chunks)} chunks")

    search_client = SearchClient(endpoint=os.environ["AI_SEARCH_ENDPOINT"], index_name=index_name, credential=credential)
    results = search_client.upload_documents(documents)
    failed = [r for r in results if not r.succeeded]
    print(f"Uploaded {len(documents) - len(failed)}/{len(documents)} chunks" + (f", {len(failed)} FAILED" if failed else ""))


if __name__ == "__main__":
    main()

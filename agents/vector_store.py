import chromadb
from sentence_transformers import SentenceTransformer

COLLECTION_NAME = "mandate_embeddings"
MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"


def main():
    client = chromadb.PersistentClient(path="agents/chroma_db")

    collection = client.get_or_create_collection(name=COLLECTION_NAME)

    model = SentenceTransformer(MODEL_NAME)

    sample_maps = [
        {
            "id": "map_001",
            "obligation_text": "Banks must update all customer KYC records within 30 days.",
            "metadata": {
                "authority": "RBI",
                "map_type": "KYC_AML",
                "priority": "High"
            }
        },
        {
            "id": "map_002",
            "obligation_text": "Banks must report cybersecurity incidents to RBI within the prescribed timeline.",
            "metadata": {
                "authority": "RBI",
                "map_type": "Cybersecurity",
                "priority": "Critical"
            }
        }
    ]

    texts = [item["obligation_text"] for item in sample_maps]
    embeddings = model.encode(texts).tolist()

    collection.add(
        ids=[item["id"] for item in sample_maps],
        documents=texts,
        embeddings=embeddings,
        metadatas=[item["metadata"] for item in sample_maps]
    )

    print("ChromaDB collection created ✅")
    print(f"Collection name: {COLLECTION_NAME}")
    print(f"Total documents stored: {collection.count()}")

    results = collection.query(
        query_embeddings=model.encode(["KYC update compliance requirement"]).tolist(),
        n_results=1
    )

    print("\nSemantic search test result:")
    print(results)


if __name__ == "__main__":
    main()
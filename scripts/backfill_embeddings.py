from gpu_doctor.collector.embeddings import migrate_pgvector  # or build_faiss
if __name__ == "__main__":
    migrate_pgvector()
    print("Embeddings created ✅")

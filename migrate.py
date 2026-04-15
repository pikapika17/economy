from database import init_db, migrate_from_json

if __name__ == "__main__":
    init_db()
    migrate_from_json("dados.json")
    print("Migração concluída com sucesso.")
"""
Fitora - build the RAG vector index.

Sources, in order of preference:
  --from-db    embed every active gym in the database (production path)
  default      embed data/processed/gyms.json (first-run / bootstrap path)

Usage:
    python -m scripts.build_index            # from the dataset JSON
    python -m scripts.build_index --from-db  # from the live database
    python -m scripts.build_index --test     # index, then run sample queries
"""
from __future__ import annotations
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.rag.vector_store import GymVectorStore, load_gyms_json   # noqa: E402

SAMPLE_QUERIES = [
    "below 1500 fee gyms",
    "AC gym under 2000 with personal trainer included",
    "ladies only gym with zumba and yoga",
    "cheapest non-ac gym for weight loss near Kakinada",
    "best rated premium gym with supplements and steam bath",
    "gym with smith machine and 10 years experienced coach",
    "1000 lopu budget gym kavali",
    "muscle gain gym with free trial within 10 km",
]


def build_from_json() -> list[dict]:
    gyms = load_gyms_json()
    print(f"[*] loaded {len(gyms)} gyms from dataset JSON")
    return gyms


def build_from_db() -> list[dict]:
    from app.api.admin import serialize_gym_for_rag
    from app.db.models import Gym, GymStatus
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        rows = db.query(Gym).filter(Gym.status == GymStatus.active).all()
        print(f"[*] loaded {len(rows)} active gyms from the database")
        payload = [serialize_gym_for_rag(db, g) for g in rows]
        for g in rows:
            g.indexed_in_rag = True
        db.commit()
        return payload
    finally:
        db.close()


def run_tests(gyms: list[dict]) -> None:
    from app.rag.retriever import GymRetriever

    retriever = GymRetriever(GymVectorStore.get())
    retriever.attach_gyms(gyms)

    print("\n" + "=" * 70)
    print("  SAMPLE RETRIEVALS")
    print("=" * 70)
    for q in SAMPLE_QUERIES:
        t0 = time.perf_counter()
        res = retriever.retrieve(q, top_k=3)
        ms = (time.perf_counter() - t0) * 1000

        parsed = {k: v for k, v in res["parsed"].items() if k != "raw_query"}
        print(f"\nQ: {q}")
        print(f"   parsed  : {parsed}")
        if res["relaxed_constraints"]:
            print(f"   relaxed : {res['relaxed_constraints']}")
        print(f"   {res['total_matches']} matches in {ms:.0f} ms")
        for i, h in enumerate(res["results"], 1):
            m = h["metadata"]
            coach = ("coach incl." if m["coach_included"]
                     else f"coach +Rs.{m['coach_fee']}")
            print(f"     {i}. {m['name'][:38]:<38} Rs.{m['monthly_fee']:<5} "
                  f"{'AC ' if m['is_ac'] else 'Non-AC'} {coach:<16} "
                  f"{m['rating']}* score={h['final_score']}")


def main() -> None:
    from_db = "--from-db" in sys.argv
    test = "--test" in sys.argv

    gyms = build_from_db() if from_db else build_from_json()
    if not gyms:
        print("[X] nothing to index", file=sys.stderr)
        sys.exit(1)

    print("[*] loading embedding model (first run downloads ~90 MB) ...")
    store = GymVectorStore.get()

    t0 = time.perf_counter()
    n = store.index_gyms(gyms, reset=True)
    dt = time.perf_counter() - t0

    print(f"[+] indexed {n} gyms in {dt:.1f}s ({dt / max(n, 1) * 1000:.0f} ms/gym)")
    print(f"[+] collection size: {store.count()}")

    if test:
        run_tests(gyms)

    print("\n[done] the chatbot is ready.")


if __name__ == "__main__":
    main()

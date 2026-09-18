"""
Fitora RAG - Chatbot / Answer Generation

Takes the retriever's ranked gyms and asks a local Ollama model to write a
short, grounded recommendation. The model is given ONLY the retrieved gym
facts and is instructed never to invent gyms, prices or phone numbers.

If Ollama is unavailable the service falls back to a deterministic template
answer built from the same facts - the product never hard-fails on the LLM.
"""
from __future__ import annotations
import logging
from typing import Any, Iterator

import ollama

log = logging.getLogger(__name__)

DEFAULT_MODEL = "qwen2.5:3b"

SYSTEM_PROMPT = """You are Fitora Assistant, a gym-discovery helper for the Kakinada region of Andhra Pradesh, India.

RULES - follow these exactly:
1. Recommend ONLY gyms from the CONTEXT below. Never invent a gym, price, phone number or address.
2. Always quote prices in rupees exactly as given, e.g. "Rs.1200/month".
3. Always state clearly whether the coach fee is INCLUDED in the membership or charged SEPARATELY. This is the single most important thing users care about.
4. Recommend the top 3 gyms at most. For each: name, locality, monthly fee, coach arrangement, and one concrete reason it fits the user's request.
5. Be concise - 3 to 6 short lines total. No markdown tables, no long paragraphs.
6. The user may write in English, Telugu, or a mix (Tenglish). Always reply in simple English.
7. If a constraint was relaxed (noted in CONTEXT), say so in one short line, e.g. "No AC gym under Rs.800, so here are the closest matches."
8. End with one short question inviting the user to pick a gym or refine the search.
"""


def _fmt_gym(rank: int, hit: dict[str, Any]) -> str:
    m = hit["metadata"]
    coach = ("coach INCLUDED in the fee"
             if m["coach_included"]
             else f"coach costs Rs.{m['coach_fee']}/month EXTRA (total Rs.{m['fee_with_coach']})")
    dist = (f", {hit['distance_from_user_km']} km from the user"
            if hit.get("distance_from_user_km") is not None else "")
    return (
        f"[{rank}] {m['name']} (id {m['gym_id']})\n"
        f"    Location: {m['locality']}, {m['district']} district{dist}\n"
        f"    Fee: Rs.{m['monthly_fee']}/month | {coach}\n"
        f"    {m['gym_type']}, {'AC' if m['is_ac'] else 'Non-AC'}"
        f"{', supplements available' if m['supplements'] else ''}\n"
        f"    Rating: {m['rating']}/5 ({m['review_count']} reviews) | "
        f"{m['equipment_count']} equipment items | {m['coach_count']} trainers"
        f" (up to {m['max_coach_experience']} yrs exp)\n"
    )


def build_context(retrieval: dict[str, Any]) -> str:
    lines = [f'USER REQUEST: "{retrieval["query"]}"', ""]

    p = retrieval["parsed"]
    understood = []
    if "max_fee" in p: understood.append(f"budget at most Rs.{p['max_fee']}/month")
    if "min_fee" in p: understood.append(f"budget at least Rs.{p['min_fee']}/month")
    if "is_ac" in p: understood.append("AC gym" if p["is_ac"] else "Non-AC gym")
    if p.get("coach_included"): understood.append("coach fee must be included")
    if p.get("wants_coach"): understood.append("wants a personal trainer")
    if "gym_type" in p: understood.append(p["gym_type"].lower())
    if "goal" in p: understood.append(f"goal: {p['goal'].replace('_', ' ')}")
    if "locality" in p: understood.append(f"in {p['locality']}")
    if p.get("near_me"): understood.append("close to the user")
    if "required_facilities" in p: understood.append("needs: " + ", ".join(p["required_facilities"]))
    if understood:
        lines.append("UNDERSTOOD CONSTRAINTS: " + "; ".join(understood))

    if retrieval["relaxed_constraints"]:
        lines.append(
            "NOTE: no gym matched everything, so these constraints were relaxed: "
            + ", ".join(retrieval["relaxed_constraints"])
        )

    lines.append("")
    lines.append("CONTEXT - matching gyms, already ranked best-first:")
    for i, hit in enumerate(retrieval["results"], 1):
        lines.append(_fmt_gym(i, hit))

    if not retrieval["results"]:
        lines.append("(no gyms matched)")
    return "\n".join(lines)


def _fallback_answer(retrieval: dict[str, Any]) -> str:
    res = retrieval["results"]
    if not res:
        return ("I could not find a gym matching that. Try widening your budget "
                "or searching a nearby town.")
    out = []
    if retrieval["relaxed_constraints"]:
        out.append("No exact match, so here are the closest options:")
    for h in res[:3]:
        m = h["metadata"]
        coach = ("coach included" if m["coach_included"]
                 else f"coach +Rs.{m['coach_fee']}/mo")
        out.append(
            f"- {m['name']}, {m['locality']} - Rs.{m['monthly_fee']}/month "
            f"({coach}), {'AC' if m['is_ac'] else 'Non-AC'}, rated {m['rating']}/5"
        )
    out.append("Which one would you like to see in detail?")
    return "\n".join(out)


class FitoraChatbot:
    def __init__(self, model: str = DEFAULT_MODEL, host: str | None = None) -> None:
        self.model = model
        self.client = ollama.Client(host=host) if host else ollama.Client()

    def available(self) -> bool:
        try:
            self.client.list()
            return True
        except Exception:
            return False

    # -------------------------------------------------------------- generate
    def answer(
        self,
        retrieval: dict[str, Any],
        history: list[dict[str, str]] | None = None,
    ) -> str:
        context = build_context(retrieval)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in (history or [])[-6:]:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": context})

        try:
            resp = self.client.chat(
                model=self.model,
                messages=messages,
                options={"temperature": 0.3, "num_predict": 400, "top_p": 0.9},
            )
            return resp["message"]["content"].strip()
        except Exception as e:
            log.warning("Ollama unavailable (%s) - using template fallback", e)
            return _fallback_answer(retrieval)

    def answer_stream(
        self,
        retrieval: dict[str, Any],
        history: list[dict[str, str]] | None = None,
    ) -> Iterator[str]:
        context = build_context(retrieval)
        messages = [{"role": "system", "content": SYSTEM_PROMPT}]
        for turn in (history or [])[-6:]:
            messages.append({"role": turn["role"], "content": turn["content"]})
        messages.append({"role": "user", "content": context})

        try:
            for chunk in self.client.chat(
                model=self.model, messages=messages, stream=True,
                options={"temperature": 0.3, "num_predict": 400, "top_p": 0.9},
            ):
                piece = chunk.get("message", {}).get("content", "")
                if piece:
                    yield piece
        except Exception as e:
            log.warning("Ollama stream unavailable (%s) - using template fallback", e)
            yield _fallback_answer(retrieval)

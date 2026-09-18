"use client";

import { AnimatePresence, motion } from "framer-motion";
import {
  CreditCard, Dumbbell, MapPin, MessageSquare, Search, Send, Sparkles, User,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";
import toast from "react-hot-toast";
import { AppShell, type NavItem } from "@/components/AppShell";
import { GymCard, type GymCardData } from "@/components/GymCard";
import { Avatar } from "@/components/ui";
import { api, ApiError, chatStream, getProfile } from "@/lib/api";
import { getLocation } from "@/lib/utils";

const NAV: NavItem[] = [
  { href: "/chat", label: "Find a gym", icon: MessageSquare },
  { href: "/gyms", label: "Browse", icon: Search },
  { href: "/memberships", label: "My memberships", icon: CreditCard },
  { href: "/profile", label: "Profile", icon: User },
];

type Turn = {
  role: "user" | "assistant";
  content: string;
  gyms?: GymCardData[];
  chips?: string[];
  relaxed?: string[];
  pending?: boolean;
};

export default function ChatPage() {
  const [turns, setTurns] = useState<Turn[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>([]);
  const [coords, setCoords] = useState<{ lat: number; lon: number } | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const profile = typeof window !== "undefined" ? getProfile<any>("user") : null;
  const firstName = profile?.full_name?.split(" ")[0] ?? "there";

  useEffect(() => {
    api.chatSuggestions()
      .then((r) => setSuggestions(r.suggestions ?? []))
      .catch(() => {});
    // A fresh browser fix beats the saved address, but either works.
    getLocation().then((loc) => loc && setCoords(loc));
  }, []);

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" });
  }, [turns]);

  async function send(text?: string) {
    const message = (text ?? input).trim();
    if (!message || busy) return;

    setInput("");
    setBusy(true);
    setTurns((t) => [
      ...t,
      { role: "user", content: message },
      { role: "assistant", content: "", pending: true },
    ]);

    let streamedText = "";
    let gotMeta = false;

    await chatStream(
      {
        message,
        latitude: coords?.lat,
        longitude: coords?.lon,
        history: turns
          .filter((t) => !t.pending)
          .slice(-6)
          .map((t) => ({ role: t.role, content: t.content })),
        top_k: 6,
      },
      {
        // Gym cards render the instant they're known - no need to wait for
        // the LLM to finish writing the answer text around them.
        onMeta: (meta) => {
          gotMeta = true;
          setTurns((t) => {
            const next = [...t];
            next[next.length - 1] = {
              role: "assistant",
              content: "",
              pending: false,
              gyms: meta.gyms ?? [],
              chips: meta.interpretation?.understood ?? [],
              relaxed: meta.interpretation?.relaxed ?? [],
            };
            return next;
          });
        },
        onToken: (token) => {
          streamedText += token;
          setTurns((t) => {
            const next = [...t];
            const last = next[next.length - 1];
            next[next.length - 1] = { ...last, content: streamedText };
            return next;
          });
        },
        onError: (msg) => {
          setTurns((t) => {
            const next = [...t];
            next[next.length - 1] = { role: "assistant", content: msg };
            return next;
          });
          toast.error(msg);
        },
      },
    );

    if (!gotMeta) {
      // Stream never got as far as the meta event - fall back so the
      // conversation doesn't end on an empty bubble.
      setTurns((t) => {
        const next = [...t];
        if (next[next.length - 1]?.pending) {
          next[next.length - 1] = {
            role: "assistant",
            content: "Something went wrong. Please try again.",
          };
        }
        return next;
      });
    }

    setBusy(false);
    inputRef.current?.focus();
  }

  const empty = turns.length === 0;

  return (
    <AppShell role="user" nav={NAV} loginPath="/login">
      <div className="max-w-4xl mx-auto px-4 sm:px-6 pb-40">
        {/* ------------------------------------------------- empty state */}
        {empty ? (
          <motion.div
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
            className="pt-14 sm:pt-20"
          >
            <div className="text-center">
              <div className="inline-grid place-items-center w-14 h-14 rounded-2xl bg-brand-gradient mb-5 animate-float">
                <Sparkles className="w-7 h-7 text-white" />
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">
                Hi {firstName}, what are you looking for?
              </h1>
              <p className="text-ink-400 mt-2.5 text-balance max-w-lg mx-auto">
                Describe the gym you want — budget, AC, a personal trainer, your area.
                Ask in English or Telugu.
              </p>
              {coords && (
                <p className="text-xs text-brand-400 mt-3 inline-flex items-center gap-1.5">
                  <MapPin className="w-3 h-3" />
                  Using your location for distances
                </p>
              )}
            </div>

            <div className="mt-10 grid sm:grid-cols-2 gap-2.5 stagger">
              {suggestions.map((s) => (
                <button
                  key={s}
                  onClick={() => send(s)}
                  className="card-hover text-left px-4 py-3.5 text-sm text-ink-200 animate-fade-up hover:text-white"
                >
                  <Search className="w-3.5 h-3.5 inline mr-2 text-ink-500" />
                  {s}
                </button>
              ))}
            </div>
          </motion.div>
        ) : (
          /* ---------------------------------------------- conversation */
          <div className="pt-6 space-y-7">
            <AnimatePresence initial={false}>
              {turns.map((t, i) => (
                <motion.div
                  key={i}
                  initial={{ opacity: 0, y: 12 }}
                  animate={{ opacity: 1, y: 0 }}
                  transition={{ duration: 0.3, ease: [0.16, 1, 0.3, 1] }}
                >
                  {t.role === "user" ? (
                    <div className="flex gap-3 justify-end">
                      <div className="bg-brand-gradient text-white rounded-2xl rounded-tr-md px-4 py-2.5 max-w-[80%]">
                        <p className="text-sm">{t.content}</p>
                      </div>
                      <Avatar
                        name={profile?.full_name ?? "You"}
                        src={profile?.photo_url}
                        size={32}
                        className="mt-0.5"
                      />
                    </div>
                  ) : (
                    <div className="flex gap-3">
                      <div className="w-8 h-8 rounded-full bg-brand-gradient grid place-items-center shrink-0 mt-0.5">
                        <Sparkles className="w-4 h-4 text-white" />
                      </div>

                      <div className="flex-1 min-w-0">
                        {t.pending ? (
                          <div className="flex items-center gap-1.5 h-8">
                            {[0, 1, 2].map((d) => (
                              <span
                                key={d}
                                className="w-2 h-2 rounded-full bg-ink-600 animate-bounce"
                                style={{ animationDelay: `${d * 140}ms` }}
                              />
                            ))}
                          </div>
                        ) : (
                          <>
                            {/* what the parser understood — builds trust */}
                            {t.chips && t.chips.length > 0 && (
                              <div className="flex flex-wrap gap-1.5 mb-3">
                                {t.chips.map((c) => (
                                  <span key={c} className="chip-brand text-[11px]">
                                    {c}
                                  </span>
                                ))}
                              </div>
                            )}

                            {t.relaxed && t.relaxed.length > 0 && (
                              <p className="text-xs text-warning mb-3">
                                No exact match, so these were relaxed:{" "}
                                {t.relaxed.join(", ")}
                              </p>
                            )}

                            <div className="card px-4 py-3">
                              <p className="text-sm text-ink-100 whitespace-pre-wrap leading-relaxed">
                                {t.content}
                              </p>
                            </div>

                            {t.gyms && t.gyms.length > 0 && (
                              <div className="mt-4 grid sm:grid-cols-2 gap-3">
                                {t.gyms.map((g, gi) => (
                                  <GymCard key={g.gym_code} gym={g} index={gi} compact />
                                ))}
                              </div>
                            )}
                          </>
                        )}
                      </div>
                    </div>
                  )}
                </motion.div>
              ))}
            </AnimatePresence>
            <div ref={endRef} />
          </div>
        )}
      </div>

      {/* ------------------------------------------------------ composer */}
      <div className="fixed bottom-0 left-0 right-0 z-30">
        <div className="bg-gradient-to-t from-ink-950 via-ink-950/95 to-transparent pt-8 pb-5">
          <div className="max-w-4xl mx-auto px-4 sm:px-6">
            <form
              onSubmit={(e) => {
                e.preventDefault();
                send();
              }}
              className="glass rounded-2xl p-2 flex items-center gap-2 shadow-2xl"
            >
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="AC gym under ₹1500 near me…"
                disabled={busy}
                className="flex-1 bg-transparent px-3 py-2.5 text-sm outline-none placeholder-ink-500 disabled:opacity-60"
              />
              <button
                type="submit"
                disabled={!input.trim() || busy}
                className="btn-primary btn-md !px-3.5 !rounded-xl"
                aria-label="Send"
              >
                <Send className="w-4 h-4" />
              </button>
            </form>
            <p className="text-[10px] text-ink-600 text-center mt-2">
              Answers come only from gyms listed on Fitora.
            </p>
          </div>
        </div>
      </div>
    </AppShell>
  );
}

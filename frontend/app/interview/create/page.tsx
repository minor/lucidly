"use client";

import { useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import {
  ArrowLeft,
  Plus,
  Trash2,
  Copy,
  Check,
  ChevronRight,
  Code,
  Globe,
  Layout,
  ClipboardList,
} from "lucide-react";
import {
  createInterviewRoom,
  addInterviewChallenge,
} from "@/lib/api";
import type { InterviewConfig } from "@/lib/types";

// ---------------------------------------------------------------------------
// Types for local form state
// ---------------------------------------------------------------------------

interface TestCaseInput {
  input: string;
  expected_output: string;
}

interface ChallengeForm {
  id: string; // local key
  title: string;
  description: string;
  category: "coding" | "frontend" | "system_design";
  starter_code: string;
  test_cases: TestCaseInput[];
}

const EMPTY_TEST_CASE: TestCaseInput = { input: "", expected_output: "" };

function newChallengeForm(): ChallengeForm {
  return {
    id: crypto.randomUUID(),
    title: "",
    description: "",
    category: "coding",
    starter_code: "",
    test_cases: [{ ...EMPTY_TEST_CASE }],
  };
}

const CATEGORY_META: Record<
  string,
  { label: string; icon: typeof Code; color: string }
> = {
  coding: { label: "Coding", icon: Code, color: "text-blue-500" },
  frontend: { label: "Frontend", icon: Globe, color: "text-green-500" },
  system_design: { label: "System Design", icon: Layout, color: "text-purple-500" },
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function CreateInterviewPage() {
  const router = useRouter();

  // Step state
  const [step, setStep] = useState<1 | 2 | 3>(1);

  // Step 1: Room info
  const [title, setTitle] = useState("");
  const [companyName, setCompanyName] = useState("");
  const [createdBy, setCreatedBy] = useState("");
  const [timeLimitMinutes, setTimeLimitMinutes] = useState(45);
  const [allowedModels, setAllowedModels] = useState<string[]>([]);
  const [showTestResults, setShowTestResults] = useState(true);

  // Step 2: Challenges
  const [challenges, setChallenges] = useState<ChallengeForm[]>([
    newChallengeForm(),
  ]);
  const [activeChallengeIdx, setActiveChallengeIdx] = useState(0);

  // Step 3: Result
  const [roomId, setRoomId] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [copied, setCopied] = useState(false);
  const [creating, setCreating] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ---- Challenge helpers ----

  const activeChallenge = challenges[activeChallengeIdx] ?? challenges[0];

  const updateChallenge = useCallback(
    (idx: number, patch: Partial<ChallengeForm>) => {
      setChallenges((prev) =>
        prev.map((c, i) => (i === idx ? { ...c, ...patch } : c))
      );
    },
    []
  );

  const addTestCase = useCallback(() => {
    updateChallenge(activeChallengeIdx, {
      test_cases: [...activeChallenge.test_cases, { ...EMPTY_TEST_CASE }],
    });
  }, [activeChallengeIdx, activeChallenge, updateChallenge]);

  const removeTestCase = useCallback(
    (tcIdx: number) => {
      updateChallenge(activeChallengeIdx, {
        test_cases: activeChallenge.test_cases.filter((_, i) => i !== tcIdx),
      });
    },
    [activeChallengeIdx, activeChallenge, updateChallenge]
  );

  const updateTestCase = useCallback(
    (tcIdx: number, field: "input" | "expected_output", value: string) => {
      updateChallenge(activeChallengeIdx, {
        test_cases: activeChallenge.test_cases.map((tc, i) =>
          i === tcIdx ? { ...tc, [field]: value } : tc
        ),
      });
    },
    [activeChallengeIdx, activeChallenge, updateChallenge]
  );

  const addChallenge = () => {
    const newCh = newChallengeForm();
    setChallenges((prev) => [...prev, newCh]);
    setActiveChallengeIdx(challenges.length);
  };

  const removeChallenge = (idx: number) => {
    if (challenges.length <= 1) return;
    setChallenges((prev) => prev.filter((_, i) => i !== idx));
    setActiveChallengeIdx((prev) =>
      prev >= challenges.length - 1 ? Math.max(0, prev - 1) : prev
    );
  };

  // ---- Submission ----

  const handleCreate = async () => {
    setCreating(true);
    setError(null);

    try {
      const config: InterviewConfig = {
        time_limit_minutes: timeLimitMinutes,
        allowed_models: allowedModels.length > 0 ? allowedModels : null,
        max_token_budget: null,
        show_test_results_to_candidate: showTestResults,
      };

      const room = await createInterviewRoom({
        created_by: createdBy || "anonymous",
        title,
        company_name: companyName,
        config,
      });

      // Add challenges
      for (const ch of challenges) {
        if (!ch.title.trim() || !ch.description.trim()) continue;
        const validTests = ch.test_cases.filter(
          (tc) => tc.input.trim() || tc.expected_output.trim()
        );
        await addInterviewChallenge(room.id, {
          title: ch.title,
          description: ch.description,
          category: ch.category,
          starter_code: ch.starter_code || undefined,
          test_cases:
            ch.category === "coding" && validTests.length > 0
              ? validTests
              : undefined,
        });
      }

      setRoomId(room.id);
      setInviteCode(room.invite_code);
      setStep(3);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setCreating(false);
    }
  };

  const inviteUrl =
    typeof window !== "undefined"
      ? `${window.location.origin}/interview/${inviteCode}`
      : "";

  const copyInviteLink = () => {
    navigator.clipboard.writeText(inviteUrl);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  // ---- Validation ----

  const step1Valid = title.trim().length > 0;
  const step2Valid = challenges.some(
    (c) => c.title.trim() && c.description.trim()
  );

  // ---- Render ----

  return (
    <div className="flex h-screen flex-col">
      {/* Header */}
      <header className="flex items-center gap-3 border-b border-border px-6 py-4">
        <button
          onClick={() =>
            step === 1
              ? router.push("/play")
              : step === 3
              ? router.push("/play")
              : setStep((s) => Math.max(1, s - 1) as 1 | 2 | 3)
          }
          className="text-muted hover:text-foreground transition-colors cursor-pointer"
        >
          <ArrowLeft className="h-4 w-4" />
        </button>
        <div>
          <h1 className="text-sm font-semibold">Create Interview</h1>
          <p className="text-xs text-muted">
            {step === 1
              ? "Step 1 — Room details"
              : step === 2
              ? "Step 2 — Add challenges"
              : "Done — Share invite link"}
          </p>
        </div>
      </header>

      {/* Step indicator */}
      <div className="flex items-center gap-2 px-6 py-3 border-b border-border">
        {[1, 2, 3].map((s) => (
          <div key={s} className="flex items-center gap-2">
            <div
              className={`h-7 w-7 rounded-full flex items-center justify-center text-xs font-medium ${
                s === step
                  ? "bg-foreground text-background"
                  : s < step
                  ? "bg-accent text-background"
                  : "bg-muted/20 text-muted"
              }`}
            >
              {s < step ? <Check className="h-3.5 w-3.5" /> : s}
            </div>
            {s < 3 && (
              <div
                className={`h-px w-12 ${
                  s < step ? "bg-accent" : "bg-border"
                }`}
              />
            )}
          </div>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        <div className="mx-auto max-w-2xl px-6 py-8">
          {/* ================= STEP 1 ================= */}
          {step === 1 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-semibold mb-1">Room Details</h2>
                <p className="text-sm text-muted">
                  Set up your interview room. Candidates will join via a unique
                  invite link.
                </p>
              </div>

              <div className="space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1.5">
                    Interview Title *
                  </label>
                  <input
                    type="text"
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    placeholder="e.g. Senior Frontend — Prompt Engineering Assessment"
                    className="w-full rounded-lg border border-input-border bg-input px-4 py-2.5 text-sm focus:border-accent focus:outline-none"
                  />
                </div>

                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-sm font-medium mb-1.5">
                      Company Name
                    </label>
                    <input
                      type="text"
                      value={companyName}
                      onChange={(e) => setCompanyName(e.target.value)}
                      placeholder="Acme Corp"
                      className="w-full rounded-lg border border-input-border bg-input px-4 py-2.5 text-sm focus:border-accent focus:outline-none"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1.5">
                      Your Name / Email
                    </label>
                    <input
                      type="text"
                      value={createdBy}
                      onChange={(e) => setCreatedBy(e.target.value)}
                      placeholder="jane@acme.com"
                      className="w-full rounded-lg border border-input-border bg-input px-4 py-2.5 text-sm focus:border-accent focus:outline-none"
                    />
                  </div>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1.5">
                    Time Limit (minutes)
                  </label>
                  <input
                    type="number"
                    min={5}
                    max={180}
                    value={timeLimitMinutes}
                    onChange={(e) =>
                      setTimeLimitMinutes(Number(e.target.value) || 45)
                    }
                    className="w-32 rounded-lg border border-input-border bg-input px-4 py-2.5 text-sm focus:border-accent focus:outline-none"
                  />
                </div>

                <div>
                  <label className="block text-sm font-medium mb-1.5">
                    Show test results to candidate?
                  </label>
                  <button
                    type="button"
                    onClick={() => setShowTestResults(!showTestResults)}
                    className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors cursor-pointer ${
                      showTestResults ? "bg-accent" : "bg-muted/30"
                    }`}
                  >
                    <span
                      className={`inline-block h-4 w-4 rounded-full bg-white transition-transform ${
                        showTestResults ? "translate-x-6" : "translate-x-1"
                      }`}
                    />
                  </button>
                </div>
              </div>

              <div className="flex justify-end pt-4">
                <button
                  onClick={() => setStep(2)}
                  disabled={!step1Valid}
                  className="flex items-center gap-2 rounded-lg bg-foreground px-5 py-2.5 text-sm font-medium text-background hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                >
                  Next: Add Challenges
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}

          {/* ================= STEP 2 ================= */}
          {step === 2 && (
            <div className="space-y-6">
              <div>
                <h2 className="text-lg font-semibold mb-1">
                  Add Challenges
                </h2>
                <p className="text-sm text-muted">
                  Create the questions candidates will solve. For coding
                  questions, add test cases.
                </p>
              </div>

              {/* Challenge tabs */}
              <div className="flex items-center gap-2 flex-wrap">
                {challenges.map((ch, i) => (
                  <button
                    key={ch.id}
                    onClick={() => setActiveChallengeIdx(i)}
                    className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium transition-colors cursor-pointer ${
                      i === activeChallengeIdx
                        ? "border-accent bg-accent/10 text-foreground"
                        : "border-border text-muted hover:text-foreground"
                    }`}
                  >
                    Q{i + 1}
                    {ch.title && (
                      <span className="max-w-[120px] truncate">
                        — {ch.title}
                      </span>
                    )}
                    {challenges.length > 1 && (
                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          removeChallenge(i);
                        }}
                        className="ml-1 text-muted hover:text-red-400 cursor-pointer"
                      >
                        <Trash2 className="h-3 w-3" />
                      </button>
                    )}
                  </button>
                ))}
                <button
                  onClick={addChallenge}
                  className="flex items-center gap-1 rounded-lg border border-dashed border-border px-3 py-1.5 text-xs text-muted hover:text-foreground hover:border-accent transition-colors cursor-pointer"
                >
                  <Plus className="h-3 w-3" />
                  Add
                </button>
              </div>

              {/* Active challenge form */}
              {activeChallenge && (
                <div className="space-y-4 rounded-xl border border-border p-5">
                  <div>
                    <label className="block text-sm font-medium mb-1.5">
                      Title *
                    </label>
                    <input
                      type="text"
                      value={activeChallenge.title}
                      onChange={(e) =>
                        updateChallenge(activeChallengeIdx, {
                          title: e.target.value,
                        })
                      }
                      placeholder="e.g. Two Sum"
                      className="w-full rounded-lg border border-input-border bg-input px-4 py-2.5 text-sm focus:border-accent focus:outline-none"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1.5">
                      Category *
                    </label>
                    <div className="flex gap-2">
                      {(
                        ["coding", "frontend", "system_design"] as const
                      ).map((cat) => {
                        const meta = CATEGORY_META[cat];
                        const Icon = meta.icon;
                        return (
                          <button
                            key={cat}
                            onClick={() =>
                              updateChallenge(activeChallengeIdx, {
                                category: cat,
                              })
                            }
                            className={`flex items-center gap-2 rounded-lg border px-4 py-2 text-sm font-medium transition-colors cursor-pointer ${
                              activeChallenge.category === cat
                                ? "border-accent bg-accent/10 text-foreground"
                                : "border-border text-muted hover:text-foreground"
                            }`}
                          >
                            <Icon
                              className={`h-4 w-4 ${
                                activeChallenge.category === cat
                                  ? meta.color
                                  : ""
                              }`}
                            />
                            {meta.label}
                          </button>
                        );
                      })}
                    </div>
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1.5">
                      Description *
                    </label>
                    <textarea
                      value={activeChallenge.description}
                      onChange={(e) =>
                        updateChallenge(activeChallengeIdx, {
                          description: e.target.value,
                        })
                      }
                      rows={4}
                      placeholder="Describe the problem. Be specific about inputs, outputs, and constraints."
                      className="w-full rounded-lg border border-input-border bg-input px-4 py-2.5 text-sm focus:border-accent focus:outline-none resize-none"
                    />
                  </div>

                  <div>
                    <label className="block text-sm font-medium mb-1.5">
                      Starter Code (optional)
                    </label>
                    <textarea
                      value={activeChallenge.starter_code}
                      onChange={(e) =>
                        updateChallenge(activeChallengeIdx, {
                          starter_code: e.target.value,
                        })
                      }
                      rows={4}
                      placeholder="def two_sum(nums, target):&#10;    pass"
                      className="w-full rounded-lg border border-input-border bg-input px-4 py-2.5 text-sm font-mono focus:border-accent focus:outline-none resize-none"
                    />
                  </div>

                  {/* Test Cases (coding only) */}
                  {activeChallenge.category === "coding" && (
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <label className="text-sm font-medium">
                          Test Cases
                        </label>
                        <button
                          onClick={addTestCase}
                          className="flex items-center gap-1 text-xs text-accent hover:text-accent/80 cursor-pointer"
                        >
                          <Plus className="h-3 w-3" />
                          Add test case
                        </button>
                      </div>
                      <div className="space-y-2">
                        {activeChallenge.test_cases.map((tc, tcIdx) => (
                          <div
                            key={tcIdx}
                            className="flex items-start gap-2 rounded-lg border border-border p-3"
                          >
                            <div className="flex-1 space-y-2">
                              <input
                                type="text"
                                value={tc.input}
                                onChange={(e) =>
                                  updateTestCase(
                                    tcIdx,
                                    "input",
                                    e.target.value
                                  )
                                }
                                placeholder="Input: e.g. two_sum([2,7,11,15], 9)"
                                className="w-full rounded-md border border-input-border bg-input px-3 py-1.5 text-xs font-mono focus:border-accent focus:outline-none"
                              />
                              <input
                                type="text"
                                value={tc.expected_output}
                                onChange={(e) =>
                                  updateTestCase(
                                    tcIdx,
                                    "expected_output",
                                    e.target.value
                                  )
                                }
                                placeholder="Expected: e.g. [0, 1]"
                                className="w-full rounded-md border border-input-border bg-input px-3 py-1.5 text-xs font-mono focus:border-accent focus:outline-none"
                              />
                            </div>
                            {activeChallenge.test_cases.length > 1 && (
                              <button
                                onClick={() => removeTestCase(tcIdx)}
                                className="mt-1 text-muted hover:text-red-400 cursor-pointer"
                              >
                                <Trash2 className="h-3.5 w-3.5" />
                              </button>
                            )}
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              )}

              {error && (
                <div className="rounded-lg bg-red-400/10 border border-red-400/20 px-4 py-3 text-sm text-red-400">
                  {error}
                </div>
              )}

              <div className="flex items-center justify-between pt-4">
                <button
                  onClick={() => setStep(1)}
                  className="text-sm text-muted hover:text-foreground cursor-pointer"
                >
                  Back
                </button>
                <button
                  onClick={handleCreate}
                  disabled={!step2Valid || creating}
                  className="flex items-center gap-2 rounded-lg bg-foreground px-5 py-2.5 text-sm font-medium text-background hover:opacity-90 disabled:opacity-40 disabled:cursor-not-allowed cursor-pointer"
                >
                  {creating ? "Creating…" : "Create Interview"}
                  <ChevronRight className="h-4 w-4" />
                </button>
              </div>
            </div>
          )}

          {/* ================= STEP 3 ================= */}
          {step === 3 && (
            <div className="space-y-8 text-center">
              <div>
                <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-accent/10 mb-4">
                  <ClipboardList className="h-8 w-8 text-accent" />
                </div>
                <h2 className="text-2xl font-bold mb-2">
                  Interview Created!
                </h2>
                <p className="text-sm text-muted max-w-md mx-auto">
                  Share the invite link below with your candidate. You can
                  observe their session in real-time.
                </p>
              </div>

              {/* Invite link */}
              <div className="mx-auto max-w-lg">
                <label className="block text-sm font-medium mb-2 text-left">
                  Candidate Invite Link
                </label>
                <div className="flex items-center gap-2">
                  <div className="flex-1 rounded-lg border border-border bg-code-bg px-4 py-3 text-sm font-mono text-foreground truncate text-left">
                    {inviteUrl}
                  </div>
                  <button
                    onClick={copyInviteLink}
                    className="flex items-center gap-1.5 rounded-lg bg-foreground px-4 py-3 text-sm font-medium text-background hover:opacity-90 cursor-pointer shrink-0"
                  >
                    {copied ? (
                      <>
                        <Check className="h-4 w-4" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="h-4 w-4" />
                        Copy
                      </>
                    )}
                  </button>
                </div>
              </div>

              {/* Actions */}
              <div className="flex flex-col items-center gap-3">
                <button
                  onClick={() =>
                    router.push(`/interview/observe/${roomId}`)
                  }
                  className="rounded-lg bg-accent px-6 py-2.5 text-sm font-medium text-background hover:opacity-90 cursor-pointer"
                >
                  Open Live Dashboard
                </button>
                <button
                  onClick={() => {
                    setStep(1);
                    setTitle("");
                    setCompanyName("");
                    setCreatedBy("");
                    setChallenges([newChallengeForm()]);
                    setActiveChallengeIdx(0);
                    setRoomId("");
                    setInviteCode("");
                  }}
                  className="text-sm text-muted hover:text-foreground underline underline-offset-4 cursor-pointer"
                >
                  Create Another Interview
                </button>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

import { useState } from "react";
import type { TestCaseResult } from "@/lib/api";

export interface UseTestResults {
  testResults: TestCaseResult[] | null;
  runningTests: boolean;
  latestCode: string;
  testTab: "results" | "code";
  setTestTab: (tab: "results" | "code") => void;
  startEval: () => void;
  cancelEval: () => void;
  setResults: (results: TestCaseResult[]) => void;
  setCode: (code: string) => void;
  reset: () => void;
}

export function useTestResults(): UseTestResults {
  const [testResults, setTestResults] = useState<TestCaseResult[] | null>(null);
  const [runningTests, setRunningTests] = useState(false);
  const [latestCode, setLatestCode] = useState("");
  const [testTab, setTestTab] = useState<"results" | "code">("results");

  return {
    testResults,
    runningTests,
    latestCode,
    testTab,
    setTestTab,
    startEval: () => setRunningTests(true),
    cancelEval: () => setRunningTests(false),
    setResults: (results) => {
      setTestResults(results);
      setRunningTests(false);
    },
    setCode: (code) => setLatestCode(code),
    reset: () => {
      setTestResults(null);
      setRunningTests(false);
    },
  };
}

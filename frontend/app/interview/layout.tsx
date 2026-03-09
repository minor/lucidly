import type { ReactNode } from "react";
import { notFound } from "next/navigation";

// DISABLED: Interview mode frontend routes.
// To re-enable /interview/* pages, set this to true.
const INTERVIEW_MODE_ENABLED = false;

interface InterviewLayoutProps {
  children: ReactNode;
}

export default function InterviewLayout({ children }: InterviewLayoutProps) {
  if (!INTERVIEW_MODE_ENABLED) {
    notFound();
  }
  return <>{children}</>;
}

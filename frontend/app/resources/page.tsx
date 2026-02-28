"use client";

import { LibraryBig, ExternalLink, BookOpen, GraduationCap, Wrench, Users } from "lucide-react";

const categories = [
  {
    title: "Official Documentation",
    icon: BookOpen,
    description: "First-party guides from AI providers",
    resources: [
      {
        name: "Anthropic – Prompt Engineering Guide",
        url: "https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/overview",
        description: "Comprehensive guide covering clarity, examples, chain-of-thought, XML tags, and more for Claude models.",
      },
      {
        name: "OpenAI – Prompt Engineering Guide",
        url: "https://platform.openai.com/docs/guides/prompt-engineering",
        description: "Best practices for GPT models including writing clear instructions, providing reference text, and splitting complex tasks.",
      },
      {
        name: "Google – Prompting Strategies",
        url: "https://ai.google.dev/gemini-api/docs/prompting-strategies",
        description: "Techniques for prompting Gemini models effectively, including multimodal prompting.",
      },
    ],
  },
  {
    title: "Courses & Tutorials",
    icon: GraduationCap,
    description: "Structured learning paths",
    resources: [
      {
        name: "DeepLearning.AI – ChatGPT Prompt Engineering for Developers",
        url: "https://www.deeplearning.ai/short-courses/chatgpt-prompt-engineering-for-developers/",
        description: "Free short course by Isa Fulford and Andrew Ng on using LLM APIs for summarization, inference, and more.",
      },
      {
        name: "Learn Prompting",
        url: "https://learnprompting.org/",
        description: "Open-source curriculum covering beginner to advanced prompt engineering techniques.",
      },
      {
        name: "Anthropic – Interactive Tutorial",
        url: "https://docs.anthropic.com/en/docs/build-with-claude/prompt-engineering/interactive-tutorial",
        description: "Hands-on, chapter-by-chapter tutorial walking through prompt engineering fundamentals with Claude.",
      },
    ],
  },
  {
    title: "Tools & Playgrounds",
    icon: Wrench,
    description: "Experiment and iterate on prompts",
    resources: [
      {
        name: "Anthropic Console & Workbench",
        url: "https://console.anthropic.com/",
        description: "Test prompts against Claude models, compare outputs, and generate production-ready code.",
      },
      {
        name: "OpenAI Playground",
        url: "https://platform.openai.com/playground",
        description: "Experiment with GPT models, adjust parameters, and prototype prompts interactively.",
      },
      {
        name: "Google AI Studio",
        url: "https://aistudio.google.com/",
        description: "Free tool to prototype with Gemini models, test prompts, and tune model behavior.",
      },
    ],
  },
  {
    title: "Community & Research",
    icon: Users,
    description: "Stay current with the community",
    resources: [
      {
        name: "Brex – Prompt Engineering Guide",
        url: "https://github.com/brexhq/prompt-engineering",
        description: "Popular open-source guide with practical tips, strategies, and real-world examples from Brex.",
      },
      {
        name: "Prompt Engineering Guide (DAIR.AI)",
        url: "https://www.promptingguide.ai/",
        description: "Research-driven guide covering techniques like few-shot, chain-of-thought, ReAct, and more.",
      },
      {
        name: "r/PromptEngineering",
        url: "https://www.reddit.com/r/PromptEngineering/",
        description: "Active Reddit community sharing tips, discoveries, and discussions on prompt engineering.",
      },
    ],
  },
];

export default function ResourcesPage() {
  return (
    <div className="flex h-screen flex-col bg-background text-foreground">
      <header className="flex items-center justify-center px-4 sm:px-8 py-2 sm:py-5">
        <div className="flex items-center gap-2">
          <LibraryBig className="h-6 w-6 text-accent" />
          <h1 className="text-xl font-bold tracking-tight">Resources</h1>
        </div>
      </header>

      <main className="flex-1 overflow-auto p-4 sm:p-8">
        <div className="mx-auto max-w-3xl">
          <p className="mb-8 text-center text-sm text-muted">
            A curated collection of prompt engineering guides, courses, and tools to help you get the most out of LLMs.
          </p>

          <div className="space-y-10">
            {categories.map((category) => {
              const Icon = category.icon;
              return (
                <section key={category.title}>
                  <div className="mb-4 flex items-center gap-2">
                    <Icon className="h-5 w-5 text-accent" />
                    <div>
                      <h2 className="text-base font-semibold">{category.title}</h2>
                      <p className="text-xs text-muted">{category.description}</p>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {category.resources.map((resource) => (
                      <a
                        key={resource.name}
                        href={resource.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="group block rounded-lg border border-border bg-card p-4 transition-colors hover:border-accent/50 hover:bg-card/80"
                      >
                        <div className="flex items-start justify-between gap-3">
                          <div className="min-w-0">
                            <h3 className="text-sm font-medium group-hover:text-accent transition-colors">
                              {resource.name}
                            </h3>
                            <p className="mt-1 text-xs text-muted leading-relaxed">
                              {resource.description}
                            </p>
                          </div>
                          <ExternalLink className="h-4 w-4 shrink-0 text-muted group-hover:text-accent transition-colors mt-0.5" />
                        </div>
                      </a>
                    ))}
                  </div>
                </section>
              );
            })}
          </div>
        </div>
      </main>
    </div>
  );
}
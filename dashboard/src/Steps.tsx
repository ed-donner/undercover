import { useCallback } from "react";
import {
  type DocumentName,
  listSections,
  listSteps,
  type Section,
  type Step,
} from "./api";
import { DOCUMENT_NAMES, formatClock } from "./format";
import { POLL_MS, useApi } from "./hooks";

const TOOL_LABELS = new Map([
  ["get_claim", "Reading the claim"],
  ["get_policy", "Reading the policy"],
  ["get_customer", "Reading the claim history"],
  ["get_policy_wording", "Reading the policy wording"],
  ["list_sections", "Reading the contents of the wording and the manual"],
  ["record_decision", "Recording the decision"],
  ["pay_claim", "Paying the claim"],
]);

interface SectionRead {
  document: DocumentName;
  section: number;
}

export function Steps({ claimId }: Readonly<{ claimId: string }>) {
  const load = useCallback(() => listSteps(claimId), [claimId]);
  const { data: steps } = useApi(load, POLL_MS);
  const { data: sections } = useApi(listSections);
  const name = (read: SectionRead) => sectionName(read, sections ?? []);
  const attempts = new Set(steps?.map((step) => step.thread_id)).size;
  return (
    <section className="panel" aria-label="The agent's steps">
      <h2>The agent&apos;s steps</h2>
      {steps?.length === 0 && <p className="muted">No steps yet.</p>}
      {steps && <SectionsRead steps={steps} name={name} />}
      <ol className="steps">
        {steps?.map((step, index) => (
          <StepItem
            key={step.step_id}
            step={step}
            attempt={
              attempts > 1 && step.thread_id !== steps[index - 1]?.thread_id
                ? attemptNumber(steps, index)
                : undefined
            }
            name={name}
          />
        ))}
      </ol>
    </section>
  );
}

function StepItem({
  step,
  attempt,
  name,
}: Readonly<{
  step: Step;
  attempt: number | undefined;
  name: (read: SectionRead) => string;
}>) {
  return (
    <>
      {attempt !== undefined && (
        <li className="attempt">
          <h3>Attempt {attempt}</h3>
        </li>
      )}
      <li className="step">
        <span className="mono muted small">{formatClock(step.created_at)}</span>
        <StepBody step={step} name={name} />
      </li>
    </>
  );
}

function SectionsRead({
  steps,
  name,
}: Readonly<{ steps: Step[]; name: (read: SectionRead) => string }>) {
  const names = [
    ...new Set(
      steps
        .map(sectionRead)
        .filter((read) => read !== undefined)
        .map(name),
    ),
  ];
  if (names.length === 0) return null;
  return (
    <section className="read" aria-label="What the agent read">
      <h3>What the agent read</h3>
      <ul>
        {names.map((title) => (
          <li key={title}>{title}</li>
        ))}
      </ul>
    </section>
  );
}

function StepBody({
  step,
  name,
}: Readonly<{ step: Step; name: (read: SectionRead) => string }>) {
  if (step.kind === "reply")
    return <p className="step-reply">{step.content}</p>;
  if (step.kind === "reminder" || step.kind === "failure") {
    return (
      <p className="refusal">
        <span className={`badge step-${step.kind}`}>
          {step.kind === "reminder" ? "Reminder" : "Failed"}
        </span>{" "}
        {step.content}
      </p>
    );
  }
  if (step.kind === "tool_call") {
    return (
      <div>
        <strong>{callLabel(step, name)}</strong>
        <code className="block mono small">{step.content}</code>
      </div>
    );
  }
  const refused = refusal(step.content);
  return (
    <div>
      {refused && (
        <p className="refusal">
          <span className="badge refused">Refused</span> {refused}
        </p>
      )}
      <details>
        <summary>What {step.name} returned</summary>
        <pre>{step.content}</pre>
      </details>
    </div>
  );
}

function callLabel(step: Step, name: (read: SectionRead) => string): string {
  const read = sectionRead(step);
  if (read) return `Reading ${name(read)}`;
  if (step.name === "search_documents") {
    const { query } = JSON.parse(step.content) as { query?: string };
    return `Searching the documents for "${query ?? ""}"`;
  }
  return TOOL_LABELS.get(step.name) ?? step.name;
}

/** The section a step read, if it read one. */
function sectionRead(step: Step): SectionRead | undefined {
  if (step.kind !== "tool_call" || step.name !== "read_section") {
    return undefined;
  }
  const read = JSON.parse(step.content) as Partial<SectionRead>;
  if (read.document === undefined || read.section === undefined) {
    return undefined;
  }
  return { document: read.document, section: read.section };
}

function sectionName(read: SectionRead, sections: Section[]): string {
  const found = sections.find(
    (section) =>
      section.document === read.document && section.section === read.section,
  );
  const name = `${DOCUMENT_NAMES[read.document]}, section ${String(read.section)}`;
  return found ? `${name}: ${found.title}` : name;
}

function attemptNumber(steps: Step[], index: number): number {
  return new Set(steps.slice(0, index + 1).map((step) => step.thread_id)).size;
}

/** The claims system's reason for refusing a request, if it refused. */
function refusal(content: string): string | undefined {
  if (!content.startsWith('{"detail":')) return undefined;
  const { detail } = JSON.parse(content) as { detail: unknown };
  return typeof detail === "string" ? detail : "The request wasn't valid.";
}

import { useEffect, useState } from "react";
import Markdown from "react-markdown";
import { getAgentInstructions } from "../api";

export function Instructions() {
  const [content, setContent] = useState<string | null>(null);

  useEffect(() => {
    void getAgentInstructions().then(setContent);
  }, []);

  if (content === null) return <p>Loading the instructions…</p>;

  return (
    <div className="panel instructions">
      <Markdown>{content}</Markdown>
    </div>
  );
}

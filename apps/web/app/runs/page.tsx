import type { Metadata } from "next";

import { RunsListView } from "@/components/runs/RunsListView";

export const metadata: Metadata = {
  title: "Runs — ProofLayer",
};

export default function RunsPage() {
  return <RunsListView />;
}

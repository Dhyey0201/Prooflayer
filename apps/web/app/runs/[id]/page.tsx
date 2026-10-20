import type { Metadata } from "next";

import { RunDetailView } from "@/components/runs/RunDetailView";

export const metadata: Metadata = {
  title: "Run detail — ProofLayer",
};

export default async function RunDetailPage({ params }: PageProps<"/runs/[id]">) {
  const { id } = await params;
  return <RunDetailView key={id} runId={id} />;
}

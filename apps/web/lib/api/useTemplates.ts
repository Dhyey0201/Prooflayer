"use client";

import { getTemplates } from "./client";
import { useAsyncResource } from "./useAsyncResource";
import type { Template } from "./types";

/** Fetches the trusted fixture registry from `GET /templates`. */
export function useTemplates() {
  return useAsyncResource<Template[]>(getTemplates);
}

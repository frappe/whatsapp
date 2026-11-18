import { jsonPaths, type Location } from "./serialize";
import type { FlowModel, Problem } from "./types";

export interface MetaValidationError {
  error: string;
  message: string;
  pointers?: { path?: string }[];
}

/** Meta's `validation_errors`, located on the model the uploaded JSON was serialized from. */
export function metaProblems(model: FlowModel, errors: MetaValidationError[]): Problem[] {
  const paths = jsonPaths(model);
  return errors.map((error) => {
    const path = error.pointers?.find((pointer) => pointer.path)?.path;
    const location = path ? closest(paths, path) : undefined;
    return {
      severity: "error",
      code: error.error,
      message: error.message,
      screenId: location?.screenId ?? "",
      ...(location?.blockId ? { blockId: location.blockId } : {}),
      ...(path ? { path } : {}),
    };
  });
}

function closest(paths: Map<string, Location>, path: string): Location | undefined {
  for (let prefix = path; prefix; prefix = parent(prefix)) {
    const location = paths.get(prefix);
    if (location) return location;
  }
  return undefined;
}

function parent(path: string): string {
  const cut = Math.max(path.lastIndexOf("."), path.lastIndexOf("["));
  return cut > 0 ? path.slice(0, cut) : "";
}

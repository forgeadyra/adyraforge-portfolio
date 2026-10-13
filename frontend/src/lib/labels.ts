import type { ProjectStatus } from "./api";

export const STATUS_LABEL: Record<ProjectStatus, string> = {
  planning: "Planning",
  in_progress: "In progress",
  review: "In review",
  completed: "Completed",
  on_hold: "On hold",
  cancelled: "Cancelled",
};

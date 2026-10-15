export type UploadFormat = "csv" | "geojson" | "json" | "zip" | "unsupported";

export interface UploadSchemaDetection {
  format: UploadFormat;
  detectedColumns: string[];
  delimiter?: string;
  isSupported: boolean;
  requiresManualReview: boolean;
  message: string;
}

export interface UploadDecisionState {
  canValidate: boolean;
  canApprove: boolean;
  canReject: boolean;
  canRun: boolean;
  canRetry: boolean;
  canCancel: boolean;
  requiredNextAction: string;
}

const CSV_EXTENSIONS = new Set([".csv", ".tsv", ".txt"]);
const JSON_EXTENSIONS = new Set([".json"]);
const GEOJSON_EXTENSIONS = new Set([".geojson"]);
const ZIP_EXTENSIONS = new Set([".zip"]);

function fileExtension(filename: string): string {
  const dotIndex = filename.lastIndexOf(".");
  return dotIndex >= 0 ? filename.slice(dotIndex).toLowerCase() : "";
}

export function detectUploadFormat(filename: string, contentType = ""): UploadFormat {
  const extension = fileExtension(filename);
  const normalizedContentType = contentType.toLowerCase();
  if (CSV_EXTENSIONS.has(extension) || normalizedContentType.includes("csv")) {
    return "csv";
  }
  if (GEOJSON_EXTENSIONS.has(extension) || normalizedContentType.includes("geo+json")) {
    return "geojson";
  }
  if (JSON_EXTENSIONS.has(extension) || normalizedContentType.includes("json")) {
    return "json";
  }
  if (ZIP_EXTENSIONS.has(extension) || normalizedContentType.includes("zip")) {
    return "zip";
  }
  return "unsupported";
}

export function detectDelimiter(sample: string): string {
  const firstLine = sample.split(/\r?\n/, 1)[0] ?? "";
  const candidates = [",", ";", "\t", "|"];
  return candidates.reduce((best, candidate) => {
    const bestCount = firstLine.split(best).length;
    const candidateCount = firstLine.split(candidate).length;
    return candidateCount > bestCount ? candidate : best;
  }, ",");
}

function splitHeader(headerLine: string, delimiter: string): string[] {
  return headerLine
    .replace(/^\uFEFF/, "")
    .split(delimiter)
    .map((column) => column.trim().replace(/^"|"$/g, ""))
    .filter(Boolean);
}

export function detectCsvSchema(text: string): UploadSchemaDetection {
  const delimiter = detectDelimiter(text);
  const headerLine = text.split(/\r?\n/, 1)[0] ?? "";
  const detectedColumns = splitHeader(headerLine, delimiter);
  return {
    format: "csv",
    detectedColumns,
    delimiter,
    isSupported: detectedColumns.length > 0,
    requiresManualReview: false,
    message:
      detectedColumns.length > 0
        ? `Detected ${detectedColumns.length} CSV columns.`
        : "CSV files need a header row before validation can run.",
  };
}

export function detectJsonSchema(text: string, format: "json" | "geojson"): UploadSchemaDetection {
  try {
    const payload = JSON.parse(text) as unknown;
    let firstRecord: Record<string, unknown> | null = null;
    if (
      format === "geojson" &&
      payload &&
      typeof payload === "object" &&
      Array.isArray((payload as { features?: unknown }).features)
    ) {
      const firstFeature = (payload as { features: Array<Record<string, unknown>> }).features[0];
      const properties = firstFeature?.properties;
      if (properties && typeof properties === "object" && !Array.isArray(properties)) {
        firstRecord = properties as Record<string, unknown>;
      }
    } else if (Array.isArray(payload)) {
      const first = payload.find((item) => item && typeof item === "object" && !Array.isArray(item));
      firstRecord = first ? (first as Record<string, unknown>) : null;
    } else if (payload && typeof payload === "object") {
      firstRecord = payload as Record<string, unknown>;
    }
    const detectedColumns = Object.keys(firstRecord ?? {});
    return {
      format,
      detectedColumns,
      isSupported: detectedColumns.length > 0,
      requiresManualReview: false,
      message:
        detectedColumns.length > 0
          ? `Detected ${detectedColumns.length} ${format.toUpperCase()} properties.`
          : "JSON files need object properties before validation can map fields.",
    };
  } catch {
    return {
      format,
      detectedColumns: [],
      isSupported: false,
      requiresManualReview: false,
      message: "The file is not valid JSON and cannot be previewed.",
    };
  }
}

export function unsupportedSchemaDetection(format: UploadFormat): UploadSchemaDetection {
  if (format === "zip") {
    return {
      format,
      detectedColumns: [],
      isSupported: true,
      requiresManualReview: true,
      message: "ZIP archives can be registered but require manual validation review.",
    };
  }
  return {
    format,
    detectedColumns: [],
    isSupported: false,
    requiresManualReview: false,
    message: "Supported upload formats are CSV, GeoJSON, JSON, and ZIP archives.",
  };
}

export function buildDefaultFieldMapping(
  requiredColumns: string[],
  detectedColumns: string[],
): Record<string, string> {
  const detectedByLower = new Map(detectedColumns.map((column) => [column.toLowerCase(), column]));
  return Object.fromEntries(
    requiredColumns.map((column) => [column, detectedByLower.get(column.toLowerCase()) ?? ""]),
  );
}

export function missingMappedColumns(
  requiredColumns: string[],
  fieldMapping: Record<string, string>,
): string[] {
  return requiredColumns.filter((column) => !fieldMapping[column]);
}

export interface UploadLifecycleStep {
  label: string;
  detail: string;
}

/**
 * Ingestion lifecycle stages for the Upload Center stepper (#176). The job
 * moves Upload → Validate → Approve → Run → Complete; `uploadLifecycleStep`
 * maps a backend job status onto the index of the active stage.
 */
export const UPLOAD_LIFECYCLE_STEPS: UploadLifecycleStep[] = [
  { label: "Upload", detail: "Register the source and upload the file to object storage" },
  { label: "Validate", detail: "Scan schema, rows, coordinates, and duplicates" },
  { label: "Approve", detail: "Review validation evidence and approve for the queue" },
  { label: "Run", detail: "Execute the ingestion worker" },
  { label: "Complete", detail: "Artifacts published — review the outputs" },
];

/** Index into {@link UPLOAD_LIFECYCLE_STEPS} for the given job status. */
export function uploadLifecycleStep(status: string): number {
  switch (status) {
    case "pending_upload":
      return 0;
    case "validation_failed":
      return 1;
    case "validated_ready":
    case "validated_with_errors":
    case "manual_review_required":
    case "manual_review":
      return 2;
    case "queued":
      return 3;
    case "running":
    case "failed":
    case "cancelled":
      return 3;
    case "completed":
      return 4;
    default:
      return 0;
  }
}

export function uploadDecisionForStatus(status: string): UploadDecisionState {
  if (status === "pending_upload") {
    return {
      canValidate: true,
      canApprove: false,
      canReject: true,
      canRun: false,
      canRetry: false,
      canCancel: false,
      requiredNextAction: "upload_object_then_validate",
    };
  }
  if (
    status === "validated_ready" ||
    status === "validated_with_errors" ||
    status === "manual_review_required"
  ) {
    return {
      canValidate: false,
      canApprove: true,
      canReject: true,
      canRun: false,
      canRetry: false,
      canCancel: false,
      requiredNextAction: "review_validation_then_approve_or_reject",
    };
  }
  if (status === "queued") {
    return {
      canValidate: false,
      canApprove: false,
      canReject: false,
      canRun: true,
      canRetry: false,
      canCancel: true,
      requiredNextAction: "run_ingestion_worker_execution",
    };
  }
  if (status === "running") {
    return {
      canValidate: false,
      canApprove: false,
      canReject: false,
      canRun: false,
      canRetry: false,
      canCancel: true,
      requiredNextAction: "wait_for_ingestion_worker_completion",
    };
  }
  if (["failed", "cancelled", "manual_review"].includes(status)) {
    return {
      canValidate: false,
      canApprove: false,
      canReject: status === "manual_review",
      canRun: false,
      canRetry: true,
      canCancel: false,
      requiredNextAction: status === "failed" ? "review_failure_then_retry_or_cancel" : "retry_or_archive_cancelled_job",
    };
  }
  if (status === "completed") {
    return {
      canValidate: false,
      canApprove: false,
      canReject: false,
      canRun: false,
      canRetry: false,
      canCancel: false,
      requiredNextAction: "review_completed_artifacts",
    };
  }
  return {
    canValidate: false,
    canApprove: false,
    canReject: ["validation_failed", "failed"].includes(status),
    canRun: false,
    canRetry: status === "failed",
    canCancel: false,
    requiredNextAction: "review_status",
  };
}

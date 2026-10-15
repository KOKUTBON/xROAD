import { describe, expect, test } from "vitest";

import {
  buildDefaultFieldMapping,
  detectCsvSchema,
  detectJsonSchema,
  detectUploadFormat,
  missingMappedColumns,
  unsupportedSchemaDetection,
  uploadDecisionForStatus,
  uploadLifecycleStep,
  UPLOAD_LIFECYCLE_STEPS,
} from "./upload-center";

describe("upload center schema detection", () => {
  test("detects a CSV upload happy path and maps required fields", () => {
    const schema = detectCsvSchema("crash_id;latitude;longitude\n1;41.1;16.8\n");
    const mapping = buildDefaultFieldMapping(["crash_id", "latitude"], schema.detectedColumns);

    expect(detectUploadFormat("crashes.csv", "text/csv")).toBe("csv");
    expect(schema).toMatchObject({
      format: "csv",
      delimiter: ";",
      detectedColumns: ["crash_id", "latitude", "longitude"],
      isSupported: true,
    });
    expect(mapping).toEqual({ crash_id: "crash_id", latitude: "latitude" });
    expect(missingMappedColumns(["crash_id", "latitude"], mapping)).toEqual([]);
  });

  test("detects validation-error setup for missing mapped fields", () => {
    const schema = detectJsonSchema('[{"id":"a","lat":41.1}]', "json");
    const mapping = buildDefaultFieldMapping(["crash_id", "latitude", "longitude"], schema.detectedColumns);

    expect(schema.detectedColumns).toEqual(["id", "lat"]);
    expect(missingMappedColumns(["crash_id", "latitude", "longitude"], mapping)).toEqual([
      "crash_id",
      "latitude",
      "longitude",
    ]);
  });

  test("marks unsupported files clearly and routes ZIP to manual review", () => {
    expect(detectUploadFormat("report.xlsx", "application/vnd.ms-excel")).toBe("unsupported");
    expect(unsupportedSchemaDetection("unsupported")).toMatchObject({
      isSupported: false,
      message: "Supported upload formats are CSV, GeoJSON, JSON, and ZIP archives.",
    });
    expect(unsupportedSchemaDetection("zip")).toMatchObject({
      isSupported: true,
      requiresManualReview: true,
    });
  });
});

describe("upload center decision state", () => {
  test("keeps approval available only after validation review states", () => {
    expect(uploadDecisionForStatus("pending_upload")).toMatchObject({
      canValidate: true,
      canApprove: false,
      canReject: true,
    });
    expect(uploadDecisionForStatus("validated_ready")).toMatchObject({
      canValidate: false,
      canApprove: true,
      canReject: true,
    });
    expect(uploadDecisionForStatus("queued")).toMatchObject({
      canValidate: false,
      canApprove: false,
      canReject: false,
      canRun: true,
      canCancel: true,
      requiredNextAction: "run_ingestion_worker_execution",
    });
    expect(uploadDecisionForStatus("failed")).toMatchObject({
      canRetry: true,
      requiredNextAction: "review_failure_then_retry_or_cancel",
    });
  });
});

describe("upload center lifecycle stepper", () => {
  test("declares the five governed lifecycle stages in order", () => {
    expect(UPLOAD_LIFECYCLE_STEPS.map((step) => step.label)).toEqual([
      "Upload",
      "Validate",
      "Approve",
      "Run",
      "Complete",
    ]);
  });

  test("maps each job status onto the active stage index", () => {
    expect(uploadLifecycleStep("pending_upload")).toBe(0);
    expect(uploadLifecycleStep("validated_ready")).toBe(2);
    expect(uploadLifecycleStep("validated_with_errors")).toBe(2);
    expect(uploadLifecycleStep("manual_review_required")).toBe(2);
    expect(uploadLifecycleStep("queued")).toBe(3);
    expect(uploadLifecycleStep("running")).toBe(3);
    expect(uploadLifecycleStep("completed")).toBe(4);
  });

  test("keeps a validation failure at the Validate stage", () => {
    expect(uploadLifecycleStep("validation_failed")).toBe(1);
  });

  test("every mapped index is a valid step", () => {
    for (const status of ["pending_upload", "validated_ready", "queued", "running", "completed", "weird"]) {
      const index = uploadLifecycleStep(status);
      expect(index).toBeGreaterThanOrEqual(0);
      expect(index).toBeLessThan(UPLOAD_LIFECYCLE_STEPS.length);
    }
  });
});

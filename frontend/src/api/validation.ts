/**
 * Runtime contract validation helpers.
 * Unknown schema versions and malformed payloads produce typed errors that
 * the UI surfaces visibly rather than silently coercing.
 */

import { z } from "zod";

export class SchemaVersionError extends Error {
  readonly expected: string;
  readonly received: string;
  constructor(expected: string, received: string) {
    super(
      `Unsupported schema_version: expected "${expected}", received "${received}". ` +
        "The backend or saved snapshot may be from an incompatible version."
    );
    this.name = "SchemaVersionError";
    this.expected = expected;
    this.received = received;
  }
}

export class ContractValidationError extends Error {
  readonly path: string;
  readonly issues: z.ZodIssue[];
  constructor(path: string, issues: z.ZodIssue[]) {
    super(
      `Contract validation failed for ${path}: ${issues
        .map((i) => `${i.path.join(".")} — ${i.message}`)
        .join("; ")}`
    );
    this.name = "ContractValidationError";
    this.path = path;
    this.issues = issues;
  }
}

export class TransportError extends Error {
  constructor(message: string, public readonly cause?: unknown) {
    super(message);
    this.name = "TransportError";
  }
}

export class BackendConflictError extends Error {
  readonly status: number;
  readonly code: string;
  constructor(status: number, code: string, message: string) {
    super(`Backend conflict (${status}): [${code}] ${message}`);
    this.name = "BackendConflictError";
    this.status = status;
    this.code = code;
  }
}

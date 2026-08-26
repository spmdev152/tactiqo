import { describe, expect, it } from "vitest";

import {
  DEFAULT_FORM_RANGE,
  DEFAULT_FORM_SCOPE,
  familyLabel,
  FORM_FAMILIES,
  FORM_METRICS,
  FORM_RANGES,
  FORM_SCOPES,
  formatMetricValue,
  isShareMetric,
  metricCeiling,
  metricLabel,
  rangeLabel,
  rangeSize,
  scopeLabel,
  SHARE_CEILING,
} from "@/features/fixtures/domain/form-metrics";

const SHARE_METRICS = [
  "win_share",
  "draw_share",
  "loss_share",
  "possession",
  "pass_accuracy",
  "cross_accuracy",
  "dribble_success",
] as const;

describe("form metrics vocabulary", () => {
  /**
   * GIVEN the twenty-five figures the backend publishes per sample
   * WHEN the vocabulary is read
   * THEN it holds exactly those members, with no duplicate among them
   */
  it("publishes the whole vocabulary once each", () => {
    expect(FORM_METRICS).toHaveLength(25);
    expect(new Set(FORM_METRICS).size).toBe(FORM_METRICS.length);
  });

  /**
   * GIVEN a vocabulary whose members every label map has to cover
   * WHEN each member is named
   * THEN every one resolves to copy rather than to nothing
   */
  it("names every member of every vocabulary", () => {
    for (const metric of FORM_METRICS) {
      expect(metricLabel(metric), metric).not.toBe("");
    }

    for (const range of FORM_RANGES) {
      expect(rangeLabel(range), range).not.toBe("");
    }

    for (const scope of FORM_SCOPES) {
      expect(scopeLabel(scope), scope).not.toBe("");
    }

    for (const family of FORM_FAMILIES) {
      expect(familyLabel(family), family).not.toBe("");
    }
  });

  /**
   * GIVEN the copy the interface shows for a window and for a scope
   * WHEN each is named
   * THEN it reads as the product decided rather than as the wire spells it
   */
  it("names the windows and scopes as product copy", () => {
    expect(FORM_RANGES.map(rangeLabel)).toEqual(["Last 3", "Last 6", "Season"]);

    expect(FORM_SCOPES.map(scopeLabel)).toEqual(["Overall", "Home / away"]);
  });

  /**
   * GIVEN the seven figures the backend measures as percentages
   * WHEN every member's unit is read
   * THEN exactly those seven are percentages and the other eighteen averages
   */
  it("owns which figures are percentages", () => {
    expect(FORM_METRICS.filter(isShareMetric)).toEqual([...SHARE_METRICS]);
  });

  /**
   * GIVEN four shares the platform computes and three it derives from provider counts
   * WHEN every member's ceiling is read
   * THEN only the platform's own four are bounded, and no average is
   */
  it("bounds only the shares the platform's own arithmetic guarantees", () => {
    expect(
      FORM_METRICS.filter((metric) => metricCeiling(metric) !== null),
    ).toEqual(["win_share", "draw_share", "loss_share", "possession"]);

    expect(metricCeiling("possession")).toBe(SHARE_CEILING);
    expect(metricCeiling("pass_accuracy")).toBeNull();
    expect(metricCeiling("cross_accuracy")).toBeNull();
    expect(metricCeiling("dribble_success")).toBeNull();
    expect(metricCeiling("goals")).toBeNull();
  });

  /**
   * GIVEN a window that counts matches and one bounded by a season instead
   * WHEN each window's size is read
   * THEN the counted windows state their target and the season states none
   */
  it("states how many matches a window asks for", () => {
    expect(rangeSize("last_3")).toBe(3);
    expect(rangeSize("last_6")).toBe(6);
    expect(rangeSize("season")).toBeNull();
  });

  /**
   * GIVEN the window and scope a freshly opened panel has to choose
   * WHEN the defaults are read
   * THEN both name members of their own vocabulary
   */
  it("defaults to a window and a scope the vocabulary defines", () => {
    expect(FORM_RANGES).toContain(DEFAULT_FORM_RANGE);
    expect(FORM_SCOPES).toContain(DEFAULT_FORM_SCOPE);
  });
});

describe("formatMetricValue", () => {
  /**
   * GIVEN a share the wire carries as a number out of a hundred
   * WHEN it is formatted
   * THEN it reads as a percentage to one decimal rather than as a bare number
   */
  it("formats a share as a percentage", () => {
    expect(formatMetricValue("win_share", 66.67)).toBe("66.7%");
    expect(formatMetricValue("possession", 54.2)).toBe("54.2%");
  });

  /**
   * GIVEN a per-match average, which several metrics carry below a tenth
   * WHEN it is formatted
   * THEN it keeps two decimals, so a rare card is not rounded away to nothing
   */
  it("formats an average to two decimals", () => {
    expect(formatMetricValue("goals", 1.6666)).toBe("1.67");
    expect(formatMetricValue("red_cards", 0.05)).toBe("0.05");
    expect(formatMetricValue("passes", 512)).toBe("512.00");
  });

  /**
   * GIVEN the same figure under a share metric and under an average metric
   * WHEN each is formatted
   * THEN the two read differently, because the unit is the metric's own
   */
  it("reads one number two ways depending on the metric", () => {
    expect(formatMetricValue("pass_accuracy", 85)).toBe("85.0%");
    expect(formatMetricValue("tackles", 85)).toBe("85.00");
  });

  /**
   * GIVEN the two ends of the range a share may occupy
   * WHEN each is formatted
   * THEN the ceiling reads as a full hundred rather than being rescaled
   */
  it("formats the ends of the share range", () => {
    expect(formatMetricValue("draw_share", 0)).toBe("0.0%");
    expect(formatMetricValue("draw_share", SHARE_CEILING)).toBe("100.0%");
  });
});

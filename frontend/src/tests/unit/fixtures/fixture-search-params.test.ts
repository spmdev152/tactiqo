import { describe, expect, it } from "vitest";

import {
  localDateToUtcDay,
  parseUtcDay,
  resolveLeagueIds,
  resolveUtcDay,
  utcDayToLocalDate,
} from "@/features/fixtures/domain/fixture-search-params";

const NOW = new Date("2026-08-25T22:40:00Z");

describe("resolveUtcDay", () => {
  /**
   * GIVEN a request that carries no date parameter
   * WHEN the day is resolved
   * THEN today's UTC calendar day is used
   */
  it("resolves an absent date to today", () => {
    expect(resolveUtcDay(undefined, NOW)).toBe("2026-08-25");
  });

  /**
   * GIVEN a date parameter that is not a calendar day
   * WHEN the day is resolved
   * THEN today's UTC calendar day is used instead of failing
   */
  it("resolves a malformed date to today", () => {
    expect(resolveUtcDay("yesterday", NOW)).toBe("2026-08-25");
  });

  /**
   * GIVEN a date parameter matching the shape but naming no calendar day
   * WHEN the day is resolved
   * THEN it is rejected rather than rolled forward into a different day
   */
  it("rejects a well-formed date that names no day", () => {
    expect(resolveUtcDay("2026-02-30", NOW)).toBe("2026-08-25");
    expect(resolveUtcDay("2026-13-01", NOW)).toBe("2026-08-25");
  });

  /**
   * GIVEN a date parameter repeated in the query
   * WHEN the day is resolved
   * THEN neither value is guessed at and today is used
   */
  it("rejects a repeated date parameter", () => {
    expect(resolveUtcDay(["2026-08-29", "2026-08-30"], NOW)).toBe("2026-08-25");
  });

  /**
   * GIVEN a valid date parameter
   * WHEN the day is resolved
   * THEN it is returned unchanged
   */
  it("keeps a valid day", () => {
    expect(resolveUtcDay("2026-08-29", NOW)).toBe("2026-08-29");
  });

  /**
   * GIVEN an instant late enough that the local and the UTC day differ
   * WHEN the fallback day is resolved
   * THEN the UTC day is used, matching the timezone the kick-offs are shown in
   */
  it("falls back to the UTC day rather than the local one", () => {
    expect(resolveUtcDay(undefined, new Date("2026-08-25T23:30:00Z"))).toBe(
      "2026-08-25",
    );
  });
});

describe("parseUtcDay", () => {
  /**
   * GIVEN a valid calendar day and a day picker round trip
   * WHEN the day is converted to a local date and back
   * THEN the original day survives, so navigation cannot drift by a day
   */
  it("round-trips a valid day through the picker representation", () => {
    const day = parseUtcDay("2026-08-29");

    expect(day).toBe("2026-08-29");
    expect(localDateToUtcDay(utcDayToLocalDate("2026-08-29"))).toBe(
      "2026-08-29",
    );
  });

  /**
   * GIVEN a calendar day whose month and day need zero padding
   * WHEN it is converted to a local date and back
   * THEN both components stay padded
   */
  it("pads single-digit components on the way back", () => {
    expect(localDateToUtcDay(utcDayToLocalDate("2026-01-05"))).toBe(
      "2026-01-05",
    );
  });
});

describe("resolveLeagueIds", () => {
  /**
   * GIVEN a league parameter holding a positive integer
   * WHEN the filter is resolved
   * THEN the internal identifier is returned as a number
   */
  it("resolves a positive integer", () => {
    expect(resolveLeagueIds("12")).toEqual([12]);
  });

  /**
   * GIVEN the parameter repeated, as choosing several competitions writes it
   * WHEN the filter is resolved
   * THEN every identifier is kept, in the order the query carried them
   */
  it("resolves a repeated parameter into every identifier", () => {
    expect(resolveLeagueIds(["3", "1", "2"])).toEqual([3, 1, 2]);
  });

  /**
   * GIVEN a parameter repeating one identifier
   * WHEN the filter is resolved
   * THEN the repeat is dropped, so it cannot widen the query it becomes
   */
  it("drops a repeated identifier", () => {
    expect(resolveLeagueIds(["2", "2", "5"])).toEqual([2, 5]);
  });

  /**
   * GIVEN a parameter mixing usable identifiers with unusable ones
   * WHEN the filter is resolved
   * THEN only the positive integers survive and nothing throws
   */
  it("keeps only the positive integers", () => {
    expect(resolveLeagueIds(undefined)).toEqual([]);
    expect(resolveLeagueIds("")).toEqual([]);
    expect(resolveLeagueIds("0")).toEqual([]);
    expect(resolveLeagueIds("-3")).toEqual([]);
    expect(resolveLeagueIds("1.5")).toEqual([]);
    expect(resolveLeagueIds("premier-league")).toEqual([]);
    expect(resolveLeagueIds(["1", "nope", "2"])).toEqual([1, 2]);
  });
});

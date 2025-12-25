import { describe, expect, it } from "vitest";
import { getTeamColors } from "./nfl-teams";

describe("getTeamColors", () => {
  it("returns known team colors", () => {
    expect(getTeamColors("KC")).toEqual({ primary: "#E31837", secondary: "#FFB81C" });
  });

  it("returns fallback colors for unknown/missing team", () => {
    expect(getTeamColors(undefined)).toEqual({ primary: "#0F172A", secondary: "#64748B" });
    expect(getTeamColors(null)).toEqual({ primary: "#0F172A", secondary: "#64748B" });
    expect(getTeamColors("XXX")).toEqual({ primary: "#0F172A", secondary: "#64748B" });
  });
});




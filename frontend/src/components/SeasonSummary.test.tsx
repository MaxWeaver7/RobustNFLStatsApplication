import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import type { Player } from "@/types/player";
import { SeasonSummary } from "./SeasonSummary";

vi.mock("./StatCard", () => ({
  StatCard: () => <div data-testid="stat-card" />,
}));

vi.mock("./charts/StatSparkline", () => ({
  StatSparkline: () => <div data-testid="sparkline" />,
}));

vi.mock("./common/CountUp", () => ({
  CountUp: () => <span data-testid="count-up" />,
}));

vi.mock("./TeamLogo", () => ({
  TeamLogo: () => <div data-testid="team-logo" />,
}));

describe("SeasonSummary team identity", () => {
  it("renders a super aura and a primary-color coin background for the player's team", () => {
    const player: Player = {
      player_id: "p1",
      player_name: "Patrick Mahomes",
      team: "KC",
      position: "QB",
    };

    render(<SeasonSummary player={player} />);

    const aura = screen.getByTestId("season-summary-team-aura");
    expect(aura).toHaveClass("blur-md");
    expect(aura).toHaveClass("opacity-40");
    expect(aura).toHaveStyle({
      background: "linear-gradient(135deg, #E31837, #FFB81C)",
    });

    const headshot = screen.getByTestId("season-summary-headshot-container");
    expect(headshot).toHaveStyle({ backgroundColor: "#E31837" });
    expect(headshot).toHaveClass("shadow-inner");
  });
});



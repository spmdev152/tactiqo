import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { LeagueFlag } from "@/features/fixtures/components/league-flag";
import type { League } from "@/features/fixtures/types/league";

const SPAIN: League = {
  id: 1,
  name: "La Liga",
  shortCode: "ESP PL",
  logoUrl: "",
  countryName: "Spain",
  countryFlagUrl:
    "https://cdn.sportmonks.com/images/countries/png/short/es.png",
};

const NOWHERE: League = {
  id: 2,
  name: "Continental Cup",
  shortCode: "",
  logoUrl: "",
  countryName: "",
  countryFlagUrl: "",
};

describe("LeagueFlag", () => {
  /**
   * GIVEN a competition whose country publishes a flag
   * WHEN the chip is rendered
   * THEN it carries an empty alt, since the name always sits beside it
   */
  it("renders a decorative flag", () => {
    const { container } = render(<LeagueFlag league={SPAIN} />);

    const flag = container.querySelector("img");

    expect(flag).not.toBeNull();
    expect(flag).toHaveAttribute("alt", "");
  });

  /**
   * GIVEN a competition with no published flag
   * WHEN the chip is rendered
   * THEN the box is kept as a neutral chip, rather than collapsed or requested
   */
  it("keeps the box without a published flag", () => {
    const { container } = render(<LeagueFlag league={NOWHERE} />);

    const placeholder = container.firstElementChild;

    expect(container.querySelector("img")).toBeNull();
    expect(placeholder).toHaveClass("h-3.5", "w-5", "bg-muted");
    expect(placeholder).toHaveAttribute("aria-hidden", "true");
  });

  /**
   * GIVEN a competition with no published flag shown in a group heading
   * WHEN the chip is rendered at the heading's size
   * THEN the placeholder takes that size too, so no group heading shifts
   */
  it("sizes the neutral chip like the flag it stands in for", () => {
    const { container } = render(
      <LeagueFlag className="h-[17px] w-6" league={NOWHERE} />,
    );

    expect(container.firstElementChild).toHaveClass("h-[17px]", "w-6");
  });

  /**
   * GIVEN two competitions whose source flags differ in aspect ratio
   * WHEN both chips are rendered
   * THEN both are cropped to the same box, so they read as one set
   */
  it("gives every flag the same box", () => {
    render(
      <>
        <LeagueFlag league={SPAIN} />
        <LeagueFlag league={{ ...SPAIN, id: 3 }} className="h-[17px] w-6" />
      </>,
    );

    const [standard, larger] = screen.getAllByRole("presentation", {
      hidden: true,
    });

    expect(standard).toHaveClass("h-3.5", "w-5", "object-cover");
    expect(larger).toHaveClass("h-[17px]", "w-6", "object-cover");
  });
});

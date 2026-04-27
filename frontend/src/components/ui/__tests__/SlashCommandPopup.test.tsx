import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import {
  filterCommands,
  SlashCommandPopup,
  SLASH_CATEGORY_LABELS,
  SLASH_COMMANDS,
  type SlashCommand,
} from "../SlashCommandPopup";

/**
 * Pure-function + render tests for the slash-command popup.
 *
 * These cover the parts that don't depend on backend state. Hook-level
 * tests (useSlashCommand error paths, retry behaviour, fetch mocks) live
 * in a separate file — they require the silent-catch fix from #132 to
 * be in main first.
 */

// ── filterCommands ─────────────────────────────────────────

function fullCommand(base: (typeof SLASH_COMMANDS)[number], display: string): SlashCommand {
  return { ...base, displayName: display, description: "", estimatedSeconds: undefined };
}

const COMMANDS: SlashCommand[] = SLASH_COMMANDS.map((b) =>
  fullCommand(b, b.slug.replace(/-/g, " ")),
);

describe("filterCommands", () => {
  it("returns the full list when query is empty", () => {
    expect(filterCommands(COMMANDS, "")).toHaveLength(COMMANDS.length);
  });

  it("returns the full list for whitespace-only query", () => {
    expect(filterCommands(COMMANDS, "   ")).toHaveLength(COMMANDS.length);
  });

  it("matches by alias prefix", () => {
    const out = filterCommands(COMMANDS, "draft");
    // all 5 /draft-X commands start with 'draft'
    const aliases = out.map((c) => c.alias).sort();
    expect(aliases).toEqual(
      ["draft-codev", "draft-license", "draft-mta", "draft-spa", "draft-ts"].sort(),
    );
  });

  it("matches by slug substring (not just prefix)", () => {
    // slug 'buyer-profile' should match query 'profile'
    const out = filterCommands(COMMANDS, "profile");
    expect(out.some((c) => c.slug === "buyer-profile")).toBe(true);
  });

  it("matches by displayName substring (case-insensitive)", () => {
    // displayName for paper-analysis was set to 'paper analysis'
    const out = filterCommands(COMMANDS, "PAPER");
    expect(out.some((c) => c.slug === "paper-analysis")).toBe(true);
  });

  it("returns empty list when no command matches", () => {
    expect(filterCommands(COMMANDS, "zzz-no-such-thing")).toEqual([]);
  });

  it("alias filtering only matches at the start (not anywhere)", () => {
    // 'mnc' is the alias for buyer-profile; query 'nc' must NOT match via alias
    // (filterCommands uses startsWith for alias)
    const out = filterCommands(COMMANDS, "nc");
    // It might still match other commands by slug, but must not include 'mnc' purely
    // because of alias matching; assert by checking the matched commands' actual matches
    // — the relevant assertion is that aliasMatch=='nc' for 'mnc' is FALSE
    const onlyAliasMatch = out.filter(
      (c) => !c.slug.toLowerCase().includes("nc") && !c.displayName.toLowerCase().includes("nc"),
    );
    expect(onlyAliasMatch).toEqual([]);
  });
});

// ── SLASH_COMMANDS catalogue invariants ───────────────────

describe("SLASH_COMMANDS catalogue", () => {
  it("has unique aliases", () => {
    const aliases = SLASH_COMMANDS.map((c) => c.alias);
    expect(new Set(aliases).size).toBe(aliases.length);
  });

  it("has unique slugs", () => {
    const slugs = SLASH_COMMANDS.map((c) => c.slug);
    expect(new Set(slugs).size).toBe(slugs.length);
  });

  it("each command has a non-empty example string", () => {
    for (const c of SLASH_COMMANDS) {
      expect(c.example).toBeTruthy();
      expect(c.example.length).toBeGreaterThan(0);
    }
  });

  it("includes all 5 /draft-X services (regression for #111-#113 family)", () => {
    const drafts = SLASH_COMMANDS.filter((c) => c.alias.startsWith("draft-")).map((c) => c.alias);
    expect(drafts.sort()).toEqual(
      ["draft-codev", "draft-license", "draft-mta", "draft-spa", "draft-ts"].sort(),
    );
  });
});

// ── Workspace-refactor category invariants (ROADMAP Phase 1, P1-1) ──
//
// Each command must declare a category so Phase 1 PRs can:
//   - hide C-class from popup (PR 7)
//   - drive workspace deep-links (PR 8)
//   - mark deprecated commands in docs (PR 10)
// Distribution numbers below are the Phase 1 baseline — bump them when
// new services are added or existing ones are reclassified, so silent
// drift of the slash inventory shows up in CI.

describe("SLASH_COMMANDS category metadata", () => {
  it("every command has a category in {A, B, C}", () => {
    for (const c of SLASH_COMMANDS) {
      expect(c.category).toMatch(/^[ABC]$/);
    }
  });

  it("category distribution matches Phase 1 baseline (A=12, B=12, C=5)", () => {
    const counts: Record<SlashCommand["category"], number> = { A: 0, B: 0, C: 0 };
    for (const c of SLASH_COMMANDS) counts[c.category] += 1;
    expect(counts).toEqual({ A: 12, B: 12, C: 5 });
  });

  it("C-class is exactly the 5 outreach-workspace migrations", () => {
    const cClass = SLASH_COMMANDS.filter((c) => c.category === "C").map((c) => c.alias).sort();
    expect(cClass).toEqual(
      ["batch-email", "email", "import-reply", "log", "outreach"].sort(),
    );
  });

  it("all /draft-X are B-class (form-driven workspace migration)", () => {
    const drafts = SLASH_COMMANDS.filter((c) => c.alias.startsWith("draft-"));
    for (const c of drafts) expect(c.category).toBe("B");
  });

  it("SLASH_CATEGORY_LABELS covers all categories", () => {
    expect(Object.keys(SLASH_CATEGORY_LABELS).sort()).toEqual(["A", "B", "C"]);
    for (const v of Object.values(SLASH_CATEGORY_LABELS)) expect(v.length).toBeGreaterThan(0);
  });
});

// ── SlashCommandPopup render ──────────────────────────────

describe("<SlashCommandPopup />", () => {
  const sample: SlashCommand[] = [
    {
      alias: "mnc",
      slug: "buyer-profile",
      displayName: "MNC Buyer Profile",
      description: "Buyer profile for MNC pharma",
      example: "Pfizer 肿瘤管线",
      estimatedSeconds: 60,
      category: "A",
    },
    {
      alias: "draft-spa",
      slug: "draft-spa",
      displayName: "Draft SPA / Merger",
      description: "Generate SPA skeleton",
      example: "某 biotech 被 MNC 收购",
      category: "B",
    },
  ];

  it("renders the empty state when commands list is empty", () => {
    render(
      <SlashCommandPopup commands={[]} activeIndex={0} onSelect={() => {}} onHover={() => {}} />,
    );
    expect(screen.getByText("No matching command")).toBeInTheDocument();
  });

  it("renders each command's alias, displayName and description", () => {
    render(
      <SlashCommandPopup
        commands={sample}
        activeIndex={0}
        onSelect={() => {}}
        onHover={() => {}}
      />,
    );
    expect(screen.getByText("/mnc")).toBeInTheDocument();
    expect(screen.getByText("MNC Buyer Profile")).toBeInTheDocument();
    expect(screen.getByText("Buyer profile for MNC pharma")).toBeInTheDocument();
    expect(screen.getByText("/draft-spa")).toBeInTheDocument();
    expect(screen.getByText("Draft SPA / Merger")).toBeInTheDocument();
  });

  it("shows estimated seconds when provided, omits when absent", () => {
    render(
      <SlashCommandPopup
        commands={sample}
        activeIndex={0}
        onSelect={() => {}}
        onHover={() => {}}
      />,
    );
    expect(screen.getByText("~60s")).toBeInTheDocument();
    // draft-spa has no estimatedSeconds
    expect(screen.queryByText(/^~\d+s$/)).toEqual(screen.getByText("~60s"));
  });

  it("each row carries role=option for accessibility", () => {
    render(
      <SlashCommandPopup
        commands={sample}
        activeIndex={1}
        onSelect={() => {}}
        onHover={() => {}}
      />,
    );
    const options = screen.getAllByRole("option");
    expect(options).toHaveLength(2);
    expect(options[1]).toHaveAttribute("aria-selected", "true");
    expect(options[0]).toHaveAttribute("aria-selected", "false");
  });
});

import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import BriefRenderer from "./BriefRenderer";

describe("BriefRenderer", () => {
  it("renders markdown heading", () => {
    render(<BriefRenderer markdown="# Hello World" />);
    expect(screen.getByText("Hello World")).toBeDefined();
  });

  it("renders copy and download buttons", () => {
    render(<BriefRenderer markdown="content" />);
    expect(screen.getByText("复制")).toBeDefined();
    expect(screen.getByText("下载")).toBeDefined();
  });
});

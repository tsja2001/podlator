import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import SubmitPage from "./SubmitPage";

describe("SubmitPage", () => {
  it("renders form", () => {
    const qc = new QueryClient();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <SubmitPage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByPlaceholderText(/youtube/)).toBeDefined();
    expect(screen.getByText("提交")).toBeDefined();
  });
});

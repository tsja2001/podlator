import { describe, it, expect } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import QueuePage from "./QueuePage";

describe("QueuePage", () => {
  it("renders filter buttons", () => {
    const qc = new QueryClient();
    render(
      <QueryClientProvider client={qc}>
        <MemoryRouter>
          <QueuePage />
        </MemoryRouter>
      </QueryClientProvider>,
    );
    expect(screen.getByText("全部")).toBeDefined();
    expect(screen.getByText("等待中")).toBeDefined();
    expect(screen.getByText("已完成")).toBeDefined();
  });
});

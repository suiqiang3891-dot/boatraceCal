import { render, screen } from "@testing-library/react";
import App from "./App";

test("App renders the first backtest dashboard from the bundled sample report", () => {
  render(<App />);

  expect(screen.getByRole("heading", { name: "BOAT RACE 回测工作台" })).toBeInTheDocument();
  expect(screen.getAllByText("+¥900").length).toBeGreaterThan(0);
  expect(screen.getByText("资金曲线")).toBeInTheDocument();
  expect(screen.getByText("场地")).toBeInTheDocument();
  expect(screen.getByText("trifecta_ordered")).toBeInTheDocument();
  expect(screen.getByText(/历史表现不代表未来结果/)).toBeInTheDocument();
});

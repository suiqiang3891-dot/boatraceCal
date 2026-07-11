import { fireEvent, render, screen } from "@testing-library/react";
import App from "./App";
import type { BacktestReport } from "./reportMetrics";

beforeEach(() => {
  localStorage.clear();
  vi.restoreAllMocks();
});

test("App renders the first smart table workbench from the bundled sample report", () => {
  render(<App />);

  expect(screen.getByRole("heading", { name: "BOAT RACE 智能表格工作台" })).toBeInTheDocument();
  expect(screen.getByText("业务日期")).toBeInTheDocument();
  expect(screen.getByText("2025-01-02")).toBeInTheDocument();
  expect(screen.getByText("候选 2")).toBeInTheDocument();
  expect(screen.getAllByText("+¥900").length).toBeGreaterThan(0);
  expect(screen.getByRole("columnheader", { name: "场地" })).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "模型概率" })).toBeInTheDocument();
  expect(screen.getByRole("columnheader", { name: "保守EV" })).toBeInTheDocument();
  expect(screen.getAllByText("三连单 1-2-3").length).toBeGreaterThan(0);
  expect(screen.getAllByText("25.0%").length).toBeGreaterThan(0);
  expect(screen.getByText("5.20")).toBeInTheDocument();
  expect(screen.getAllByText("待审核").length).toBeGreaterThan(1);
  expect(screen.getByText("审核 已确认 0 / PASS 0 / 待审 2")).toBeInTheDocument();
  expect(screen.getByRole("heading", { name: "行级详情" })).toBeInTheDocument();
  expect(screen.getByText("sample-data-v1")).toBeInTheDocument();
  expect(screen.getByText(/六艇概率构成等待模型明细/)).toBeInTheDocument();
  expect(screen.getByText(/历史表现不代表未来结果/)).toBeInTheDocument();
});

test("App updates the detail panel when a smart table row is selected", () => {
  render(<App />);

  fireEvent.click(screen.getByRole("button", { name: /20250102-01-02/ }));

  expect(screen.getByRole("heading", { name: "20250102-01-02" })).toBeInTheDocument();
  expect(screen.getAllByText("中").length).toBeGreaterThan(0);
  expect(screen.getAllByText("18.0%").length).toBeGreaterThan(0);
  expect(screen.getAllByText("未中").length).toBeGreaterThan(0);
});

test("App renders blocked reports without crashing", () => {
  const blockedReport: BacktestReport = {
    readiness: {
      status: "blocked",
      ready: false,
    },
    summary: null,
    equity_curve: null,
    slices: null,
    settlements: null,
  };

  render(<App report={blockedReport} />);

  expect(screen.getByText("BLOCKED")).toBeInTheDocument();
  expect(screen.getByText("没有可显示候选")).toBeInTheDocument();
  expect(screen.getByText(/等待数据质量检查/)).toBeInTheDocument();
});

test("App filters the smart table rows by decision state", () => {
  render(<App />);

  fireEvent.click(
    screen.getAllByRole("button", { name: "PASS" }).find((button) =>
      button.getAttribute("aria-pressed") === "false",
    ) as HTMLElement,
  );

  expect(screen.getByText("没有可显示候选")).toBeInTheDocument();
});

test("App applies local review actions without changing the report contract", () => {
  render(<App />);

  fireEvent.click(screen.getByRole("button", { name: "增加模拟单位" }));
  expect(screen.getByLabelText("当前模拟单位")).toHaveTextContent("2 单位");

  fireEvent.change(screen.getByLabelText("审核备注"), {
    target: { value: "盘口确认后保留" },
  });
  expect(screen.getByDisplayValue("盘口确认后保留")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "确认候选" }));
  expect(screen.getAllByText("已确认").length).toBeGreaterThan(1);
  expect(screen.getByText("审核 已确认 1 / PASS 0 / 待审 1")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "人工 PASS" }));
  expect(screen.getAllByText("已PASS").length).toBeGreaterThan(1);
  expect(screen.getByText("审核 已确认 0 / PASS 1 / 待审 1")).toBeInTheDocument();

  fireEvent.click(screen.getByRole("button", { name: "重置审核" }));
  expect(screen.getByLabelText("当前模拟单位")).toHaveTextContent("1 单位");
  expect(screen.getByDisplayValue("positive_ev / sample")).toBeInTheDocument();
  expect(screen.getByText("审核 已确认 0 / PASS 0 / 待审 2")).toBeInTheDocument();
});

test("App persists review actions for the current report draft", () => {
  const { unmount } = render(<App />);

  fireEvent.click(screen.getByRole("button", { name: "增加模拟单位" }));
  fireEvent.change(screen.getByLabelText("审核备注"), {
    target: { value: "刷新后仍保留" },
  });
  fireEvent.click(screen.getByRole("button", { name: "确认候选" }));
  unmount();

  render(<App />);

  expect(screen.getByText("审核 已确认 1 / PASS 0 / 待审 1")).toBeInTheDocument();
  expect(screen.getByLabelText("当前模拟单位")).toHaveTextContent("2 单位");
  expect(screen.getByDisplayValue("刷新后仍保留")).toBeInTheDocument();
});

test("App exports the reviewed smart table as an Excel compatible file", () => {
  const createdUrls: string[] = [];
  const createObjectUrl = vi.fn((blob: Blob) => {
      expect(blob).toBeInstanceOf(Blob);
      createdUrls.push("blob:review-export");
      return "blob:review-export";
    });
  const revokeObjectUrl = vi.fn();
  Object.defineProperty(URL, "createObjectURL", {
    configurable: true,
    value: createObjectUrl,
  });
  Object.defineProperty(URL, "revokeObjectURL", {
    configurable: true,
    value: revokeObjectUrl,
  });

  const clickedDownloads: Array<{ download: string; href: string }> = [];
  const originalCreateElement = document.createElement.bind(document);
  vi.spyOn(document, "createElement").mockImplementation((tagName, options) => {
    const element = originalCreateElement(tagName, options);
    if (tagName.toLowerCase() === "a") {
      element.click = vi.fn(() => {
        clickedDownloads.push({
          download: (element as HTMLAnchorElement).download,
          href: (element as HTMLAnchorElement).href,
        });
      });
    }
    return element;
  });

  render(<App />);

  fireEvent.change(screen.getByLabelText("审核备注"), {
    target: { value: "导出备注" },
  });
  fireEvent.click(screen.getByRole("button", { name: "确认候选" }));
  fireEvent.click(screen.getByRole("button", { name: "导出 Excel" }));

  expect(createObjectUrl).toHaveBeenCalledTimes(1);
  expect(revokeObjectUrl).toHaveBeenCalledWith("blob:review-export");
  expect(createdUrls).toEqual(["blob:review-export"]);
  expect(clickedDownloads).toEqual([
    {
      download: "boatrace-review-2025-01-02.csv",
      href: "blob:review-export",
    },
  ]);
});

import { useEffect, useRef } from "react";
import * as echarts from "echarts/core";
import { GridComponent, TooltipComponent } from "echarts/components";
import { LineChart } from "echarts/charts";
import { SVGRenderer } from "echarts/renderers";
import type { DashboardModel } from "./reportMetrics";

echarts.use([GridComponent, TooltipComponent, LineChart, SVGRenderer]);

type EquityChartProps = {
  points: DashboardModel["equityPoints"];
};

export function EquityChart({ points }: EquityChartProps) {
  const chartRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (import.meta.env.MODE === "test") {
      return undefined;
    }
    if (chartRef.current === null) {
      return undefined;
    }
    const chart = echarts.init(chartRef.current, undefined, { renderer: "svg" });
    chart.setOption({
      color: ["#0f766e", "#b45309"],
      tooltip: { trigger: "axis" },
      grid: { left: 46, right: 18, top: 20, bottom: 38 },
      xAxis: {
        type: "category",
        data: points.map((point) => point.raceId),
        axisLabel: { color: "#475569", interval: 0, fontSize: 11 },
        axisLine: { lineStyle: { color: "#cbd5e1" } },
      },
      yAxis: {
        type: "value",
        axisLabel: { color: "#475569" },
        splitLine: { lineStyle: { color: "#e2e8f0" } },
      },
      series: [
        {
          name: "资金",
          type: "line",
          smooth: true,
          symbolSize: 8,
          data: points.map((point) => point.equityYen),
          areaStyle: { color: "rgba(15, 118, 110, 0.12)" },
        },
      ],
    });

    const resize = () => chart.resize();
    window.addEventListener("resize", resize);
    return () => {
      window.removeEventListener("resize", resize);
      chart.dispose();
    };
  }, [points]);

  return <div ref={chartRef} className="equity-chart" aria-label="资金曲线图" />;
}

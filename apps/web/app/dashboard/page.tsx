import type { Metadata } from "next";

import { DashboardView } from "./dashboard-view";

export const metadata: Metadata = { title: "Dashboard" };

/**
 * A server component holding only the route metadata. The body is a client
 * component because it renders a chart, and `metadata` cannot be exported
 * from a client module — splitting them is the supported way to have both.
 */
export default function DashboardPage() {
  return <DashboardView />;
}

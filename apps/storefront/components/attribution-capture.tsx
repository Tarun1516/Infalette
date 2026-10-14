"use client";

import { useEffect } from "react";
import { captureAttribution } from "@/lib/api";

/**
 * Mounted once per app shell: records UTM/campaign params from any
 * landing URL into the last-touch attribution store used at checkout.
 */
export default function AttributionCapture() {
  useEffect(() => {
    captureAttribution();
  }, []);
  return null;
}

import { defineManifest } from "@crxjs/vite-plugin";

export default defineManifest({
  manifest_version: 3,
  name: "AI Page Agent",
  version: "0.1.0",
  description: "AI-агент, отвечающий на вопросы о текущей странице",
  action: { default_title: "AI Page Agent" },
  background: { service_worker: "src/background.ts", type: "module" },
  side_panel: { default_path: "index.html" },
  permissions: ["activeTab", "scripting", "tabs", "sidePanel"],
  host_permissions: ["http://localhost:8000/*"],
});

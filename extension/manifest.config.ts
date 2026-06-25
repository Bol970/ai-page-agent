import { defineManifest } from "@crxjs/vite-plugin";

export default defineManifest({
  manifest_version: 3,
  name: "AI Page Agent",
  version: "0.1.0",
  description: "AI-агент, отвечающий на вопросы о текущей странице",
  action: { default_popup: "index.html", default_title: "AI Page Agent" },
  permissions: ["activeTab", "scripting", "tabs"],
  host_permissions: ["http://localhost:8000/*"],
});
